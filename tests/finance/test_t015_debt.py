from datetime import date
from decimal import ROUND_DOWN, Decimal, getcontext, localcontext

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from cre_brain.finance.debt import (
    DebtSizingInput,
    LoanInput,
    LoanTerms,
    QuoteComparisonInput,
    RefinanceInput,
    amortize_debt,
    compare_debt_quotes,
    refinance_debt,
    size_debt,
)

D = Decimal
META = {"calc_id": "calc", "code_version": "test"}


def terms(**changes):
    return LoanTerms(
        **dict(
            input_id="terms",
            base_rate=D(".06"),
            spread=D("0"),
            term_months=60,
            amortization_months=360,
            io_months=0,
            fee_rate=D("0"),
            fixed_fee=D("0"),
            prepayment_rate=D("0"),
        )
        | changes
    )


def loan(**changes):
    return LoanInput(
        **dict(input_id="loan", principal=D("1000000"), close_date=date(2024, 1, 31)) | changes
    )


def sizing(**changes):
    return DebtSizingInput(
        **dict(
            input_id="sizing",
            property_value=D("2000000"),
            annual_noi=D("150000"),
            max_ltv=D(".75"),
            min_dscr=D("1.25"),
            min_debt_yield=D(".08"),
        )
        | changes
    )


@pytest.mark.parametrize(
    ("changes", "binding"),
    [
        ({"max_ltv": D(".25")}, "ltv_limit"),
        ({"min_dscr": D("3")}, "dscr_limit"),
        ({"min_debt_yield": D(".25")}, "debt_yield_limit"),
    ],
)
def test_t015_ac1_debt_sizing_binding_constraints(changes, binding):
    result = size_debt(sizing(**changes), terms(), **META)
    assert result.outputs["loan_amount"] == result.outputs[binding]
    assert result.outputs["loan_amount"] == min(
        result.outputs[k] for k in ("ltv_limit", "dscr_limit", "debt_yield_limit")
    )
    assert result.inputs == {"sizing": "sizing", "terms": "terms"}


@given(
    principal=st.integers(1, 10000000),
    rate=st.integers(0, 1200),
    term=st.integers(1, 60),
    io=st.integers(0, 60),
)
@settings(max_examples=40, deadline=None)
def test_t015_ac1_debt_balances_conserve_with_explicit_balloon(principal, rate, term, io):
    result = amortize_debt(
        loan(principal=D(principal)),
        terms(base_rate=D(rate) / 10000, term_months=term, io_months=min(io, term)),
        **META,
    )
    o = result.outputs
    assert o[f"month:{term}:ending_balance"] == 0
    assert o["balloon_payoff"] > 0
    for month in range(1, term + 1):
        prefix = f"month:{month}:"
        assert abs(
            o[prefix + "opening_balance"]
            - o[prefix + "scheduled_principal"]
            - o[prefix + "balloon_principal"]
            - o[prefix + "ending_balance"]
        ) < D("1e-18")
    assert abs(o["scheduled_principal"] + o["balloon_payoff"] - D(principal)) < D("1e-18")


def test_t015_ac1_debt_io_zero_rate_and_fully_amortized():
    interest_only = amortize_debt(loan(), terms(io_months=60), **META).outputs
    assert interest_only["month:1:scheduled_payment"] == D("5000")
    assert interest_only["balloon_payoff"] == D("1000000")
    zero = amortize_debt(
        loan(principal=D("1200")),
        terms(base_rate=D("0"), amortization_months=12, term_months=12, io_months=0),
        **META,
    ).outputs
    assert zero["month:1:scheduled_payment"] == 100
    assert zero["balloon_payoff"] == 0
    assert zero["total_interest"] == 0


def test_t015_ac1_debt_dscr_decreases_with_principal_and_context_isolated():
    low = amortize_debt(loan(principal=D("500000"), annual_noi=D("150000")), terms(), **META)
    high = amortize_debt(loan(annual_noi=D("150000")), terms(), **META)
    assert low.outputs["dscr"] > high.outputs["dscr"]
    expected = size_debt(sizing(), terms(), **META)
    with localcontext() as caller:
        caller.prec = 6
        caller.rounding = ROUND_DOWN
        before = caller.copy()
        actual = size_debt(sizing(), terms(), **META)
        assert actual == expected
        assert getcontext().prec == before.prec
        assert getcontext().flags == before.flags
    zero = size_debt(sizing(), terms(base_rate=D("0"), io_months=60), **META)
    assert zero.outputs["dscr_limit_binding_possible"] == 0
    assert zero.outputs["loan_amount"] == min(
        zero.outputs["ltv_limit"], zero.outputs["debt_yield_limit"]
    )


def test_t015_ac2_debt_quote_cost_ranking_fees_spread_prepay_and_ties():
    cheap = terms(input_id="a", base_rate=D(".04"), spread=D(".01"))
    tie = terms(input_id="b", base_rate=D(".05"))
    costly = terms(input_id="c", base_rate=D(".04"), fee_rate=D(".05"), prepayment_rate=D(".1"))
    horizon = QuoteComparisonInput(input_id="comparison", payoff_month=12)
    result = compare_debt_quotes(loan(), [costly, tie, cheap], comparison=horizon, **META)
    o = result.outputs
    assert o["quote:a:rank"] == 1
    assert o["quote:b:rank"] == 2
    assert o["quote:a:effective_annual_cost"] == o["quote:b:effective_annual_cost"]
    assert o["quote:c:rank"] == 3
    assert o["quote:c:fees"] == D("50000")
    assert o["quote:c:prepayment_fee"] > 0
    assert result.inputs == {
        "loan": "loan",
        "comparison": "comparison",
        "quote:a": "a",
        "quote:b": "b",
        "quote:c": "c",
    }
    other = compare_debt_quotes(loan(), [cheap, tie, costly], comparison=horizon, **META)
    assert other == result


def test_t015_ac2_debt_quote_io_amort_and_maturity_no_prepay():
    result = compare_debt_quotes(
        loan(),
        [terms(input_id="io", io_months=60), terms(input_id="amort")],
        **META,
    )
    assert abs(result.outputs["quote:io:effective_annual_cost"] - (D("1.005") ** 12 - 1)) < D(
        "1e-20"
    )
    assert result.outputs["quote:io:balloon_payoff"] == D("1000000")
    assert result.outputs["quote:amort:balloon_payoff"] < D("1000000")
    assert result.outputs["quote:io:prepayment_fee"] == 0
    with pytest.raises(ValueError, match="unique"):
        compare_debt_quotes(loan(), [terms(), terms()], **META)
    with pytest.raises(ValueError, match="proceeds"):
        compare_debt_quotes(loan(), [terms(fixed_fee=D("1000000"))], **META)


@pytest.mark.parametrize("month", [12, 60])
def test_t015_ac3_debt_refinance_dated_payoff_and_sources_uses(month):
    old = terms(io_months=60, prepayment_rate=D(".02"))
    new = terms(input_id="new", fee_rate=D(".01"))
    refi = RefinanceInput(
        input_id="refi",
        refinance_date=date(2025 if month == 12 else 2029, 1, 31),
        new_principal=D("1200000"),
    )
    result = refinance_debt(loan(), old, refi, new, **META)
    o = result.outputs
    assert o["old_balance_payoff"] == D("1000000")
    assert o["old_prepayment_fee"] == (D("20000") if month == 12 else 0)
    assert o["new_fees"] == D("12000")
    assert (
        o["cash_out"] + o["old_balance_payoff"] + o["old_prepayment_fee"] + o["new_fees"]
        == o["new_principal"]
    )
    assert (
        o["new:month:1:payment_date_ordinal"]
        == date(2025 if month == 12 else 2029, 2, 28).toordinal()
    )
    assert result.inputs == {
        "loan": "loan",
        "old_terms": "terms",
        "refinance": "refi",
        "new_terms": "new",
    }


def test_t015_ac3_debt_refinance_rejects_unsupported_dates_and_bad_inputs():
    with pytest.raises(ValueError, match="payment date"):
        refinance_debt(
            loan(),
            terms(),
            RefinanceInput(input_id="refi", refinance_date=date(2025, 1, 30), new_principal=D("1")),
            terms(input_id="new"),
            **META,
        )
    with pytest.raises(ValidationError):
        terms(io_months=61)
    with pytest.raises(ValidationError):
        terms(base_rate=0.06)
    with pytest.raises(ValidationError):
        loan(principal=D("NaN"))
