from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cre_brain.finance.t12 import ChartOfAccounts, MissingMonthRule, T12Entry, normalize_t12


def entry(index: int, month: int, account: str, amount: str, *, one_time: bool = False) -> T12Entry:
    return T12Entry(
        input_id=f"ledger-{index}",
        month=date(2025, month, 1),
        account=account,
        amount=Decimal(amount),
        one_time=one_time,
    )


def chart(mapping: dict[str, str]) -> ChartOfAccounts:
    return ChartOfAccounts(input_id="policy-chart", mapping=mapping)


def rule(strategy: str) -> MissingMonthRule:
    return MissingMonthRule.model_validate({"input_id": f"policy-{strategy}", "strategy": strategy})


def test_t013_ac2_t12_maps_accounts_flags_missing_months_and_one_time_items() -> None:
    result = normalize_t12(
        [
            entry(1, 1, "rent", "100"),
            entry(2, 2, "rent", "200"),
            entry(3, 2, "repair", "50", one_time=True),
            entry(4, 2, "mystery", "10"),
        ],
        chart=chart({"rent": "rental_income", "repair": "repairs"}),
        missing_month_rule=MissingMonthRule(
            input_id="assumption-annualize", strategy="annualize_observed"
        ),
        calc_id="t12",
        code_version="release-1",
    )
    assert result.inputs == {
        "chart": "policy-chart",
        "missing_month_policy": "assumption-annualize",
        **{f"entry:{i}": f"ledger-{i}" for i in range(1, 5)},
    }
    assert result.outputs["line:rental_income"] == Decimal("1800")
    assert result.outputs["line:repairs"] == Decimal("50")
    assert result.outputs["line:unmapped:mystery"] == Decimal("60")
    assert result.outputs["missing_month_count"] == Decimal(10)
    assert result.outputs["imputed_month_count"] == Decimal(10)
    assert result.outputs["annualization_factor"] == Decimal(6)
    assert result.outputs["one_time_total"] == Decimal(50)
    assert result.outputs["one_time_count"] == Decimal(1)
    assert result.outputs["unmapped_count"] == Decimal(1)


def test_t013_ac2_t12_zero_policy_does_not_invent_missing_months() -> None:
    result = normalize_t12(
        [entry(1, 1, "rent", "100")],
        chart=chart({"rent": "income"}),
        missing_month_rule=rule("zero"),
        calc_id="t12",
        code_version="v",
    )
    assert result.outputs["line:income"] == Decimal(100)
    assert result.outputs["missing_month_count"] == Decimal(11)
    assert result.outputs["imputed_month_count"] == Decimal(0)
    assert result.outputs["annualization_factor"] == Decimal(1)


@given(st.lists(st.integers(-100000, 100000), min_size=12, max_size=12))
def test_t013_ac3_t12_twelve_month_annualization_is_identity(amounts) -> None:
    rows = [entry(month, month, "rent", str(amount)) for month, amount in enumerate(amounts, 1)]
    result = normalize_t12(
        rows,
        chart=chart({"rent": "income"}),
        missing_month_rule=rule("annualize_observed"),
        calc_id="t12",
        code_version="v",
    )
    assert result.outputs["line:income"] == sum(map(Decimal, amounts), Decimal())
    assert result.outputs["annualization_factor"] == Decimal(1)
    assert result.outputs["missing_month_count"] == Decimal(0)


def test_t013_ac2_t12_refuses_duplicate_ids_bad_dates_and_unknown_policy() -> None:
    with pytest.raises(ValueError):
        normalize_t12(
            [entry(1, 1, "rent", "1"), entry(1, 2, "rent", "2")],
            chart=chart({"rent": "income"}),
            missing_month_rule=rule("zero"),
            calc_id="t12",
            code_version="v",
        )
    with pytest.raises(ValueError):
        T12Entry(input_id="x", month=date(2025, 1, 2), account="rent", amount=Decimal(1))
    with pytest.raises(ValueError):
        rule("guess")
