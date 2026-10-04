"""Decimal returns with explicit IRR ambiguity in the open (-0.99, 10) domain.

In discount factor q=1/(1+r), dated NPV is a generalized polynomial.
Removing its lowest power and recursively isolating derivative roots gives
monotone brackets, including stationary/tangent roots; a sampling grid cannot.
Dated calculations use ACT/365 fixed, aggregate repeated dates and sort them.

pyxirr 0.10.8 IRR/XIRR and Excel-timed NPV are cross-checks, not the authority
for root count. Only normalized cash flows/rates cross its binary64 boundary.
Authoritative monetary arithmetic is 28-digit Decimal; root isolation uses
80–256 digits and returns rates rounded to 28 digits with residual diagnostics.
Working precision covers the full nonzero input exponent span, sum growth
and 40 guard digits, so repeated-date aggregation is exact in any input order.
No pyxirr float is converted into authoritative money or a reported root.
Unresolvable precision/complexity fails closed rather than inventing an IRR.
"""

from datetime import date
from decimal import Decimal, localcontext
from math import isfinite
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
        return 0
    return 1 if value > 0 else -1


def _bisect(terms: Terms, left: Decimal, right: Decimal, epsilon: Decimal) -> Decimal:
    left_sign = _sign(*_evaluate(terms, left), epsilon)
    for _ in range(4 * max(0, -epsilon.adjusted()) + 400):
        middle = (left + right) / 2
        if middle == left or middle == right:
            return middle
        middle_sign = _sign(*_evaluate(terms, middle), epsilon)
        if middle_sign == 0:
            return middle
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
    roots = [point for point, sign in zip(points[1:-1], values[1:-1], strict=True) if sign == 0]
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
        by_time: dict[Decimal, Decimal] = {}
        for time, amount in zip(_times(source), source.cash_flows, strict=True):
            by_time[time] = by_time.get(time, ZERO) + amount
        terms = sorted((time, amount) for time, amount in by_time.items() if amount)
        if not terms:
            return [], True, ZERO
        signs = [coefficient > 0 for _, coefficient in terms]
        changes = sum(a != b for a, b in zip(signs, signs[1:], strict=False))
        if changes > 1 and len(terms) > 128:
            raise ValueError(
                "Nonconventional IRR supports at most 128 distinct nonzero dates/periods"
            )
        low, high = ONE / (ONE + HIGH_RATE), ONE / (ONE + LOW_RATE)
        epsilon = Decimal(10) ** (-precision + 12)
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
    discount = ONE / (ONE + source.discount_rate)
    value = ZERO
    for amount in reversed(source.cash_flows):
        value = (value + amount) * discount
    scale = max(abs(amount) for amount in source.cash_flows)
    normalized = [float(amount / scale) if scale else 0.0 for amount in source.cash_flows]
    binary_rate = float(source.discount_rate)
    supported = isfinite(binary_rate) and all(isfinite(amount) for amount in normalized)
    backend = pyxirr.npv(binary_rate, normalized, start_from_zero=False) if supported else None
    consistent = (
        supported
        and backend is not None
        and isfinite(backend)
        and (abs(backend - float(value / scale if scale else ZERO)) <= 1e-9 * max(1, abs(backend)))
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
