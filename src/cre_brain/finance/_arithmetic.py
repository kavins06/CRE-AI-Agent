"""Bounded exact money and guarded ACT/365 discounting, with 28-digit outputs.

Finite decimal money uses Fraction until the output boundary. Fractional-year
growth is Decimal (80–256 working digits), never binary64. Unsupported input
span/precision fails explicitly. Public callers must use _calculation isolation.
"""

from datetime import date
from decimal import Decimal, localcontext
from fractions import Fraction
from math import gcd, lcm


def working_precision(values: list[Decimal]) -> int:
    nonzero = [v for v in values if v]
    if not nonzero:
        return 80
    if any(abs(v.adjusted()) > 4096 or len(v.as_tuple().digits) > 216 for v in nonzero):
        raise ValueError("Finance inputs exceed the bounded precision budget")
    span = max(v.adjusted() for v in nonzero) - min(int(v.as_tuple().exponent) for v in nonzero) + 1
    precision = max(80, span + len(str(len(values))) + 40)
    if precision > 256:
        raise ValueError("Finance input span exceeds 256 working precision digits")
    return precision


def decimal_value(value: Fraction, precision: int = 28) -> Decimal:
    if max(value.numerator.bit_length(), value.denominator.bit_length()) > 65536:
        raise ValueError("Exact finance arithmetic exceeds the rational complexity budget")
    with localcontext() as context:
        context.prec = precision
        return Decimal(value.numerator) / Decimal(value.denominator)


def return_coefficients(values: list[Fraction]) -> tuple[Decimal, ...]:
    """Clear a common denominator exactly; uniform scaling preserves all roots.

    Even guarded decimal conversion of recurring coefficients can collapse
    distinct IRRs. Money outputs must separately use the unscaled ledger.
    """
    denominator = 1
    for value in values:
        if max(value.numerator.bit_length(), value.denominator.bit_length()) > 65536:
            raise ValueError("Return coefficients exceed the rational complexity budget")
        denominator = lcm(denominator, value.denominator)
        if denominator.bit_length() > 65536:
            raise ValueError("Return denominator exceeds the rational complexity budget")
    coefficients = [value.numerator * (denominator // value.denominator) for value in values]
    if any(abs(value).bit_length() > 65536 for value in coefficients):
        raise ValueError("Return coefficients exceed the rational complexity budget")
    divisor = gcd(*coefficients) or 1
    return tuple(Decimal(value // divisor) for value in coefficients)


def growth(rate: Decimal, start: date, end: date) -> Decimal:
    days = (end - start).days
    if days % 365 == 0:
        return (1 + rate) ** (days // 365)
    return ((1 + rate).ln() * (Decimal(days) / 365)).exp()


def dated_value(
    flows: list[tuple[date, Fraction]], rate: Decimal, valuation_date: date, precision: int
) -> Decimal:
    with localcontext() as context:
        context.prec = precision
        return sum(
            (
                decimal_value(amount, precision) * growth(rate, day, valuation_date)
                for day, amount in flows
            ),
            Decimal(0),
        )
