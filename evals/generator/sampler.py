"""Isolated PRNG; integers select inputs, Decimal constructs all financial values."""

import json
from datetime import date
from decimal import Decimal, localcontext
from hashlib import sha256
from random import Random
from typing import Literal, TypedDict

from cre_brain.finance.proforma import ProFormaInput
from cre_brain.finance.t12 import ChartOfAccounts, MissingMonthRule

from ._context import generator_context, isolated_decimal
from .identity import input_id
from .models import ACCOUNTS, Account, DefaultPriors, Entry, LatentDeal, Unit


class _UnitValues(TypedDict):
    unit_id: str
    unit_type: Literal["1BR", "2BR", "3BR"]
    market_rent: Decimal
    contract_rent: Decimal
    occupied: bool
    monthly_concession: Decimal


class _EntryValues(TypedDict):
    month: date
    account: Account
    amount: Decimal


class _ProjectionValues(TypedDict):
    base_monthly_revenue: Decimal
    base_monthly_operating_expenses: Decimal
    annual_revenue_growth: Decimal
    annual_expense_growth: Decimal
    vacancy_rate: Decimal
    credit_loss_rate: Decimal
    monthly_reserves: Decimal
    projection_months: int


@isolated_decimal
def sample_deal(seed: str, *, index: int = 1, priors: DefaultPriors | None = None) -> LatentDeal:
    if not isinstance(seed, str) or not seed or len(seed) > 1024:
        raise ValueError("Seed must be a nonempty string of at most 1024 characters")
    if type(index) is not int or not 1 <= index <= 1000:
        raise ValueError("Deal index must be an integer in [1, 1000]")
    priors = DefaultPriors.model_validate(priors or DefaultPriors())
    rng = Random(int.from_bytes(sha256(json.dumps([seed, index]).encode()).digest(), "big"))
    deal_id = f"deal-{index:04d}"
    with localcontext(generator_context()):
        cents = Decimal("0.01")
        count = rng.randint(priors.min_units, priors.max_units)
        vacancy_bps = rng.randint(priors.min_vacancy_bps, priors.max_vacancy_bps)
        units = []
        for number in range(1, count + 1):
            market = (
                Decimal(rng.randint(int(priors.min_rent * 100), int(priors.max_rent * 100))) / 100
            )
            occupied = rng.randint(1, 10000) > vacancy_bps
            contract = (
                (market * (10000 - rng.randint(0, priors.max_loss_to_lease_bps)) / 10000).quantize(
                    cents
                )
                if occupied
                else Decimal("0.00")
            )
            concession = (contract * rng.randint(0, priors.max_concession_bps) / 10000).quantize(
                cents
            )
            unit_values: _UnitValues = dict(
                unit_id=f"U{number:03d}",
                unit_type=rng.choice(("1BR", "2BR", "3BR")),
                market_rent=market,
                contract_rent=contract,
                occupied=occupied,
                monthly_concession=concession,
            )
            units.append(
                Unit(input_id=input_id(f"{deal_id}:unit:{number}", unit_values), **unit_values)
            )
        collected = sum((u.contract_rent - u.monthly_concession for u in units), Decimal(0))
        other = Decimal(count * rng.randint(1500, 6000)) / 100
        revenue = collected + other
        amounts = {"rent": collected, "other_income": other}
        # Independent per-category shares of collected revenue; property tax included in opex.
        for expense_account, low, high in (
            ("tax", 800, 1200),
            ("insurance", 300, 600),
            ("utilities", 500, 900),
            ("repairs", 600, 1000),
            ("management", 300, 500),
            ("payroll", 700, 1000),
        ):
            amounts[expense_account] = (revenue * rng.randint(low, high) / 10000).quantize(cents)
        expenses = sum(
            (v for k, v in amounts.items() if k not in ("rent", "other_income")), Decimal(0)
        )
        amounts["reserves"] = Decimal(count * rng.randint(1500, 4000)) / 100
        entries = []
        for month in range(1, 13):
            for account in ACCOUNTS:
                entry_values: _EntryValues = dict(
                    month=date(2025, month, 1), account=account, amount=amounts[account]
                )
                entries.append(
                    Entry(
                        input_id=input_id(f"{deal_id}:ledger:{month}:{account}", entry_values),
                        **entry_values,
                    )
                )
        mapping: dict[str, str] = {a: a for a in ACCOUNTS}
        chart = ChartOfAccounts(input_id=input_id(f"{deal_id}:chart", mapping), mapping=mapping)
        rule = MissingMonthRule(
            input_id=input_id(f"{deal_id}:missing", {"strategy": "zero"}), strategy="zero"
        )
        projection_values: _ProjectionValues = dict(
            base_monthly_revenue=revenue,
            base_monthly_operating_expenses=expenses,
            annual_revenue_growth=Decimal(rng.randint(0, 500)) / 10000,
            annual_expense_growth=Decimal(rng.randint(100, 500)) / 10000,
            vacancy_rate=Decimal(0),
            credit_loss_rate=Decimal(0),
            monthly_reserves=amounts["reserves"],
            projection_months=12,
        )
        proforma = ProFormaInput(
            input_id=input_id(f"{deal_id}:projection", projection_values), **projection_values
        )
        return LatentDeal(
            deal_id=deal_id,
            layout=("yardi", "realpage", "broker")[(index - 1) % 3],
            as_of=date(2026, 1, 1),
            vintage=rng.randint(1940, 2020),
            asking_price=Decimal(count * rng.randint(80000, 250000)),
            units=tuple(units),
            entries=tuple(entries),
            chart=chart,
            missing_month_rule=rule,
            proforma=proforma,
        )
