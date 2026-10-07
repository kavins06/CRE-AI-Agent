from datetime import date, timedelta
from decimal import ROUND_UP, Decimal, localcontext

import pytest

from cre_brain.finance.returns import ReturnsInput, calculate_returns

D = Decimal
META = {"calc_id": "certified-returns", "code_version": "test"}


def source_for_roots(rates, scale, day_step):
    with localcontext() as ctx:
        ctx.prec = 240
        coefficients = [D(1)]
        for rate in rates:
            updated = [D(0)] * (len(coefficients) + 1)
            for index, coefficient in enumerate(coefficients):
                updated[index] += coefficient
                updated[index + 1] -= (1 + rate) * coefficient
            coefficients = updated
        amounts = tuple(coefficient * D(scale) for coefficient in coefficients)
    start = date(2024, 1, 1)
    return ReturnsInput(
        input_id="exact-close-flows",
        cash_flows=amounts,
        dates=(
            tuple(start + timedelta(days=day_step * i) for i in range(len(amounts)))
            if day_step is not None
            else None
        ),
        finance_rate=D(".1"),
        reinvest_rate=D(".1"),
    )


@pytest.mark.parametrize("gap", ["1e-35", "1e-40", "1e-100"])
@pytest.mark.parametrize("scale", ["1", "1e-100", "1e100"])
@pytest.mark.parametrize("day_step", [None, 365])
def test_t016_ac1_returns_certifies_two_representable_near_zero_roots(gap, scale, day_step):
    source = source_for_roots([D(0), D(gap)], scale, day_step)
    result = calculate_returns(source, **META)
    outputs = result.outputs
    assert outputs["root_count"] == 2
    assert outputs["ambiguous"] == 1
    assert outputs["unique"] == outputs["undefined"] == 0
    assert "irr" not in outputs and "xirr" not in outputs
    assert outputs["reported_return"] == outputs["mirr"]
    assert outputs["root:0"] == 0
    with localcontext() as ctx:
        ctx.prec = 240
        assert abs(outputs["root:1"] - D(gap)) <= D(gap) * D("1e-26")
        for rate in (D(0), D(gap)):
            residual = sum(
                (amount / (1 + rate) ** i for i, amount in enumerate(source.cash_flows)),
                D(0),
            )
            assert abs(residual) <= abs(D(scale)) * D("1e-220")


@pytest.mark.parametrize("gap", ["1e-35", "1e-40", "1e-100"])
@pytest.mark.parametrize("day_step", [None, 365])
def test_t016_ac1_returns_unrepresentable_nonzero_close_pair_fails_closed(gap, day_step):
    with localcontext() as ctx:
        ctx.prec = 240
        rates = [D(".1"), D(".1") + D(gap)]
    source = source_for_roots(rates, "1", day_step)
    with pytest.raises(ValueError, match="28 output digits"):
        calculate_returns(source, **META)


@pytest.mark.parametrize("rates", [[D(0), D(0)], [D(".1"), D(".1")], [D(0), D(0), D("1e-40")]])
def test_t016_ac1_returns_certified_tangencies_count_distinct_roots(rates):
    source = source_for_roots(rates, "1", None)
    result = calculate_returns(source, **META)
    expected = sorted(set(rates))
    assert result.outputs["root_count"] == len(expected)
    assert result.outputs["unique"] == (len(expected) == 1)
    assert result.outputs["ambiguous"] == (len(expected) > 1)
    assert [result.outputs[f"root:{i}"] for i in range(len(expected))] == pytest.approx(
        expected, abs=D("1e-65")
    )


def test_t016_ac1_returns_irregular_reduced_lattice_certifies_tangency():
    start = date(2024, 1, 1)
    source = ReturnsInput(
        input_id="irregular-tangent",
        cash_flows=(D(-3), D(5), D(-2)),
        dates=(start, start + timedelta(days=146), start + timedelta(days=365)),
        finance_rate=D(".1"),
        reinvest_rate=D(".1"),
    )
    # -3 + 5*q**(2/5) - 2*q has an exact double root at q=1.
    # The bounded exact-polynomial path can certify it after reducing the day lattice.
    result = calculate_returns(source, **META)
    assert result.outputs["root_count"] == result.outputs["unique"] == 1
    assert result.outputs["xirr"] == 0


def test_t016_ac1_returns_uncertified_large_lattice_tangency_fails_closed():
    start = date(2024, 1, 1)
    source = ReturnsInput(
        input_id="large-lattice-tangent",
        cash_flows=(D(-2000), D(2001), D(-1)),
        dates=(start, start + timedelta(days=1), start + timedelta(days=2001)),
        finance_rate=D(".1"),
        reinvest_rate=D(".1"),
    )
    with pytest.raises(ValueError, match="certif"):
        calculate_returns(source, **META)


@pytest.mark.parametrize("gap", ["1e-35", "1e-100"])
@pytest.mark.parametrize("direction", [-1, 1])
def test_t016_ac1_returns_nearly_tangent_nonzero_stationary_point_is_not_a_root(gap, direction):
    with localcontext() as ctx:
        ctx.prec = 240
        source = ReturnsInput(
            input_id="near-tangent",
            cash_flows=(D(-1), D(2), D(-1) + direction * D(gap)),
            finance_rate=D(".1"),
            reinvest_rate=D(".1"),
        )
        expected = D(gap).sqrt()
    result = calculate_returns(source, **META)
    outputs = result.outputs
    assert outputs["unique"] == 0
    if direction < 0:
        assert outputs["root_count"] == outputs["ambiguous"] == 0
        assert outputs["undefined"] == 1
        assert "reported_return" not in outputs
    else:
        assert outputs["root_count"] == 2
        assert outputs["ambiguous"] == 1
        assert outputs["root:0"] == pytest.approx(-expected, rel=D("1e-26"), abs=D(0))
        assert outputs["root:1"] == pytest.approx(expected, rel=D("1e-26"), abs=D(0))


@pytest.mark.parametrize("gap", ["1e-35", "1e-100"])
@pytest.mark.parametrize("day_step", [1, 182, 730])
def test_t016_ac1_returns_close_dated_roots_convert_actual_day_lattice(gap, day_step):
    source = source_for_roots([D(0), D(gap)], "1", day_step)
    with localcontext() as ctx:
        ctx.prec = 240
        expected = (1 + D(gap)) ** (D(365) / day_step) - 1
    result = calculate_returns(source, **META)
    assert result.outputs["root_count"] == 2
    assert result.outputs["ambiguous"] == 1
    assert result.outputs["root:0"] == 0
    assert result.outputs["root:1"] == pytest.approx(expected, rel=D("1e-26"), abs=D(0))


def test_t016_ac1_returns_exact_open_boundaries_removed_without_losing_interior_roots():
    source = source_for_roots([D("-.99"), D("-.99"), D(10), D(0), D(".1")], "1", None)
    result = calculate_returns(source, **META)
    assert result.outputs["root_count"] == 2
    assert result.outputs["ambiguous"] == 1
    assert result.outputs["root:0"] == 0
    assert result.outputs["root:1"] == pytest.approx(D(".1"), abs=D("1e-27"))


def test_t016_ac3_returns_close_root_certification_preserves_caller_and_json():
    source = source_for_roots([D(0), D("1e-100")], "1e100", 365)
    expected = calculate_returns(source, **META)
    with localcontext() as caller:
        caller.prec = 5
        caller.rounding = ROUND_UP
        before = caller.copy()
        result = calculate_returns(source, **META)
        assert result == expected
        assert caller.prec == before.prec
        assert caller.rounding == before.rounding
        assert caller.flags == before.flags
    assert type(expected).model_validate_json(expected.model_dump_json()) == expected
