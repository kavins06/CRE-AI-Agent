"""Finance v1 uses 28 significant digits, half-even rounding, and isolated signals.

https://docs.python.org/3.12/library/decimal.html#decimal.localcontext
"""

from collections.abc import Callable
from decimal import (
    ROUND_HALF_EVEN,
    Context,
    DivisionByZero,
    FloatOperation,
    InvalidOperation,
    Overflow,
    localcontext,
)
from functools import wraps

from cre_brain.domain import CalcResult


def _calculation[**P](function: Callable[P, CalcResult]) -> Callable[P, CalcResult]:
    @wraps(function)
    def isolated(*args: P.args, **kwargs: P.kwargs) -> CalcResult:
        with localcontext(
            Context(
                prec=28,
                rounding=ROUND_HALF_EVEN,
                Emin=-999999,
                Emax=999999,
                capitals=1,
                clamp=0,
                flags=[],
                traps=[InvalidOperation, DivisionByZero, Overflow, FloatOperation],
            )
        ):
            return function(*args, **kwargs)

    return isolated
