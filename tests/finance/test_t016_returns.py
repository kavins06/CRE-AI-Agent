from datetime import date, timedelta
from decimal import ROUND_UP, Decimal, getcontext, localcontext

import pytest
import pyxirr
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from cre_brain.finance.returns import (
    CashOnCashInput,
    NPVInput,
    ReturnsInput,
    calculate_returns,
    cash_on_cash,
    excel_npv,
)

D = Decimal
META = {"calc_id": "return-calc", "code_version": "test"}


def flows(values, **changes):
    return ReturnsInput(
        input_id="cashflows",
        cash_flows=tuple(D(str(value)) for value in values),
        finance_rate=D(".1"),
        reinvest_rate=D(".1"),
        **changes,
    )


def roots(result):
    return [result.outputs[f"root:{i}"] for i in range(int(result.outputs["root_count"]))]


def periodic_npv(values, rate):
    return sum((value / (1 + rate) ** i for i, value in enumerate(values)), D(0))


def test_t016_ac1_returns_multiple_roots_and_mirr_fallback():
    source = flows([-100, 230, -132])
    result = calculate_returns(source, **META)
    o = result.outputs
    assert o["ambiguous"] == 1
    assert o["undefined"] == o["unique"] == 0
    assert "irr" not in o
    assert roots(result) == pytest.approx([D(".1"), D(".2")], abs=D("1e-24"))
    expected_mirr = (D(253) / (D(100) + D(132) / D("1.1") ** 2)).sqrt() - 1
    assert abs(o["mirr"] - expected_mirr) < D("1e-24")
    assert o["reported_return"] == o["mirr"]
    assert result.inputs == {"cash_flows": "cashflows"}
    assert float(o["mirr"]) == pytest.approx(pyxirr.mirr([-100, 230, -132], 0.1, 0.1))


@pytest.mark.parametrize("values", [[100, 20, 50], [-100, -1], [-100, 50, -100]])
def test_t016_ac1_returns_undefined_never_invents_irr(values):
    result = calculate_returns(flows(values), **META)
    assert result.outputs["undefined"] == 1
    assert result.outputs["root_count"] == 0
    assert "irr" not in result.outputs
    assert "reported_return" not in result.outputs


@pytest.mark.parametrize("rate", ["-.99", "10", "10.0000001", "-.999"])
def test_t016_ac1_returns_open_domain_excludes_boundaries_and_outside(rate):
    source = flows([-1, 1 + D(rate)])
    result = calculate_returns(source, **META)
    assert result.outputs["undefined"] == 1
    assert roots(result) == []


@pytest.mark.parametrize("rate", ["-.9899999", "9.9999999", "0"])
def test_t016_ac1_returns_near_domain_edges_and_zero(rate):
    source = flows([-1, 1 + D(rate)])
    result = calculate_returns(source, **META)
    assert result.outputs["unique"] == 1
    assert abs(result.outputs["irr"] - D(rate)) < D("1e-24")


@pytest.mark.parametrize("scale", ["1e-200", "1", "1e200"])
@pytest.mark.parametrize("gap", ["0", ".00000001", ".000000000001"])
def test_t016_ac1_returns_close_and_tangent_roots_are_not_grid_dependent(scale, gap):
    a, b = D("1.1"), D("1.1") + D(gap)
    source = flows([-D(scale), (a + b) * D(scale), -a * b * D(scale)])
    result = calculate_returns(source, **META)
    expected = [a - 1] if gap == "0" else [a - 1, b - 1]
    assert roots(result) == pytest.approx(expected, abs=D("1e-24"))
    assert result.outputs["unique"] == (gap == "0")
    assert result.outputs["ambiguous"] == (gap != "0")


def test_t016_ac1_returns_three_roots_and_identically_zero_not_unique():
    result = calculate_returns(flows([-1, D("3.6"), D("-4.31"), D("1.716")]), **META)
    assert roots(result) == pytest.approx([D(".1"), D(".2"), D(".3")], abs=D("1e-24"))
    zero = calculate_returns(flows([0, 0, 0]), **META)
    assert zero.outputs["ambiguous"] == 1
    assert zero.outputs["infinitely_many_roots"] == 1
    assert zero.outputs["unique"] == 0
    assert "reported_return" not in zero.outputs


def test_t016_ac1_returns_dated_irregular_and_duplicate_dates():
    dates = (date(2024, 1, 1), date(2024, 1, 1), date(2025, 7, 1))
    source = flows([-60, -40, 120], dates=dates)
    result = calculate_returns(source, **META)
    rate = result.outputs["xirr"]
    with localcontext() as ctx:
        ctx.prec = 60
        expected = D("1.2") ** (D(365) / D((dates[-1] - dates[0]).days)) - 1
    assert abs(rate - expected) < D("1e-24")
    assert abs(pyxirr.xnpv(float(rate), dates, [-60, -40, 120])) < 1e-9
    unordered = flows([120, -40, -60], dates=(dates[2], dates[1], dates[0]))
    assert calculate_returns(unordered, **META).outputs == result.outputs
    cancellation = calculate_returns(flows([-100, 100], dates=(dates[0], dates[0])), **META)
    assert cancellation.outputs["infinitely_many_roots"] == 1
    nonzero = calculate_returns(flows([-100, 110], dates=(dates[0], dates[0])), **META)
    assert nonzero.outputs["undefined"] == 1


def test_t016_ac1_returns_dated_multiple_roots_and_tangent():
    start = date(2024, 1, 1)
    dates = tuple(start + timedelta(days=365 * i) for i in range(3))
    for values, expected in [
        ([-100, 230, -132], [D(".1"), D(".2")]),
        ([-100, 220, -121], [D(".1")]),
    ]:
        result = calculate_returns(flows(values, dates=dates), **META)
        assert roots(result) == pytest.approx(expected, abs=D("1e-24"))
        for root in roots(result):
            assert abs(pyxirr.xnpv(float(root), dates, values)) < 1e-8


def test_t016_ac1_returns_dated_mirr_uses_actual_time():
    source = flows(
        [-100, 50, -100],
        dates=(date(2024, 1, 1), date(2024, 7, 1), date(2026, 1, 1)),
    )
    result = calculate_returns(source, **META)
    horizon = D(731) / 365
    intermediate = D(182) / 365
    expected = (
        (D(50) * D("1.1") ** (horizon - intermediate)) / (D(100) + D(100) / D("1.1") ** horizon)
    ) ** (1 / horizon) - 1
    assert abs(result.outputs["mirr"] - expected) < D("1e-24")


@pytest.mark.parametrize(
    "changes",
    [
        {"dates": (date(2024, 1, 1),)},
        {"dates": ("2024-02-30", "2025-01-01")},
        {"cash_flows": (D("-100"), float("inf"))},
        {"cash_flows": (D("-100"), 110.0)},
        {"cash_flows": (D("NaN"), D("100"))},
        {"finance_rate": D("-1")},
    ],
)
def test_t016_ac1_returns_invalid_inputs_rejected(changes):
    arguments = (
        dict(
            input_id="invalid",
            cash_flows=(D("-100"), D("110")),
            finance_rate=D(".1"),
            reinvest_rate=D(".1"),
        )
        | changes
    )
    with pytest.raises(ValidationError):
        ReturnsInput(**arguments)


def test_t016_ac2_returns_excel_npv_period_one_timing():
    source = NPVInput(input_id="npv", cash_flows=(D("-100"), D("121")), discount_rate=D(".1"))
    result = excel_npv(source, **META)
    assert abs(result.outputs["npv"] - D(10) / D("1.1")) < D("1e-24")
    assert result.inputs == {"cash_flows": "npv"}
    assert float(result.outputs["npv"]) == pytest.approx(
        pyxirr.npv(0.1, [-100, 121], start_from_zero=False)
    )
    ms_example = excel_npv(
        NPVInput(
            input_id="excel-example",
            discount_rate=D(".1"),
            cash_flows=(D("-10000"), D("3000"), D("4200"), D("6800")),
        ),
        **META,
    )
    assert round(ms_example.outputs["npv"], 2) == D("1188.44")
    huge = excel_npv(
        NPVInput(input_id="huge", discount_rate=D("1e999"), cash_flows=(D("1"),)),
        **META,
    )
    assert huge.outputs["pyxirr_consistent"] == 0
    assert huge.outputs["npv"] == D(1) / (D(1) + D("1e999"))


@given(initial=st.integers(1, 1000000), basis_points=st.integers(-9800, 99000))
@settings(max_examples=40, deadline=None)
def test_t016_ac3_returns_reported_irr_residual_property(initial, basis_points):
    rate = D(basis_points) / 10000
    source = flows([-initial, D(initial) * (1 + rate)])
    result = calculate_returns(source, **META)
    assert result.outputs["unique"] == 1
    for root in roots(result):
        assert abs(periodic_npv(source.cash_flows, root)) / D(initial) < D("1e-24")
    assert result.outputs["equity_multiple"] == 1 + rate


@given(growth_factors=st.lists(st.integers(200, 100000), min_size=1, max_size=4, unique=True))
@settings(max_examples=40, deadline=None)
def test_t016_ac3_returns_isolates_every_constructed_periodic_root(growth_factors):
    expected_growth = sorted(D(value) / 10000 for value in growth_factors)
    coefficients = [D(1)]
    for factor in expected_growth:
        next_coefficients = [D(0)] * (len(coefficients) + 1)
        for index, coefficient in enumerate(coefficients):
            next_coefficients[index] += coefficient
            next_coefficients[index + 1] -= factor * coefficient
        coefficients = next_coefficients
    result = calculate_returns(flows(coefficients), **META)
    assert roots(result) == pytest.approx(
        [factor - 1 for factor in expected_growth], abs=D("1e-24")
    )
    assert result.outputs["max_relative_npv_residual"] < D("1e-24")


def test_t016_ac3_returns_equity_multiple_all_contributions_and_cash_on_cash():
    result = calculate_returns(flows([-100, -50, 30, 150]), **META)
    assert result.outputs["equity_multiple"] == D("1.2")
    assert result.outputs["total_contributions"] == 150
    assert result.outputs["total_distributions"] == 180
    metric = cash_on_cash(
        CashOnCashInput(
            input_id="cash-on-cash",
            annual_operating_cash_flow=D("-5"),
            invested_equity=D("100"),
        ),
        **META,
    )
    assert metric.outputs["cash_on_cash"] == D("-.05")
    assert metric.inputs == {"cash_on_cash": "cash-on-cash"}
    all_positive = calculate_returns(flows([10, 20]), **META)
    assert all_positive.outputs["equity_multiple_defined"] == 0
    assert "equity_multiple" not in all_positive.outputs


def test_t016_ac3_returns_caller_context_independent_and_json_round_trip():
    source = flows([-100, 230, -132])
    expected = calculate_returns(source, **META)
    with localcontext() as caller:
        caller.prec = 5
        caller.rounding = ROUND_UP
        before = caller.copy()
        result = calculate_returns(source, **META)
        assert result == expected
        assert getcontext().prec == before.prec
        assert getcontext().rounding == before.rounding
        assert getcontext().flags == before.flags
    assert type(result).model_validate_json(result.model_dump_json()) == result
