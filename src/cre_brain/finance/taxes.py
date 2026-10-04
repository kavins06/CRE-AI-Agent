"""Property-tax reassessment schedules driven by explicit jurisdiction rules."""

from decimal import Decimal
from typing import Annotated

from pydantic import BeforeValidator, Field

from cre_brain.domain import CalcResult
from cre_brain.domain.base import Identifier
from cre_brain.domain.models import DomainModel
from cre_brain.finance._context import _calculation


def _reject_float(value: object) -> object:
    if isinstance(value, float):
        raise ValueError("Binary floating-point finance inputs are not allowed")
    return value


NonnegativeDecimal = Annotated[Decimal, BeforeValidator(_reject_float), Field(ge=0)]
Ratio = Annotated[Decimal, BeforeValidator(_reject_float), Field(ge=0, le=1)]


class TaxReassessmentRule(DomainModel):
    input_id: Identifier
    assessment_ratio: Ratio
    millage: NonnegativeDecimal
    phase_in_years: int = Field(strict=True, ge=1)
    annual_growth_cap: Ratio | None = None
    full_reassessment: bool


class TaxAssessment(DomainModel):
    input_id: Identifier
    sale_price: NonnegativeDecimal
    current_assessed_value: NonnegativeDecimal
    current_annual_tax: NonnegativeDecimal


@_calculation
def reassess_taxes(
    assessment: TaxAssessment,
    *,
    rule: TaxReassessmentRule,
    projection_years: int,
    calc_id: str,
    code_version: str,
) -> CalcResult:
    if isinstance(projection_years, bool) or projection_years < 1:
        raise ValueError("Tax projection requires at least one year")

    reassessed_value = (
        assessment.sale_price if rule.full_reassessment else assessment.current_assessed_value
    )
    raw_target = reassessed_value * rule.assessment_ratio * rule.millage / Decimal(1000)
    value_increased = assessment.sale_price > assessment.current_assessed_value
    floor_applied = (
        rule.full_reassessment and value_increased and raw_target < assessment.current_annual_tax
    )
    target_tax = max(raw_target, assessment.current_annual_tax) if floor_applied else raw_target
    outputs: dict[str, Decimal] = {
        "reassessed_value": reassessed_value,
        "target_annual_tax": target_tax,
        "reassessment_increase": target_tax - assessment.current_annual_tax,
        "current_annual_tax": assessment.current_annual_tax,
        "assessment_floor_applied": Decimal(floor_applied),
    }
    prior_tax = assessment.current_annual_tax
    for year in range(1, projection_years + 1):
        phase_fraction = min(Decimal(year) / Decimal(rule.phase_in_years), Decimal(1))
        phased_tax = (
            assessment.current_annual_tax
            + (target_tax - assessment.current_annual_tax) * phase_fraction
        )
        if rule.annual_growth_cap is not None and phased_tax > prior_tax:
            phased_tax = min(phased_tax, prior_tax * (Decimal(1) + rule.annual_growth_cap))
        outputs[f"year:{year}:property_tax"] = phased_tax
        prior_tax = phased_tax
    return CalcResult(
        calc_id=calc_id,
        fn="reassess_taxes",
        inputs={"tax_assessment": assessment.input_id, "jurisdiction_rule": rule.input_id},
        outputs=outputs,
        code_version=code_version,
    )
