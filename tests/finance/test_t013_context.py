from datetime import date
from decimal import (
    ROUND_DOWN,
    ROUND_UP,
    Context,
    Decimal,
    DefaultContext,
    Inexact,
    Overflow,
    Rounded,
    localcontext,
)

import pytest

from cre_brain.finance import (
    ChartOfAccounts,
    MissingMonthRule,
    RentRollUnit,
    T12Entry,
    normalize_rent_roll,
    normalize_t12,
)


def results():
    units = [
        RentRollUnit(
            unit_id=f"u-{index}",
            input_id=f"fact-{index}",
            unit_type="studio",
            market_rent=Decimal("1000.01"),
            contract_rent=Decimal("900.01") if index < 2 else Decimal(0),
            occupied=index < 2,
        )
        for index in range(3)
    ]
    rentroll = normalize_rent_roll(units, calc_id="rentroll", code_version="v1")
    t12 = normalize_t12(
        [
            T12Entry(
                input_id=f"ledger-{month}",
                month=date(2025, month, 1),
                account="rent",
                amount=Decimal("1234.56"),
            )
            for month in range(1, 8)
        ],
        chart=ChartOfAccounts(input_id="chart", mapping={"rent": "income"}),
        missing_month_rule=MissingMonthRule(input_id="policy", strategy="annualize_observed"),
        calc_id="t12",
        code_version="v1",
    )
    return rentroll, t12


@pytest.mark.parametrize(
    "caller",
    [
        Context(prec=8, rounding=ROUND_DOWN),
        Context(prec=36, rounding=ROUND_UP),
        Context(prec=8, traps=[Inexact, Rounded]),
        Context(prec=28, Emin=-2, Emax=2, traps=[Overflow]),
    ],
)
def test_t013_ac3_rentroll_and_t12_ignore_and_preserve_caller_decimal_context(caller) -> None:
    with localcontext(Context(prec=28)):
        expected = results()
    assert expected[0].outputs["physical_occupancy"] == Decimal("0.6666666666666666666666666667")
    assert expected[1].outputs["annualization_factor"] == Decimal("1.714285714285714285714285714")
    with localcontext(caller) as active:
        before = str(active)
        assert results() == expected
        assert str(active) == before


def test_t013_ac3_rentroll_restores_caller_context_after_validation_failure() -> None:
    with localcontext(Context(prec=8, rounding=ROUND_UP)) as active:
        before = str(active)
        with pytest.raises(ValueError, match="at least one"):
            normalize_rent_roll([], calc_id="empty", code_version="v1")
        assert str(active) == before


def test_t013_ac3_rentroll_and_t12_ignore_mutated_default_decimal_context(monkeypatch) -> None:
    expected = results()
    for field, value in {
        "prec": 8,
        "rounding": ROUND_DOWN,
        "Emin": -2,
        "Emax": 2,
        "capitals": 0,
        "clamp": 1,
    }.items():
        monkeypatch.setattr(DefaultContext, field, value)
    for signal in DefaultContext.traps:
        monkeypatch.setitem(DefaultContext.traps, signal, True)
    assert results() == expected
