"""Forward-NOI capitalization with explicit sale costs and debt payoff."""

from fractions import Fraction

from cre_brain.domain import CalcResult
from cre_brain.domain.base import Identifier
from cre_brain.domain.models import DomainModel
from cre_brain.finance._arithmetic import decimal_value, working_precision
from cre_brain.finance._context import _calculation
from cre_brain.finance.proforma import NonnegativeDecimal, Ratio
from cre_brain.finance.returns import PositiveDecimal


class ExitInput(DomainModel):
    input_id: Identifier
    forward_noi: NonnegativeDecimal
    cap_rate: PositiveDecimal
    selling_cost_rate: Ratio
    fixed_selling_cost: NonnegativeDecimal
    debt_payoff: NonnegativeDecimal


def _exit_amounts(source: ExitInput) -> dict[str, Fraction]:
    working_precision(
        [
            source.forward_noi,
            source.cap_rate,
            source.selling_cost_rate,
            source.fixed_selling_cost,
            source.debt_payoff,
        ]
    )
    gross = Fraction(source.forward_noi) / Fraction(source.cap_rate)
    costs = gross * Fraction(source.selling_cost_rate) + Fraction(source.fixed_selling_cost)
    return {
        "gross_value": gross,
        "selling_costs": costs,
        "net_sale_proceeds": gross - costs,
        "net_equity_proceeds": gross - costs - Fraction(source.debt_payoff),
    }


@_calculation
def calculate_exit(source: ExitInput, *, calc_id: str, code_version: str) -> CalcResult:
    return CalcResult(
        calc_id=calc_id,
        fn="calculate_exit",
        inputs={"exit": source.input_id},
        outputs={key: decimal_value(amount) for key, amount in _exit_amounts(source).items()},
        code_version=code_version,
    )
