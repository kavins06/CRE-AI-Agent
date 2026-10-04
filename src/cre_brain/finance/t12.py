"""Deterministic chart mapping and incomplete T-12 normalization."""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator

from cre_brain.domain import CalcResult
from cre_brain.domain.base import Identifier
from cre_brain.domain.models import DomainModel

MissingMonthPolicy = Literal["zero", "annualize_observed"]
ZERO = Decimal()


class T12Entry(DomainModel):
    input_id: Identifier
    month: date
    account: Identifier
    amount: Decimal
    one_time: bool = False

    @field_validator("month")
    @classmethod
    def first_of_month(cls, value: date) -> date:
        if value.day != 1:
            raise ValueError("T-12 months must use the first day of each month")
        return value


class ChartOfAccounts(DomainModel):
    input_id: Identifier
    mapping: dict[Identifier, Identifier] = Field(min_length=1)


class MissingMonthRule(DomainModel):
    input_id: Identifier
    strategy: MissingMonthPolicy


def _month_number(value: date) -> int:
    return value.year * 12 + value.month - 1


def normalize_t12(
    entries: list[T12Entry],
    *,
    chart: ChartOfAccounts,
    missing_month_rule: MissingMonthRule,
    calc_id: str,
    code_version: str,
) -> CalcResult:
    if not entries:
        raise ValueError("T-12 requires at least one ledger entry")
    if len({entry.input_id for entry in entries}) != len(entries):
        raise ValueError("T-12 ledger input IDs must be unique")
    months = {entry.month for entry in entries}
    month_numbers = {_month_number(month) for month in months}
    if len(months) > 12 or max(month_numbers) - min(month_numbers) >= 12:
        raise ValueError("T-12 entries must fit in one twelve-month window")
    missing = 12 - len(months)
    factor = (
        Decimal(12) / Decimal(len(months))
        if missing_month_rule.strategy == "annualize_observed"
        else Decimal(1)
    )
    recurring: defaultdict[str, Decimal] = defaultdict(Decimal)
    one_time: defaultdict[str, Decimal] = defaultdict(Decimal)
    unmapped_count = 0
    for entry in entries:
        line = chart.mapping.get(entry.account)
        if line is None:
            line = f"unmapped:{entry.account}"
            unmapped_count += 1
        (one_time if entry.one_time else recurring)[line] += entry.amount
    outputs = {
        f"line:{line}": recurring[line] * factor + one_time[line]
        for line in sorted(recurring.keys() | one_time.keys())
    }
    outputs.update(
        {
            "missing_month_count": Decimal(missing),
            "imputed_month_count": Decimal(
                missing if missing_month_rule.strategy == "annualize_observed" else 0
            ),
            "annualization_factor": factor,
            "one_time_total": sum(one_time.values(), ZERO),
            "one_time_count": Decimal(sum(entry.one_time for entry in entries)),
            "unmapped_count": Decimal(unmapped_count),
        }
    )
    for entry in entries:
        if entry.one_time:
            outputs[f"one_time:{entry.input_id}"] = Decimal(1)
    return CalcResult(
        calc_id=calc_id,
        fn="normalize_t12",
        inputs={
            "chart": chart.input_id,
            "missing_month_policy": missing_month_rule.input_id,
            **{f"entry:{index}": entry.input_id for index, entry in enumerate(entries, 1)},
        },
        outputs=outputs,
        code_version=code_version,
    )
