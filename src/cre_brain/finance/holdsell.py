"""Decision-date NPV comparison; historical capital affects returns, not ranking.

Operating flows are net equity cash flows after debt service. Refinancing records
draw less old payoff, fees and prepayment; the terminal exit must include the
then-outstanding new debt payoff. No implied debt amortization or missing balloon
is invented. Equal exact decision values receive the same competition rank.
"""

from decimal import Decimal
from fractions import Fraction
from typing import Literal

from pydantic import Field

from cre_brain.domain import CalcResult
from cre_brain.domain.base import Identifier
from cre_brain.domain.models import DomainModel
from cre_brain.finance._arithmetic import dated_value, decimal_value, working_precision
from cre_brain.finance._context import _calculation
from cre_brain.finance.exit import ExitInput, _exit_amounts
from cre_brain.finance.proforma import NonnegativeDecimal
from cre_brain.finance.returns import DateOnly, Rate
from cre_brain.finance.waterfall import DatedEquityFlow, _return_outputs


class RefinanceEvent(DomainModel):
    input_id: Identifier
    date: DateOnly
    new_principal: NonnegativeDecimal
    old_debt_payoff: NonnegativeDecimal
    fees: NonnegativeDecimal
    prepayment_cost: NonnegativeDecimal


class DispositionScenario(DomainModel):
    input_id: Identifier
    kind: Literal["hold", "sell", "refinance"]
    terminal_date: DateOnly
    exit: ExitInput
    operating_flows: tuple[DatedEquityFlow, ...] = Field(max_length=598)
    refinance: RefinanceEvent | None


class HoldSellInput(DomainModel):
    input_id: Identifier
    decision_date: DateOnly
    discount_rate: Rate
    historical_flows: tuple[DatedEquityFlow, ...] = Field(max_length=598)
    finance_rate: Rate
    reinvest_rate: Rate


@_calculation
def compare_hold_sell(
    source: HoldSellInput,
    alternatives: tuple[DispositionScenario, ...],
    *,
    calc_id: str,
    code_version: str,
) -> CalcResult:
    if not alternatives or len({a.kind for a in alternatives}) != len(alternatives):
        raise ValueError("Supply distinct hold, sell or refinance alternatives")
    if any(f.date > source.decision_date for f in source.historical_flows):
        raise ValueError("Historical flows cannot follow the decision date")
    precision = working_precision(
        [source.discount_rate, source.finance_rate, source.reinvest_rate]
        + [f.amount for f in source.historical_flows]
        + [f.amount for a in alternatives for f in a.operating_flows]
        + [
            v
            for a in alternatives
            for v in (
                a.exit.forward_noi,
                a.exit.cap_rate,
                a.exit.selling_cost_rate,
                a.exit.fixed_selling_cost,
                a.exit.debt_payoff,
            )
        ]
        + [
            v
            for a in alternatives
            if a.refinance
            for v in (
                a.refinance.new_principal,
                a.refinance.old_debt_payoff,
                a.refinance.fees,
                a.refinance.prepayment_cost,
            )
        ]
    )
    outputs: dict[str, Decimal] = {}
    inputs = {
        "comparison": source.input_id,
        **{f"historical:{i}": f.input_id for i, f in enumerate(source.historical_flows)},
    }
    values: dict[str, Decimal] = {}
    for a in alternatives:
        if a.terminal_date < source.decision_date or any(
            not source.decision_date <= f.date <= a.terminal_date for f in a.operating_flows
        ):
            raise ValueError("Operating and terminal flows violate the decision timeline")
        if a.kind == "sell" and (
            a.terminal_date != source.decision_date or a.operating_flows or a.refinance
        ):
            raise ValueError("The sell alternative must dispose immediately")
        if (a.kind == "refinance") != (a.refinance is not None):
            raise ValueError("Only the refinance alternative requires a refinance event")
        inputs[a.kind] = a.input_id
        inputs[f"{a.kind}:exit"] = a.exit.input_id
        future = [(f.date, Fraction(f.amount)) for f in a.operating_flows]
        inputs.update(
            {f"{a.kind}:operating:{i}": f.input_id for i, f in enumerate(a.operating_flows)}
        )
        if a.refinance:
            refi = a.refinance
            if not source.decision_date <= refi.date <= a.terminal_date:
                raise ValueError("Refinance date violates the decision timeline")
            proceeds = (
                Fraction(refi.new_principal)
                - Fraction(refi.old_debt_payoff)
                - Fraction(refi.fees)
                - Fraction(refi.prepayment_cost)
            )
            future.append((refi.date, proceeds))
            inputs[f"{a.kind}:refinance"] = refi.input_id
            outputs[f"{a.kind}:refinance_proceeds"] = decimal_value(proceeds)
        exit_amounts = _exit_amounts(a.exit)
        future.append((a.terminal_date, exit_amounts["net_equity_proceeds"]))
        values[a.kind] = dated_value(future, source.discount_rate, source.decision_date, precision)
        outputs[f"{a.kind}:npv"] = decimal_value(Fraction(values[a.kind]))
        outputs.update({f"{a.kind}:exit:{k}": decimal_value(v) for k, v in exit_amounts.items()})
        ledger = sorted([*((f.date, Fraction(f.amount)) for f in source.historical_flows), *future])
        if len(ledger) > 600:
            raise ValueError("Scenario returns support at most 600 dated flows")
        outputs.update(
            {
                f"{a.kind}:returns:{k}": v
                for k, v in _return_outputs(
                    ledger,
                    source.finance_rate,
                    source.reinvest_rate,
                    source.input_id,
                    calc_id,
                    code_version,
                ).items()
            }
        )
    for kind, value in values.items():
        outputs[f"{kind}:rank"] = Decimal(1 + sum(other > value for other in values.values()))
        if "sell" in values:
            outputs[f"{kind}:incremental_npv"] = decimal_value(
                Fraction(value) - Fraction(values["sell"])
            )
    return CalcResult(
        calc_id=calc_id,
        fn="compare_hold_sell",
        inputs=inputs,
        outputs=outputs,
        code_version=code_version,
    )
