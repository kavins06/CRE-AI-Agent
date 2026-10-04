from decimal import Decimal

import pytest

from cre_brain.domain import CalcResult
from cre_brain.finance.proforma import ProFormaInput, build_proforma
from cre_brain.finance.taxes import TaxAssessment, TaxReassessmentRule, reassess_taxes
from cre_brain.finance.valueadd import ValueAddPlan, build_value_add_schedule

D = Decimal


def _proforma(**changes: object) -> ProFormaInput:
    values: dict[str, object] = {
        "input_id": "proforma-input",
        "base_monthly_revenue": D("1000"),
        "base_monthly_operating_expenses": D("300"),
        "annual_revenue_growth": D("0"),
        "annual_expense_growth": D("0"),
        "vacancy_rate": D("0"),
        "credit_loss_rate": D("0"),
        "monthly_reserves": D("0"),
        "projection_months": 24,
    }
    return ProFormaInput.model_validate(values | changes)


def test_t014_ac2_taxes_retained_assessed_basis_is_not_ratio_adjusted_again() -> None:
    result = reassess_taxes(
        TaxAssessment(
            input_id="assessment",
            sale_price=D("1200000"),
            current_assessed_value=D("500000"),
            current_annual_tax=D("5000"),
        ),
        rule=TaxReassessmentRule(
            input_id="rule",
            assessment_ratio=D("0.5"),
            millage=D("10"),
            phase_in_years=1,
            annual_growth_cap=None,
            full_reassessment=False,
        ),
        projection_years=2,
        calc_id="taxes",
        code_version="v1",
    )
    assert result.outputs["reassessed_value"] == D("500000")
    assert result.outputs["year:1:property_tax"] == D("5000")
    assert result.outputs["year:2:property_tax"] == D("5000")


def test_t014_ac2_taxes_sale_price_is_converted_to_assessed_basis_once() -> None:
    result = reassess_taxes(
        TaxAssessment(
            input_id="assessment",
            sale_price=D("1200000"),
            current_assessed_value=D("500000"),
            current_annual_tax=D("5000"),
        ),
        rule=TaxReassessmentRule(
            input_id="rule",
            assessment_ratio=D("0.5"),
            millage=D("10"),
            phase_in_years=1,
            annual_growth_cap=None,
            full_reassessment=True,
        ),
        projection_years=1,
        calc_id="taxes",
        code_version="v1",
    )
    assert result.outputs["reassessed_value"] == D("600000")
    assert result.outputs["year:1:property_tax"] == D("6000")


def test_t014_ac3_valueadd_offline_units_cannot_earn_grown_rent() -> None:
    schedule = build_value_add_schedule(
        ValueAddPlan(
            input_id="plan",
            total_units=1,
            units_per_month=1,
            start_month=13,
            downtime_months=1,
            cost_per_unit=D("100"),
            current_monthly_rent_per_unit=D("1000"),
            monthly_rent_premium=D("100"),
            ramp_months=1,
        ),
        projection_months=24,
        calc_id="turns",
        code_version="v1",
    )
    result = build_proforma(
        _proforma(annual_revenue_growth=D("0.10")),
        value_add=schedule,
        calc_id="proforma",
        code_version="v1",
    )
    assert result.outputs["month:13:gross_potential_revenue"] == D("0")
    assert result.outputs["month:13:value_add_noi_impact"] == D("-1100")
    assert result.outputs["month:14:gross_potential_revenue"] == D("1200")


@pytest.mark.parametrize("kind", ["tax", "cost"])
def test_t014_ac1_proforma_rejects_negative_schedule_costs(kind: str) -> None:
    schedule = CalcResult(
        calc_id="invalid-schedule",
        fn="reassess_taxes" if kind == "tax" else "build_value_add_schedule",
        inputs={"source": "input"},
        outputs=(
            {"year:1:property_tax": D("-12000")}
            if kind == "tax"
            else {
                "month:1:gross_rent_impact": D("0"),
                "month:1:premium_rent_income": D("0"),
                "month:1:offline_rent_loss": D("0"),
                "month:1:renovation_cost": D("-10000"),
            }
        ),
        code_version="v1",
    )
    with pytest.raises(ValueError, match="nonnegative"):
        build_proforma(
            _proforma(projection_months=1),
            taxes=schedule if kind == "tax" else None,
            value_add=schedule if kind == "cost" else None,
            calc_id="proforma",
            code_version="v1",
        )


def test_t014_ac1_proforma_accepts_declining_growth_and_full_vacancy() -> None:
    result = build_proforma(
        _proforma(annual_revenue_growth=D("-0.05"), annual_expense_growth=D("-0.05")),
        calc_id="decline",
        code_version="v1",
    )
    assert result.outputs["month:13:base_revenue"] == D("950")
    assert result.outputs["month:13:operating_expenses"] == D("285")
    empty = build_proforma(_proforma(vacancy_rate=D("1")), calc_id="empty", code_version="v1")
    assert empty.outputs["year:1:effective_gross_income"] == D("0")
    assert empty.outputs["year:1:cash_flow"] == D("-3600")
