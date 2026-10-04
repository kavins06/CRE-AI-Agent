"""Validated Decimal latent inputs and configurable, explicitly uncalibrated priors."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, localcontext
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from cre_brain.finance.proforma import ProFormaInput
from cre_brain.finance.rentroll import RentRollUnit
from cre_brain.finance.t12 import ChartOfAccounts, MissingMonthRule, T12Entry

from ._context import generator_context
from .identity import input_id

Layout = Literal["yardi", "realpage", "broker"]
DealId = Annotated[str, StringConstraints(pattern=r"^deal-[0-9]{4}$")]
PositiveMoney = Annotated[Decimal, Field(gt=0, le=1_000_000, decimal_places=2)]
BasisPoints = Annotated[int, Field(ge=0, le=10000)]
Account = Literal[
    "rent",
    "other_income",
    "tax",
    "insurance",
    "utilities",
    "repairs",
    "management",
    "payroll",
    "reserves",
]
ACCOUNTS: tuple[Account, ...] = (
    "rent",
    "other_income",
    "tax",
    "insurance",
    "utilities",
    "repairs",
    "management",
    "payroll",
    "reserves",
)
EXPENSE_ACCOUNTS = ACCOUNTS[2:-1]


class Boundary(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, allow_inf_nan=False, revalidate_instances="always"
    )


class DefaultPriors(Boundary):
    calibrated: Literal[False] = False
    min_units: Annotated[int, Field(ge=12, le=96)] = 12
    max_units: Annotated[int, Field(ge=12, le=96)] = 96
    min_rent: PositiveMoney = Decimal("900.00")
    max_rent: PositiveMoney = Decimal("2400.00")
    min_vacancy_bps: BasisPoints = 200
    max_vacancy_bps: BasisPoints = 1500
    max_loss_to_lease_bps: BasisPoints = 1200
    max_concession_bps: BasisPoints = 500

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if (
            self.min_units > self.max_units
            or self.min_rent > self.max_rent
            or self.min_vacancy_bps > self.max_vacancy_bps
        ):
            raise ValueError("Prior bounds must be ordered")
        return self


class Unit(RentRollUnit):
    model_config = Boundary.model_config
    unit_id: Annotated[str, StringConstraints(pattern=r"\AU[0-9]{3}\z", strip_whitespace=False)]
    unit_type: Literal["1BR", "2BR", "3BR"]
    market_rent: PositiveMoney
    contract_rent: Annotated[Decimal, Field(ge=0, le=1_000_000, decimal_places=2)]
    monthly_concession: Annotated[Decimal, Field(ge=0, le=1_000_000, decimal_places=2)]


class Entry(T12Entry):
    model_config = Boundary.model_config
    account: Account
    amount: Annotated[Decimal, Field(ge=0, le=1_000_000_000, decimal_places=2)]
    one_time: Literal[False] = False


class LatentDeal(Boundary):
    deal_id: DealId
    layout: Layout
    as_of: date
    vintage: Annotated[int, Field(ge=1940, le=2020)]
    asking_price: Annotated[Decimal, Field(gt=0, le=1_000_000_000, decimal_places=2)]
    units: Annotated[tuple[Unit, ...], Field(min_length=1, max_length=96)]
    entries: Annotated[tuple[Entry, ...], Field(min_length=108, max_length=108)]
    chart: ChartOfAccounts
    missing_month_rule: MissingMonthRule
    proforma: ProFormaInput

    @model_validator(mode="after")
    def coherent(self) -> Self:
        # Revalidate finance boundaries too: model_copy() is deliberately not validation.
        pf = ProFormaInput.model_validate(self.proforma.model_dump())
        if len({u.unit_id for u in self.units}) != len(self.units):
            raise ValueError("Duplicate unit IDs")
        ids = [u.input_id for u in self.units] + [e.input_id for e in self.entries]
        ids += [self.chart.input_id, self.missing_month_rule.input_id, pf.input_id]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate input IDs")
        expected_ids = [
            input_id(f"{self.deal_id}:unit:{number}", u.model_dump(exclude={"input_id"}))
            for number, u in enumerate(self.units, 1)
        ]
        expected_ids += [
            input_id(
                f"{self.deal_id}:ledger:{e.month.month}:{e.account}",
                e.model_dump(exclude={"input_id", "one_time"}),
            )
            for e in self.entries
        ]
        expected_ids += [
            input_id(f"{self.deal_id}:chart", self.chart.mapping),
            input_id(f"{self.deal_id}:missing", {"strategy": self.missing_month_rule.strategy}),
            input_id(f"{self.deal_id}:projection", pf.model_dump(exclude={"input_id"})),
        ]
        if ids != expected_ids:
            raise ValueError("Input identity must match deal lineage and exact input contents")
        pairs = {(e.month, e.account) for e in self.entries}
        expected = {
            (date(self.as_of.year - 1, month, 1), account)
            for month in range(1, 13)
            for account in ACCOUNTS
        }
        if pairs != expected or len(pairs) != len(self.entries):
            raise ValueError("Exactly twelve complete calendar months are required")
        if self.as_of.month != 1 or self.as_of.day != 1:
            raise ValueError("As-of must follow the complete prior calendar year")
        if self.chart.mapping != {account: account for account in ACCOUNTS}:
            raise ValueError("Chart must preserve expense and below-NOI reserve categories")
        if self.missing_month_rule.strategy != "zero":
            raise ValueError("Complete T12 fixtures use zero missing-month policy")
        with localcontext(generator_context()):
            rent = sum((u.contract_rent - u.monthly_concession for u in self.units), Decimal(0))
            for month in range(1, 13):
                amounts = {e.account: e.amount for e in self.entries if e.month.month == month}
                if amounts["rent"] != rent:
                    raise ValueError("Ledger rent must match occupied net collections")
                expenses = sum((amounts[a] for a in EXPENSE_ACCOUNTS), Decimal(0))
                if (
                    pf.base_monthly_revenue != rent + amounts["other_income"]
                    or pf.base_monthly_operating_expenses != expenses
                    or pf.monthly_reserves != amounts["reserves"]
                ):
                    raise ValueError("Projection inputs must reconcile to the rendered ledger")
        if pf.vacancy_rate != 0 or pf.credit_loss_rate != 0 or pf.projection_months != 12:
            raise ValueError("Collection-basis projection cannot subtract vacancy twice")
        return self
