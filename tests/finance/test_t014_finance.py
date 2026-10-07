from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from cre_brain.finance.proforma import ProFormaInput, build_proforma
from cre_brain.finance.taxes import TaxAssessment, TaxReassessmentRule, reassess_taxes
from cre_brain.finance.valueadd import ValueAddPlan, build_value_add_schedule

D = Decimal


def test_t014_ac1_proforma_monthly_and_annual_cash_flow_includes_losses_and_reserves() -> None:
    result = build_proforma(
        ProFormaInput(
            input_id="proforma-input",
            base_monthly_revenue=D("10000"),
            base_monthly_operating_expenses=D("3000"),
            annual_revenue_growth=D("0.10"),
            annual_expense_growth=D("0.05"),
            vacancy_rate=D("0.10"),
            credit_loss_rate=D("0.05"),
            monthly_reserves=D("500"),
            projection_months=24,
        ),
        calc_id="proforma-calc",
        code_version="v1",
    )

    assert result.outputs["month:1:vacancy_loss"] == D("1000")
    assert result.outputs["month:1:credit_loss"] == D("450")
    assert result.outputs["month:1:noi"] == D("5550")
    assert result.outputs["month:13:gross_potential_revenue"] == D("11000.00")
    assert result.outputs["month:13:noi"] == D("6255.0000")
    assert result.outputs["year:1:cash_flow"] == D("60600")
    assert result.outputs["year:2:cash_flow"] == D("69060.0000")
    assert result.inputs == {"proforma": "proforma-input"}


def test_t014_ac1_proforma_rejects_binary_float_finance_inputs() -> None:
    with pytest.raises(ValidationError):
        ProFormaInput(
            input_id="proforma-input",
            base_monthly_revenue=0.1,
            base_monthly_operating_expenses=D("0"),
            annual_revenue_growth=D("0"),
            annual_expense_growth=D("0"),
            vacancy_rate=D("0"),
            credit_loss_rate=D("0"),
            monthly_reserves=D("0"),
            projection_months=12,
        )


@given(
    assessed=st.integers(min_value=1, max_value=10_000_000),
    premium=st.integers(min_value=1, max_value=10_000_000),
    current_tax=st.integers(min_value=0, max_value=1_000_000),
)
def test_t014_ac2_taxes_full_reassessment_never_reduces_tax_on_value_increase(
    assessed: int, premium: int, current_tax: int
) -> None:
    result = reassess_taxes(
        TaxAssessment(
            input_id="tax-assessment",
            sale_price=D(assessed + premium),
            current_assessed_value=D(assessed),
            current_annual_tax=D(current_tax),
        ),
        rule=TaxReassessmentRule(
            input_id="jurisdiction-rule",
            assessment_ratio=D("1"),
            millage=D("10"),
            phase_in_years=1,
            annual_growth_cap=None,
            full_reassessment=True,
        ),
        projection_years=1,
        calc_id="tax-calc",
        code_version="v1",
    )

    assert result.outputs["year:1:property_tax"] >= D(current_tax)


def test_t014_ac2_taxes_phase_in_and_cap_are_explicit_and_provenanced() -> None:
    result = reassess_taxes(
        TaxAssessment(
            input_id="tax-assessment",
            sale_price=D("2000000"),
            current_assessed_value=D("1000000"),
            current_annual_tax=D("10000"),
        ),
        rule=TaxReassessmentRule(
            input_id="jurisdiction-rule",
            assessment_ratio=D("1"),
            millage=D("20"),
            phase_in_years=2,
            annual_growth_cap=D("0.25"),
            full_reassessment=True,
        ),
        projection_years=3,
        calc_id="tax-calc",
        code_version="v1",
    )

    assert result.outputs["target_annual_tax"] == D("40000")
    assert result.outputs["year:1:property_tax"] == D("12500.00")
    assert result.outputs["year:2:property_tax"] == D("15625.0000")
    assert result.outputs["year:3:property_tax"] == D("19531.250000")
    assert result.inputs == {
        "tax_assessment": "tax-assessment",
        "jurisdiction_rule": "jurisdiction-rule",
    }


def test_t014_ac3_valueadd_unit_turn_schedule_feeds_proforma_noi_and_cash_flow() -> None:
    value_add = build_value_add_schedule(
        ValueAddPlan(
            input_id="renovation-plan",
            total_units=4,
            units_per_month=2,
            start_month=1,
            downtime_months=1,
            cost_per_unit=D("10000"),
            current_monthly_rent_per_unit=D("1000"),
            monthly_rent_premium=D("100"),
            ramp_months=2,
        ),
        projection_months=4,
        calc_id="valueadd-calc",
        code_version="v1",
    )
    assert value_add.outputs["month:1:units_turned"] == D("2")
    assert value_add.outputs["month:2:renovation_cost"] == D("20000")
    assert value_add.outputs["month:2:gross_rent_impact"] == D("-1900.0")
    assert value_add.outputs["month:4:gross_rent_impact"] == D("400")

    proforma = build_proforma(
        ProFormaInput(
            input_id="proforma-input",
            base_monthly_revenue=D("10000"),
            base_monthly_operating_expenses=D("2000"),
            annual_revenue_growth=D("0"),
            annual_expense_growth=D("0"),
            vacancy_rate=D("0"),
            credit_loss_rate=D("0"),
            monthly_reserves=D("0"),
            projection_months=4,
        ),
        value_add=value_add,
        calc_id="proforma-calc",
        code_version="v1",
    )
    assert proforma.outputs["month:3:value_add_noi_impact"] == D("300")
    assert proforma.outputs["month:3:noi"] == D("8300")
    assert proforma.outputs["month:1:cash_flow"] == D("-14000")
    assert proforma.inputs == {
        "proforma": "proforma-input",
        "value_add_schedule": "valueadd-calc",
    }


def test_t014_ac3_valueadd_rejects_schedule_shorter_than_plan_start() -> None:
    plan = ValueAddPlan(
        input_id="renovation-plan",
        total_units=1,
        units_per_month=1,
        start_month=2,
        downtime_months=0,
        cost_per_unit=D("1"),
        current_monthly_rent_per_unit=D("1"),
        monthly_rent_premium=D("1"),
        ramp_months=1,
    )
    with pytest.raises(ValueError, match="start month"):
        build_value_add_schedule(
            plan, projection_months=1, calc_id="valueadd-calc", code_version="v1"
        )
