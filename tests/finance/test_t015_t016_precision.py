from datetime import date
from decimal import ROUND_DOWN, Decimal, getcontext, localcontext
from fractions import Fraction
from itertools import permutations

import pytest
import pyxirr

from cre_brain.domain import CalcResult
from cre_brain.finance.debt import LoanInput, LoanTerms, compare_debt_quotes
from cre_brain.finance.returns import NPVInput, excel_npv

D = Decimal
META = {"calc_id": "precision", "code_version": "test"}


def quote(identifier, rate="0", fee="0"):
    return LoanTerms(
        input_id=identifier,
        base_rate=D(rate),
        spread=D(0),
        term_months=12,
        amortization_months=12,
        io_months=12,
        fee_rate=D(0),
        fixed_fee=D(fee),
        prepayment_rate=D(0),
    )


def loan(principal="1200"):
    return LoanInput(input_id="loan", principal=D(principal), close_date=date(2024, 1, 1))


@pytest.mark.parametrize("rate", ["1e-26", "1e-80", "1e-180"])
@pytest.mark.parametrize("principal", ["1200", "1e6"])
def test_t015_ac2_debt_tiny_positive_cost_never_ranks_as_free(rate, principal):
    source = loan(principal)
    quotes = [quote("a-positive", rate), quote("z-free")]
    with localcontext() as oracle:
        oracle.prec = 256
        expected = (1 + D(rate) / 12) ** 12 - 1
    result = compare_debt_quotes(source, quotes, **META)
    cost = result.outputs["quote:a-positive:effective_annual_cost"]
    assert cost > 0
    assert abs(cost - expected) / expected < D("1e-24")
    assert result.outputs["quote:z-free:effective_annual_cost"] == 0
    assert result.outputs["quote:z-free:rank"] == 1
    assert result.outputs["quote:a-positive:rank"] == 2
    assert compare_debt_quotes(source, list(reversed(quotes)), **META) == result


@pytest.mark.parametrize("fee", ["1e-26", "1e-80", "1e-180"])
def test_t015_ac2_debt_tiny_fixed_fee_is_in_effective_cost(fee):
    source = loan()
    with localcontext() as oracle:
        oracle.prec = 256
        expected = source.principal / (source.principal - D(fee)) - 1
    result = compare_debt_quotes(source, [quote("a-fee", fee=fee), quote("z-free")], **META)
    cost = result.outputs["quote:a-fee:effective_annual_cost"]
    assert cost > 0
    assert abs(cost - expected) / expected < D("1e-24")
    assert result.outputs["quote:z-free:rank"] == 1
    assert result.outputs["quote:a-fee:fees"] == D(fee)


def test_t015_ac2_debt_unsupported_quote_precision_fails_closed():
    with pytest.raises(ValueError, match="precision"):
        compare_debt_quotes(loan(), [quote("tiny", "1e-300")], **META)


@pytest.mark.parametrize("magnitude", ["1e80", "1e100", "1e200"])
def test_t016_ac2_returns_exact_cancellation_preserves_small_npv(magnitude):
    values = [D(magnitude).copy_negate(), D(1), D(magnitude)]
    for ordered in permutations(values):
        result = excel_npv(
            NPVInput(input_id="cancellation", cash_flows=ordered, discount_rate=D(0)), **META
        )
        assert result.outputs["npv"] == 1
        binary = pyxirr.npv(
            0.0, [float(amount / D(magnitude)) for amount in ordered], start_from_zero=False
        )
        agrees = abs(Fraction(binary) * Fraction(D(magnitude)) - 1) <= Fraction(1, 10**9)
        assert result.outputs["pyxirr_consistent"] == D(agrees)


@pytest.mark.parametrize("magnitude", ["1e80", "1e100", "1e200"])
def test_t016_ac2_returns_discounted_cancellation_uses_exact_rational_oracle(magnitude):
    # First and third discounted flows cancel at the Excel period-one convention.
    large = D(magnitude)
    values = (large.copy_negate(), D(1), D("1.21" + magnitude[1:]))
    discount = Fraction(10, 11)
    exact = sum(
        (Fraction(amount) * discount**period for period, amount in enumerate(values, 1)),
        Fraction(0),
    )
    expected = D(exact.numerator) / D(exact.denominator)
    result = excel_npv(
        NPVInput(input_id="discounted", cash_flows=values, discount_rate=D(".1")), **META
    )
    assert result.outputs["npv"] == expected
    assert result.outputs["pyxirr_consistent"] == 0


def test_t016_ac2_returns_npv_and_debt_are_caller_context_independent():
    source = NPVInput(
        input_id="cancel", cash_flows=(D("-1e200"), D(1), D("1e200")), discount_rate=D(0)
    )
    quotes = [quote("positive", "1e-80"), quote("free")]
    expected_npv = excel_npv(source, **META)
    expected_cost = compare_debt_quotes(loan(), quotes, **META)
    with localcontext() as caller:
        caller.prec = 5
        caller.rounding = ROUND_DOWN
        before = caller.copy()
        assert excel_npv(source, **META) == expected_npv
        assert compare_debt_quotes(loan(), quotes, **META) == expected_cost
        assert getcontext().prec == before.prec
        assert getcontext().rounding == before.rounding
        assert getcontext().flags == before.flags
    assert expected_npv.outputs["npv"] == 1
    assert CalcResult.model_validate_json(expected_npv.model_dump_json()) == expected_npv
    assert CalcResult.model_validate_json(expected_cost.model_dump_json()) == expected_cost


@pytest.mark.parametrize(
    ("values", "rate"),
    [((D("1e5000"),), D(0)), ((D(1),), D("1e-5000")), ((D(1),) * 600, D("1e999"))],
)
def test_t016_ac2_returns_npv_exact_complexity_budget_fails_closed(values, rate):
    with pytest.raises(ValueError, match="complexity"):
        excel_npv(NPVInput(input_id="budget", cash_flows=values, discount_rate=rate), **META)


def test_t016_ac2_returns_npv_supports_long_conventional_decimal_rate():
    source = NPVInput(input_id="long", cash_flows=(D(1),) * 600, discount_rate=D(".123456789"))
    with localcontext() as oracle:
        oracle.prec = 100
        discount = 1 / (1 + source.discount_rate)
        expected = (1 - discount**600) / source.discount_rate
    assert abs(excel_npv(source, **META).outputs["npv"] - expected) < D("1e-26")
