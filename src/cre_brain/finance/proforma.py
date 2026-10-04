"""Monthly and annual operating projections with explicit calculation lineage."""

from decimal import Decimal
from typing import Annotated

from pydantic import BeforeValidator, Field

from cre_brain.domain import CalcResult
from cre_brain.domain.base import Identifier
from cre_brain.domain.models import DomainModel
from cre_brain.finance._context import _calculation

ZERO = Decimal()


def _reject_float(value: object) -> object:
    if isinstance(value, float):
        raise ValueError("Binary floating-point finance inputs are not allowed")
    return value


NonnegativeDecimal = Annotated[Decimal, BeforeValidator(_reject_float), Field(ge=0)]
Ratio = Annotated[Decimal, BeforeValidator(_reject_float), Field(ge=0, le=1)]
Growth = Annotated[Decimal, BeforeValidator(_reject_float), Field(gt=-1)]


class ProFormaInput(DomainModel):
    input_id: Identifier
    base_monthly_revenue: NonnegativeDecimal
    base_monthly_operating_expenses: NonnegativeDecimal
    annual_revenue_growth: Growth
    annual_expense_growth: Growth
    vacancy_rate: Ratio
    credit_loss_rate: Ratio
    monthly_reserves: NonnegativeDecimal
    projection_months: int = Field(strict=True, ge=1, le=360)


def _schedule_value(schedule: CalcResult | None, key: str) -> Decimal:
    if schedule is None:
        return ZERO
    try:
        value = schedule.outputs[key]
    except KeyError as error:
        raise ValueError(f"Schedule is missing required output {key!r}") from error
    if value < 0:
        raise ValueError(f"Schedule output {key!r} must be nonnegative")
    return value


@_calculation
def build_proforma(
    assumptions: ProFormaInput,
    *,
    value_add: CalcResult | None = None,
    taxes: CalcResult | None = None,
    calc_id: str,
    code_version: str,
) -> CalcResult:
    if value_add is not None and value_add.fn != "build_value_add_schedule":
        raise ValueError("value_add must be a value-add schedule calculation")
    if taxes is not None and taxes.fn != "reassess_taxes":
        raise ValueError("taxes must be a tax reassessment calculation")
    inputs = {"proforma": assumptions.input_id}
    if value_add is not None:
        inputs["value_add_schedule"] = value_add.calc_id
    if taxes is not None:
        inputs["tax_schedule"] = taxes.calc_id

    outputs: dict[str, Decimal] = {}
    annual: dict[int, dict[str, Decimal]] = {}
    for month in range(1, assumptions.projection_months + 1):
        year = ((month - 1) // 12) + 1
        year_values = annual.setdefault(
            year,
            {
                key: ZERO
                for key in (
                    "gross_potential_revenue",
                    "effective_gross_income",
                    "operating_expenses",
                    "property_tax",
                    "reserves",
                    "noi",
                    "renovation_cost",
                    "cash_flow",
                    "value_add_noi_impact",
                )
            },
        )
        growth_period = year - 1
        revenue_growth = (Decimal(1) + assumptions.annual_revenue_growth) ** growth_period
        base_revenue = assumptions.base_monthly_revenue * revenue_growth
        operating_expenses = (
            assumptions.base_monthly_operating_expenses
            * (Decimal(1) + assumptions.annual_expense_growth) ** growth_period
        )
        premium_income = _schedule_value(value_add, f"month:{month}:premium_rent_income")
        offline_rent_loss = (
            _schedule_value(value_add, f"month:{month}:offline_rent_loss") * revenue_growth
        )
        value_add_rent = premium_income - offline_rent_loss
        renovation_cost = _schedule_value(value_add, f"month:{month}:renovation_cost")
        gross_revenue = base_revenue + value_add_rent
        if gross_revenue < 0:
            raise ValueError("Value-add schedule cannot make gross revenue negative")
        vacancy_loss = gross_revenue * assumptions.vacancy_rate
        after_vacancy = gross_revenue - vacancy_loss
        credit_loss = after_vacancy * assumptions.credit_loss_rate
        effective_revenue = after_vacancy - credit_loss
        base_effective = (
            base_revenue
            * (Decimal(1) - assumptions.vacancy_rate)
            * (Decimal(1) - assumptions.credit_loss_rate)
        )
        value_add_noi_impact = effective_revenue - base_effective
        annual_tax = _schedule_value(taxes, f"year:{year}:property_tax")
        property_tax = annual_tax / Decimal(12)
        noi = effective_revenue - operating_expenses - property_tax - assumptions.monthly_reserves
        cash_flow = noi - renovation_cost
        monthly = {
            "base_revenue": base_revenue,
            "value_add_gross_rent_impact": value_add_rent,
            "gross_potential_revenue": gross_revenue,
            "vacancy_loss": vacancy_loss,
            "credit_loss": credit_loss,
            "effective_gross_income": effective_revenue,
            "operating_expenses": operating_expenses,
            "property_tax": property_tax,
            "reserves": assumptions.monthly_reserves,
            "value_add_noi_impact": value_add_noi_impact,
            "noi": noi,
            "renovation_cost": renovation_cost,
            "cash_flow": cash_flow,
        }
        for name, value in monthly.items():
            outputs[f"month:{month}:{name}"] = value
            if name in year_values:
                year_values[name] += value
    for year, values in annual.items():
        for name, value in values.items():
            outputs[f"year:{year}:{name}"] = value
    return CalcResult(
        calc_id=calc_id,
        fn="build_proforma",
        inputs=inputs,
        outputs=outputs,
        code_version=code_version,
    )
