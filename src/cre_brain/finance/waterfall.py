"""European dated waterfall: simple ACT/365 LP pref, capital, GP catch-up, promote.

Negative property flows are additional pro-rata capital calls (including losses),
not clawbacks. Pref accrues only on unreturned LP capital; unpaid pref does not
compound. Capital is returned pari passu. GP catch-up is cumulative profit share,
excluding capital, and pays 100% to GP until caught up. Each finite promote tier
ends at an LP fixed-rate dated NPV hurdle, not an assumed unique IRR. The last
tier is unbounded. Same-day events execute in supplied order. No terminal write-off
or fabricated IRR: outstanding balances and certified return status are exposed.
"""

from datetime import date
from decimal import Decimal
from fractions import Fraction
from typing import Self

from pydantic import Field, model_validator

from cre_brain.domain import CalcResult
from cre_brain.domain.base import Identifier
from cre_brain.domain.models import DomainModel
from cre_brain.finance._arithmetic import dated_value, decimal_value, working_precision
from cre_brain.finance._context import _calculation
from cre_brain.finance.proforma import NonnegativeDecimal, Ratio
from cre_brain.finance.returns import (
    DateOnly,
    FiniteDecimal,
    Rate,
    ReturnsInput,
    calculate_returns,
)


class DatedEquityFlow(DomainModel):
    input_id: Identifier
    date: DateOnly
    amount: FiniteDecimal


class PromoteTier(DomainModel):
    hurdle_rate: NonnegativeDecimal | None
    lp_share: Ratio = Field(gt=0)


class WaterfallTerms(DomainModel):
    input_id: Identifier
    lp_ownership: Ratio = Field(gt=0)
    preferred_rate: NonnegativeDecimal
    catch_up_share: Ratio = Field(lt=1)
    tiers: tuple[PromoteTier, ...] = Field(min_length=1, max_length=20)
    finance_rate: Rate
    reinvest_rate: Rate

    @model_validator(mode="after")
    def ordered_tiers(self) -> Self:
        if self.tiers[-1].hurdle_rate is not None:
            raise ValueError("The final promote tier must be unbounded")
        last = Decimal(-1)
        for tier in self.tiers[:-1]:
            if tier.hurdle_rate is None or tier.hurdle_rate <= last:
                raise ValueError("Finite IRR hurdles must be strictly increasing")
            last = tier.hurdle_rate
        return self


def _return_outputs(
    ledger: list[tuple[date, Fraction]],
    finance_rate: Decimal,
    reinvest_rate: Decimal,
    input_id: str,
    calc_id: str,
    code_version: str,
) -> dict[str, Decimal]:
    # One dated event alone has no holding-period return.
    if len(ledger) == 1:
        ledger = [*ledger, (ledger[0][0], Fraction(0))]
    return calculate_returns(
        ReturnsInput(
            input_id=input_id,
            cash_flows=tuple(decimal_value(v) for _, v in ledger),
            dates=tuple(d for d, _ in ledger),
            finance_rate=finance_rate,
            reinvest_rate=reinvest_rate,
        ),
        calc_id=calc_id,
        code_version=code_version,
    ).outputs


@_calculation
def distribute_waterfall(
    flows: tuple[DatedEquityFlow, ...],
    terms: WaterfallTerms,
    *,
    calc_id: str,
    code_version: str,
) -> CalcResult:
    if not 1 <= len(flows) <= 600:
        raise ValueError("Waterfalls require 1–600 dated flows")
    if any(a.date > b.date for a, b in zip(flows, flows[1:], strict=False)):
        raise ValueError("Waterfall flows must be chronological")
    if flows[0].amount >= 0:
        raise ValueError("The first flow must be a capital contribution")
    precision = working_precision(
        [f.amount for f in flows]
        + [
            terms.lp_ownership,
            terms.preferred_rate,
            terms.catch_up_share,
            terms.finance_rate,
            terms.reinvest_rate,
        ]
        + [v for tier in terms.tiers for v in (tier.lp_share, tier.hurdle_rate) if v is not None]
    )
    ownership = Fraction(terms.lp_ownership)
    capitals = [Fraction(0), Fraction(0)]
    profit = [Fraction(0), Fraction(0)]
    total = [Fraction(0), Fraction(0)]
    ledgers: list[list[tuple[date, Fraction]]] = [[], []]
    pref = Fraction(0)
    outputs: dict[str, Decimal] = {}
    previous = flows[0].date
    for index, event in enumerate(flows):
        pref += (
            capitals[0]
            * Fraction(terms.preferred_rate)
            * Fraction((event.date - previous).days, 365)
        )
        previous = event.date
        stages = ["pref", "capital", "catchup", *[f"tier:{i}" for i in range(len(terms.tiers))]]
        allocation = {stage: [Fraction(0), Fraction(0)] for stage in stages}
        if event.amount < 0:
            contribution = -Fraction(event.amount)
            lp = contribution * ownership
            gp = contribution - lp
            capitals[0] += lp
            capitals[1] += gp
            ledgers[0].append((event.date, -lp))
            ledgers[1].append((event.date, -gp))
        else:
            remaining = Fraction(event.amount)
            paid_pref = min(remaining, pref)
            allocation["pref"][0] = paid_pref
            pref -= paid_pref
            remaining -= paid_pref
            profit[0] += paid_pref
            capital = sum(capitals)
            returned = min(remaining, capital)
            lp_capital = returned * capitals[0] / capital if capital else Fraction(0)
            allocation["capital"] = [lp_capital, returned - lp_capital]
            capitals[0] -= lp_capital
            capitals[1] -= returned - lp_capital
            remaining -= returned
            catchup = Fraction(terms.catch_up_share)
            gp_catchup = min(
                remaining, max(Fraction(0), profit[0] * catchup / (1 - catchup) - profit[1])
            )
            allocation["catchup"][1] = gp_catchup
            profit[1] += gp_catchup
            remaining -= gp_catchup
            for tier_index, tier in enumerate(terms.tiers):
                share = Fraction(tier.lp_share)
                if tier.hurdle_rate is None:
                    amount = remaining
                else:
                    lp_so_far = sum((v[0] for v in allocation.values()), Fraction(0))
                    value = dated_value(
                        [*ledgers[0], (event.date, lp_so_far)],
                        tier.hurdle_rate,
                        event.date,
                        precision,
                    )
                    gap = max(Fraction(0), -Fraction(value))
                    amount = min(remaining, gap / share)
                lp_amount = amount * share
                gp_amount = amount - lp_amount
                allocation[f"tier:{tier_index}"] = [lp_amount, gp_amount]
                profit[0] += lp_amount
                profit[1] += gp_amount
                remaining -= amount
            for party in range(2):
                paid = sum((v[party] for v in allocation.values()), Fraction(0))
                total[party] += paid
                ledgers[party].append((event.date, paid))
        outputs[f"event:{index}:date_ordinal"] = Decimal(event.date.toordinal())
        outputs[f"event:{index}:property_flow"] = event.amount
        for stage, amounts in allocation.items():
            for party, name in enumerate(("lp", "gp")):
                outputs[f"event:{index}:{stage}:{name}"] = decimal_value(amounts[party])
    outputs.update(
        lp_distributions=decimal_value(total[0]),
        gp_distributions=decimal_value(total[1]),
        total_distributions=decimal_value(sum(total, Fraction(0))),
        unreturned_lp_capital=decimal_value(capitals[0]),
        unreturned_gp_capital=decimal_value(capitals[1]),
        unpaid_pref=decimal_value(pref),
    )
    for party, name in enumerate(("lp", "gp")):
        outputs.update(
            {
                f"{name}:{k}": v
                for k, v in _return_outputs(
                    ledgers[party],
                    terms.finance_rate,
                    terms.reinvest_rate,
                    terms.input_id,
                    calc_id,
                    code_version,
                ).items()
            }
        )
    return CalcResult(
        calc_id=calc_id,
        fn="distribute_waterfall",
        inputs={"terms": terms.input_id, **{f"flow:{i}": f.input_id for i, f in enumerate(flows)}},
        outputs=outputs,
        code_version=code_version,
    )
