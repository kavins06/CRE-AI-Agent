"""Complete Decimal recipe matching finance v1, independent of mutable defaults."""

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


def generator_context() -> Context:
    # Finance's helper decorates CalcResult functions; these boundaries construct
    # latent models instead, so use the same explicit recipe with a fresh context.
    return Context(
        prec=28,
        rounding=ROUND_HALF_EVEN,
        Emin=-999999,
        Emax=999999,
        capitals=1,
        clamp=0,
        flags=[],
        traps=[InvalidOperation, DivisionByZero, Overflow, FloatOperation],
    )


def isolated_decimal[**P, R](function: Callable[P, R]) -> Callable[P, R]:
    """Isolate validation as well as arithmetic, preserving all caller signals."""

    @wraps(function)
    def isolated(*args: P.args, **kwargs: P.kwargs) -> R:
        with localcontext(generator_context()):
            return function(*args, **kwargs)

    return isolated
