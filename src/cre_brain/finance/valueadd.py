"""Deterministic unit-turn schedules for value-add underwriting."""

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


class ValueAddPlan(DomainModel):
    input_id: Identifier
    total_units: int = Field(strict=True, ge=1)
    units_per_month: int = Field(strict=True, ge=1)
    start_month: int = Field(strict=True, ge=1)
    downtime_months: int = Field(strict=True, ge=0)
    cost_per_unit: NonnegativeDecimal
    current_monthly_rent_per_unit: NonnegativeDecimal
    monthly_rent_premium: NonnegativeDecimal
    ramp_months: int = Field(strict=True, ge=1)


@_calculation
def build_value_add_schedule(
    plan: ValueAddPlan,
    *,
    projection_months: int,
    calc_id: str,
    code_version: str,
) -> CalcResult:
    if isinstance(projection_months, bool) or projection_months < plan.start_month:
        raise ValueError("Projection must include the renovation start month")
    cohorts: list[tuple[int, int]] = []
    remaining = plan.total_units
    turn_month = plan.start_month
    while remaining:
        units = min(remaining, plan.units_per_month)
        cohorts.append((turn_month, units))
        turn_month += 1
        remaining -= units

    outputs: dict[str, Decimal] = {
        "total_units": Decimal(plan.total_units),
        "total_renovation_cost": plan.cost_per_unit * Decimal(plan.total_units),
    }
    renovated = 0
    for month in range(1, projection_months + 1):
        units_turned = sum(units for cohort_month, units in cohorts if cohort_month == month)
        renovated += units_turned
        offline_units = sum(
            units
            for cohort_month, units in cohorts
            if cohort_month <= month < cohort_month + plan.downtime_months
        )
        premium_units = ZERO
        for cohort_month, units in cohorts:
            ready_month = cohort_month + plan.downtime_months
            if month < ready_month:
                continue
            ramp_fraction = min(
                Decimal(month - ready_month + 1) / Decimal(plan.ramp_months), Decimal(1)
            )
            premium_units += Decimal(units) * ramp_fraction
        renovation_cost = Decimal(units_turned) * plan.cost_per_unit
        rent_impact = (
            premium_units * plan.monthly_rent_premium
            - Decimal(offline_units) * plan.current_monthly_rent_per_unit
        )
        prefix = f"month:{month}"
        outputs.update(
            {
                f"{prefix}:units_turned": Decimal(units_turned),
                f"{prefix}:renovated_units": Decimal(renovated),
                f"{prefix}:offline_units": Decimal(offline_units),
                f"{prefix}:premium_units_equivalent": premium_units,
                f"{prefix}:renovation_cost": renovation_cost,
                f"{prefix}:gross_rent_impact": rent_impact,
            }
        )
    return CalcResult(
        calc_id=calc_id,
        fn="build_value_add_schedule",
        inputs={"value_add_plan": plan.input_id},
        outputs=outputs,
        code_version=code_version,
    )
