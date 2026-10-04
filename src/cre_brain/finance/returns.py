"""Decimal returns with explicit IRR ambiguity in the open (-0.99, 10) domain.

On the reduced integer period/day lattice, NPV is a rational polynomial.
Up to degree 128, exact Fraction Sturm counts certify distinct roots (including
tangencies) before bracket refinement; residual size never decides cardinality.
Larger lattices use generalized-polynomial derivative brackets and reject
uncertain stationary/boundary signs rather than declaring approximate zeros.
Dated calculations use ACT/365 fixed, aggregate repeated dates and sort them.

pyxirr 0.10.8 IRR/XIRR and Excel-timed NPV are cross-checks, not the authority
for root count. Only normalized cash flows/rates cross its binary64 boundary.
Authoritative monetary arithmetic is 28-digit Decimal; bracket refinement and
rate conversion use 80–256 digits, with rates rounded to 28 output digits.
Exact root counts use rational coefficients bounded to 16384-bit intermediates.
Working precision covers the full nonzero input exponent span, sum growth
and 40 guard digits, so repeated-date aggregation is exact in any input order.
No pyxirr float is converted into authoritative money or a reported root.
Unresolvable precision/complexity fails closed rather than inventing an IRR.
Excel NPV uses exact rational Horner arithmetic before one 28-digit rounding;
inputs are bounded to 4096 decimal digits and intermediates to 65536 bits.
"""

from datetime import date
from decimal import Decimal, localcontext
from fractions import Fraction
from math import gcd, isfinite
from typing import Annotated, Self

import pyxirr
from pydantic import BeforeValidator, Field, model_validator

from cre_brain.domain import CalcResult
from cre_brain.domain.base import Identifier
from cre_brain.domain.models import DomainModel
from cre_brain.finance._context import _calculation
from cre_brain.finance.proforma import _reject_float

FiniteDecimal = Annotated[Decimal, BeforeValidator(_reject_float)]
Rate = Annotated[Decimal, BeforeValidator(_reject_float), Field(gt=-1)]
PositiveDecimal = Annotated[Decimal, BeforeValidator(_reject_float), Field(gt=0)]
DateOnly = Annotated[date, Field(strict=True)]
ZERO = Decimal(0)
ONE = Decimal(1)
LOW_RATE = Decimal("-.99")
HIGH_RATE = Decimal(10)
Terms = list[tuple[Decimal, Decimal]]
Polynomial = list[Fraction]


def _trim(polynomial: Polynomial) -> Polynomial:
    while polynomial and not polynomial[-1]:
        polynomial.pop()
    return polynomial


def _rational_value(polynomial: Polynomial, point: Fraction) -> Fraction:
    value = Fraction(0)
    for coefficient in reversed(polynomial):
        value = value * point + coefficient
    return value


def _remainder(dividend: Polynomial, divisor: Polynomial) -> Polynomial:
    result = dividend.copy()
    while len(result) >= len(divisor):
        factor = result[-1] / divisor[-1]
        shift = len(result) - len(divisor)
        for index, coefficient in enumerate(divisor):
            result[index + shift] -= factor * coefficient
        if any(
            max(coefficient.numerator.bit_length(), coefficient.denominator.bit_length()) > 16384
            for coefficient in result
        ):
            raise ValueError("IRR exact certification exceeds the rational complexity budget")
        _trim(result)
    return result


def _exact_quotient(dividend: Polynomial, divisor: Polynomial) -> Polynomial:
    remainder = dividend.copy()
    quotient = [Fraction(0)] * (len(dividend) - len(divisor) + 1)
    while len(remainder) >= len(divisor):
        factor = remainder[-1] / divisor[-1]
        if max(factor.numerator.bit_length(), factor.denominator.bit_length()) > 16384:
            raise ValueError("IRR square-free reduction exceeds the rational complexity budget")
        shift = len(remainder) - len(divisor)
        quotient[shift] = factor
        for index, coefficient in enumerate(divisor):
            remainder[index + shift] -= factor * coefficient
        _trim(remainder)
    if remainder:
        raise ValueError("IRR square-free reduction could not be certified exactly")
    return _trim(quotient)


def _sturm(polynomial: Polynomial) -> list[Polynomial]:
    derivative = [coefficient * index for index, coefficient in enumerate(polynomial)][1:]
    sequence = [polynomial, _trim(derivative)]
    while sequence[-1]:
        remainder = _remainder(sequence[-2], sequence[-1])
        if not remainder:
            break
        scale = abs(remainder[-1])
        remainder = [-coefficient / scale for coefficient in remainder]
        if any(
            max(coefficient.numerator.bit_length(), coefficient.denominator.bit_length()) > 16384
            for coefficient in remainder
        ):
            raise ValueError("IRR exact certification exceeds the rational complexity budget")
        sequence.append(remainder)
    if len(sequence[-1]) > 1:
        return _sturm(_exact_quotient(polynomial, sequence[-1]))
    return sequence


def _variations(sequence: list[Polynomial], point: Fraction) -> int:
    values = [_rational_value(polynomial, point) for polynomial in sequence]
    signs = [value > 0 for value in values if value]
    return sum(a != b for a, b in zip(signs, signs[1:], strict=False))


def _remove_boundary(polynomial: Polynomial, point: Fraction) -> Polynomial:
    while len(polynomial) > 1 and not _rational_value(polynomial, point):
        quotient = [Fraction(0)] * (len(polynomial) - 1)
        quotient[-1] = polynomial[-1]
        for index in range(len(quotient) - 2, -1, -1):
            quotient[index] = polynomial[index + 1] + point * quotient[index + 1]
        polynomial = quotient
    return polynomial


def _certified_rates(
    lattice: list[tuple[int, Decimal]], step: Decimal, epsilon: Decimal
) -> list[Decimal]:
    polynomial = [Fraction(0)] * (lattice[-1][0] + 1)
    for power, amount in lattice:
        polynomial[power] = Fraction(amount)
    if step == step.to_integral_value():
        low, high = Fraction(1, 11) ** int(step), Fraction(100) ** int(step)
        polynomial = _remove_boundary(_remove_boundary(polynomial, low), high)
    else:
        low_value = _power(ONE / 11, step)
        high_value = _power(Decimal(100), step)
        # Enclose irrational domain endpoints; a root in this padding fails the
        # public open-boundary check rather than being silently omitted.
        low = Fraction(low_value * (ONE - epsilon))
        high = Fraction(high_value * (ONE + epsilon))
    if len(polynomial) < 2:
        return []
    sequence = _sturm(polynomial)
    low_variations, high_variations = _variations(sequence, low), _variations(sequence, high)
    brackets = [(low, high, low_variations, high_variations, 0)]
    roots: list[Fraction] = []
    tolerance = Fraction(epsilon)
    depth_limit = 4 * max(0, -epsilon.adjusted()) + 400
    while brackets:
        left, right, left_variations, right_variations, depth = brackets.pop()
        count = left_variations - right_variations
        if not count:
            continue
        # Sturm variations count (left, right], including repeated roots once.
        if count == 1 and not _rational_value(polynomial, right):
            roots.append(right)
            continue
        if count == 1 and right - left <= tolerance * min(abs(left), abs(right)):
            roots.append((left + right) / 2)
            continue
        if depth >= depth_limit:
            raise ValueError("IRR exact root separation cannot be certified at working precision")
        middle = Fraction(1) if left < 1 < right else (left + right) / 2
        middle_variations = _variations(sequence, middle)
        brackets.extend(
            [
                (left, middle, left_variations, middle_variations, depth + 1),
                (middle, right, middle_variations, right_variations, depth + 1),
            ]
        )
    return [
        _power(Decimal(root.denominator) / Decimal(root.numerator), ONE / step) - ONE
        for root in roots
    ]


class ReturnsInput(DomainModel):
    input_id: Identifier
    cash_flows: tuple[FiniteDecimal, ...] = Field(min_length=2, max_length=600)
    dates: tuple[DateOnly, ...] | None = None
    finance_rate: Rate
    reinvest_rate: Rate

    @model_validator(mode="after")
    def dates_match(self) -> Self:
        if self.dates is not None and len(self.dates) != len(self.cash_flows):
            raise ValueError("Every dated cash flow needs exactly one date")
        return self


class NPVInput(DomainModel):
    input_id: Identifier
    cash_flows: tuple[FiniteDecimal, ...] = Field(min_length=1, max_length=600)
    discount_rate: Rate


class CashOnCashInput(DomainModel):
    input_id: Identifier
    annual_operating_cash_flow: FiniteDecimal
    invested_equity: PositiveDecimal


def _times(source: ReturnsInput) -> list[Decimal]:
    if source.dates is None:
        return [Decimal(i) for i in range(len(source.cash_flows))]
    start = min(source.dates)
    return [Decimal((day - start).days) / 365 for day in source.dates]


def _power(base: Decimal, exponent: Decimal) -> Decimal:
    if exponent == exponent.to_integral_value():
        return base ** int(exponent)
    return (base.ln() * exponent).exp()


def _evaluate(terms: Terms, q: Decimal) -> tuple[Decimal, Decimal]:
    values = [coefficient * _power(q, power) for power, coefficient in terms]
    return sum(values, ZERO), sum((abs(value) for value in values), ZERO)


def _sign(value: Decimal, scale: Decimal, epsilon: Decimal) -> int:
    if abs(value) <= scale * epsilon:
        raise ValueError("IRR stationary or boundary sign cannot be certified at working precision")
    return 1 if value > 0 else -1


def _bisect(terms: Terms, left: Decimal, right: Decimal, epsilon: Decimal) -> Decimal:
    left_sign = 1 if _evaluate(terms, left)[0] > 0 else -1
    for _ in range(4 * max(0, -epsilon.adjusted()) + 400):
        middle = (left + right) / 2
        if middle == left or middle == right or right - left <= epsilon * min(left, right):
            return middle
        middle_value = _evaluate(terms, middle)[0]
        if middle_value == 0:
            raise ValueError("IRR bracket sign cannot be certified at working precision")
        middle_sign = 1 if middle_value > 0 else -1
        if middle_sign == left_sign:
            left = middle
        else:
            right = middle
    raise ValueError("IRR bracket failed to converge at the working precision")


def _isolate(terms: Terms, low: Decimal, high: Decimal, epsilon: Decimal) -> list[Decimal]:
    if len(terms) < 2:
        return []
    shift = terms[0][0]
    magnitude = max(abs(coefficient) for _, coefficient in terms)
    terms = [(power - shift, coefficient / magnitude) for power, coefficient in terms]
    signs = [coefficient > 0 for _, coefficient in terms]
    changes = sum(a != b for a, b in zip(signs, signs[1:], strict=False))
    if changes == 0:
        return []
    critical = (
        _isolate(
            [(power, coefficient * power) for power, coefficient in terms[1:]],
            low,
            high,
            epsilon,
        )
        if changes > 1
        else []
    )
    points = [low, *critical, high]
    values = [_sign(*_evaluate(terms, point), epsilon) for point in points]
    roots = []
    for left, right, left_sign, right_sign in zip(
        points, points[1:], values, values[1:], strict=False
    ):
        if left_sign * right_sign < 0:
            roots.append(_bisect(terms, left, right, epsilon))
    return sorted(roots)


def _root_rates(source: ReturnsInput) -> tuple[list[Decimal], bool, Decimal]:
    nonzero = [value for value in source.cash_flows if value]
    aligned_digits = (
        max(value.adjusted() for value in nonzero)
        - min(int(value.as_tuple().exponent) for value in nonzero)
        + 1
        if nonzero
        else 0
    )
    precision = max(80, aligned_digits + len(str(len(nonzero))) + 40)
    if precision > 256:
        raise ValueError("IRR cash-flow exponent span requires more than 256 precision digits")
    with localcontext() as context:
        context.prec = precision
        periods = (
            [(day - min(source.dates)).days for day in source.dates]
            if source.dates is not None
            else list(range(len(source.cash_flows)))
        )
        by_time: dict[int, Decimal] = {}
        for time, amount in zip(periods, source.cash_flows, strict=True):
            by_time[time] = by_time.get(time, ZERO) + amount
        exact_terms = sorted((time, amount) for time, amount in by_time.items() if amount)
        if not exact_terms:
            return [], True, ZERO
        denominator = 365 if source.dates is not None else 1
        terms = [(Decimal(time) / denominator, amount) for time, amount in exact_terms]
        signs = [coefficient > 0 for _, coefficient in terms]
        changes = sum(a != b for a, b in zip(signs, signs[1:], strict=False))
        if not changes:
            return [], False, ZERO
        if changes > 1 and len(terms) > 128:
            raise ValueError(
                "Nonconventional IRR supports at most 128 distinct nonzero dates/periods"
            )
        low, high = ONE / (ONE + HIGH_RATE), ONE / (ONE + LOW_RATE)
        epsilon = Decimal(10) ** (-precision + 12)
        shift = exact_terms[0][0]
        spacing = gcd(*(time - shift for time, _ in exact_terms))
        if spacing and (exact_terms[-1][0] - shift) // spacing <= 128:
            lattice = [((time - shift) // spacing, amount) for time, amount in exact_terms]
            rates = sorted(_certified_rates(lattice, Decimal(spacing) / denominator, epsilon))
        else:
            discount_roots = _isolate(terms, low, high, epsilon)
            rates = sorted(ONE / q - ONE for q in discount_roots)
    rounded = [+rate for rate in rates]
    if len(set(rounded)) != len(rounded):
        raise ValueError("Distinct IRR roots cannot be resolved at 28 output digits")
    if any(not LOW_RATE < rate < HIGH_RATE for rate in rounded):
        raise ValueError("IRR root cannot be distinguished from the open-domain boundary")
    maximum_residual = ZERO
    with localcontext() as context:
        context.prec = precision
        for rate in rounded:
            residual, scale = _evaluate(terms, ONE / (ONE + rate))
            relative = abs(residual) / scale
            if relative > Decimal("1e-24"):
                raise ValueError("IRR numerical residual exceeds the declared relative tolerance")
            maximum_residual = max(maximum_residual, relative)
    return rounded, False, +maximum_residual


def _mirr(source: ReturnsInput) -> Decimal | None:
    times = _times(source)
    horizon = max(times)
    if not horizon:
        return None
    negative_pv = sum(
        (
            -amount / _power(ONE + source.finance_rate, time)
            for time, amount in zip(times, source.cash_flows, strict=True)
            if amount < 0
        ),
        ZERO,
    )
    positive_fv = sum(
        (
            amount * _power(ONE + source.reinvest_rate, horizon - time)
            for time, amount in zip(times, source.cash_flows, strict=True)
            if amount > 0
        ),
        ZERO,
    )
    if not negative_pv or not positive_fv:
        return None
    return _power(positive_fv / negative_pv, ONE / horizon) - ONE


def _backend_checks(source: ReturnsInput, rates: list[Decimal]) -> tuple[int, bool]:
    scale = max(abs(amount) for amount in source.cash_flows)
    if not scale:
        return 0, False
    values = [float(amount / scale) for amount in source.cash_flows]
    if any(
        not isfinite(value) or (amount != 0 and value == 0)
        for value, amount in zip(values, source.cash_flows, strict=True)
    ):
        return 0, False
    verified = 0
    for rate in rates:
        if source.dates is None:
            candidate = pyxirr.irr(values, guess=float(rate), silent=True)
            residual = pyxirr.npv(float(rate), values, start_from_zero=True)
        else:
            candidate = pyxirr.xirr(source.dates, values, guess=float(rate), silent=True)
            residual = pyxirr.xnpv(float(rate), source.dates, values, silent=True)
        if (
            candidate is not None
            and isfinite(candidate)
            and abs(candidate - float(rate)) <= 1e-7
            and residual is not None
            and isfinite(residual)
            and abs(residual) <= 1e-6
        ):
            verified += 1
    return verified, True


@_calculation
def calculate_returns(source: ReturnsInput, *, calc_id: str, code_version: str) -> CalcResult:
    rates, infinite, residual = _root_rates(source)
    unique = len(rates) == 1 and not infinite
    ambiguous = len(rates) > 1 or infinite
    contributions = sum((-amount for amount in source.cash_flows if amount < 0), ZERO)
    distributions = sum((amount for amount in source.cash_flows if amount > 0), ZERO)
    mirr = _mirr(source)
    verified, supported = _backend_checks(source, rates)
    outputs = {
        "root_count": Decimal(len(rates)),
        "unique": Decimal(unique),
        "ambiguous": Decimal(ambiguous),
        "undefined": Decimal(not unique and not ambiguous),
        "infinitely_many_roots": Decimal(infinite),
        "max_relative_npv_residual": residual,
        "pyxirr_verified_roots": Decimal(verified),
        "pyxirr_supported": Decimal(supported),
        "total_contributions": contributions,
        "total_distributions": distributions,
        "equity_multiple_defined": Decimal(bool(contributions)),
        "mirr_defined": Decimal(mirr is not None),
        **{f"root:{i}": rate for i, rate in enumerate(rates)},
    }
    if contributions:
        outputs["equity_multiple"] = distributions / contributions
    if mirr is not None:
        outputs["mirr"] = mirr
    if unique:
        outputs["xirr" if source.dates is not None else "irr"] = rates[0]
        outputs["reported_return"] = rates[0]
    elif ambiguous and mirr is not None and not infinite:
        outputs["reported_return"] = mirr
    return CalcResult(
        calc_id=calc_id,
        fn="calculate_returns",
        inputs={"cash_flows": source.input_id},
        outputs=outputs,
        code_version=code_version,
    )


@_calculation
def excel_npv(source: NPVInput, *, calc_id: str, code_version: str) -> CalcResult:
    def exact(amount: Decimal) -> Fraction:
        digits = amount.as_tuple()
        if amount and len(digits.digits) + abs(int(digits.exponent)) > 4096:
            raise ValueError("NPV input exceeds the exact arithmetic complexity budget")
        return Fraction(amount)

    discount = Fraction(1) / (1 + exact(source.discount_rate))
    rational = Fraction(0)
    for amount in reversed(source.cash_flows):
        rational = (rational + exact(amount)) * discount
        if max(rational.numerator.bit_length(), rational.denominator.bit_length()) > 65536:
            raise ValueError("NPV exact arithmetic exceeds the rational complexity budget")
    value = Decimal(rational.numerator) / Decimal(rational.denominator)
    scale = max(abs(amount) for amount in source.cash_flows)
    normalized = [float(amount / scale) if scale else 0.0 for amount in source.cash_flows]
    binary_rate = float(source.discount_rate)
    supported = (
        isfinite(binary_rate)
        and (source.discount_rate == 0 or binary_rate != 0)
        and all(
            isfinite(binary) and (amount == 0 or binary != 0)
            for binary, amount in zip(normalized, source.cash_flows, strict=True)
        )
    )
    backend = pyxirr.npv(binary_rate, normalized, start_from_zero=False) if supported else None
    consistent = (
        supported
        and backend is not None
        and isfinite(backend)
        and abs(Decimal.from_float(backend) * scale - value) <= Decimal("1e-9") * abs(value)
    )
    return CalcResult(
        calc_id=calc_id,
        fn="excel_npv",
        inputs={"cash_flows": source.input_id},
        outputs={"npv": value, "pyxirr_consistent": Decimal(consistent)},
        code_version=code_version,
    )


@_calculation
def cash_on_cash(source: CashOnCashInput, *, calc_id: str, code_version: str) -> CalcResult:
    return CalcResult(
        calc_id=calc_id,
        fn="cash_on_cash",
        inputs={"cash_on_cash": source.input_id},
        outputs={"cash_on_cash": source.annual_operating_cash_flow / source.invested_equity},
        code_version=code_version,
    )
