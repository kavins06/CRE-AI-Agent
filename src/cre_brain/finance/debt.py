"""Monthly debt: scheduled amortization is separate from an explicit maturity balloon.

Fixed rates are base plus spread; no forward floating-rate curve is implied.
IO delays the start of the stated amortization period. DSCR sizing uses the
post-IO payment (or the IO payment for a fully IO term), not the balloon.
Quotes rank borrower effective annual yield, including fees and early payoff.
Dates are contractual monthly anniversaries, clamped to the month's last day.
"""

from calendar import monthrange
from datetime import date
from decimal import Decimal, getcontext, localcontext
from fractions import Fraction
from typing import Annotated, Self

from pydantic import BeforeValidator, Field, model_validator

from cre_brain.domain import CalcResult
from cre_brain.domain.base import Identifier
from cre_brain.domain.models import DomainModel
from cre_brain.finance._context import _calculation
from cre_brain.finance.proforma import NonnegativeDecimal, Ratio, _reject_float

PositiveDecimal = Annotated[Decimal, BeforeValidator(_reject_float), Field(gt=0)]
ZERO = Decimal(0)
ONE = Decimal(1)
TWELVE = Decimal(12)


class LoanTerms(DomainModel):
    input_id: Identifier
    base_rate: NonnegativeDecimal
    spread: NonnegativeDecimal
    term_months: int = Field(strict=True, ge=1, le=600)
    amortization_months: int = Field(strict=True, ge=1, le=600)
    io_months: int = Field(strict=True, ge=0, le=600)
    fee_rate: Ratio
    fixed_fee: NonnegativeDecimal
    prepayment_rate: Ratio

    @model_validator(mode="after")
    def valid_io(self) -> Self:
        if self.io_months > self.term_months:
            raise ValueError("IO months cannot exceed the loan term")
        return self


class LoanInput(DomainModel):
    input_id: Identifier
    principal: PositiveDecimal
    close_date: date
    annual_noi: NonnegativeDecimal | None = None


class QuoteComparisonInput(DomainModel):
    input_id: Identifier
    payoff_month: int = Field(strict=True, ge=1, le=600)


class DebtSizingInput(DomainModel):
    input_id: Identifier
    property_value: PositiveDecimal
    annual_noi: NonnegativeDecimal
    max_ltv: Ratio
    min_dscr: PositiveDecimal
    min_debt_yield: PositiveDecimal


class RefinanceInput(DomainModel):
    input_id: Identifier
    refinance_date: date
    new_principal: PositiveDecimal


def _payment(principal: Decimal, rate: Decimal, months: int) -> Decimal:
    if not rate:
        return principal / months
    discount = ONE / (ONE + rate)
    annuity = ZERO
    for _ in range(months):
        annuity = (annuity + ONE) * discount
    return principal / annuity


def _monthly_rate(terms: LoanTerms) -> Decimal:
    return (terms.base_rate + terms.spread) / TWELVE


def _anniversary(start: date, month: int) -> date:
    year, offset = divmod(start.year * 12 + start.month - 1 + month, 12)
    target_month = offset + 1
    return date(year, target_month, min(start.day, monthrange(year, target_month)[1]))


def _scheduled_payment(principal: Decimal, terms: LoanTerms) -> Decimal:
    rate = _monthly_rate(terms)
    if terms.io_months == terms.term_months:
        return principal * rate
    return _payment(principal, rate, terms.amortization_months)


def _schedule(loan: LoanInput, terms: LoanTerms) -> dict[str, Decimal]:
    rate = _monthly_rate(terms)
    payment = _payment(loan.principal, rate, terms.amortization_months)
    balance = loan.principal
    outputs: dict[str, Decimal] = {}
    total_interest = ZERO
    total_principal = ZERO
    balloon = ZERO
    for month in range(1, terms.term_months + 1):
        opening = balance
        interest = opening * rate
        principal = (
            ZERO if month <= terms.io_months else min(opening, max(ZERO, payment - interest))
        )
        # Remove the finite-precision residue only at contractual amortization completion.
        if month == terms.io_months + terms.amortization_months:
            principal = opening
        scheduled = interest + principal
        balance = opening - principal
        outstanding = balance
        balloon = balance if month == terms.term_months else ZERO
        balance -= balloon
        values = {
            "opening_balance": opening,
            "interest": interest,
            "scheduled_principal": principal,
            "scheduled_payment": scheduled,
            "balance_before_balloon": outstanding,
            "balloon_principal": balloon,
            "total_payment": scheduled + balloon,
            "ending_balance": balance,
            "payment_date_ordinal": Decimal(_anniversary(loan.close_date, month).toordinal()),
        }
        outputs.update({f"month:{month}:{key}": value for key, value in values.items()})
        total_interest += interest
        total_principal += principal
    outputs.update(
        total_interest=total_interest,
        scheduled_principal=total_principal,
        balloon_payoff=balloon,
        stabilized_annual_debt_service=_scheduled_payment(loan.principal, terms) * TWELVE,
    )
    return outputs


@_calculation
def size_debt(
    assumptions: DebtSizingInput, terms: LoanTerms, *, calc_id: str, code_version: str
) -> CalcResult:
    ltv_limit = assumptions.property_value * assumptions.max_ltv
    yield_limit = assumptions.annual_noi / assumptions.min_debt_yield
    annual_constant = _scheduled_payment(ONE, terms) * TWELVE
    dscr_possible = bool(annual_constant)
    dscr_limit = (
        assumptions.annual_noi / assumptions.min_dscr / annual_constant
        if dscr_possible
        else min(ltv_limit, yield_limit)
    )
    amount = min(ltv_limit, yield_limit, dscr_limit)
    service = amount * annual_constant
    return CalcResult(
        calc_id=calc_id,
        fn="size_debt",
        inputs={"sizing": assumptions.input_id, "terms": terms.input_id},
        outputs={
            "ltv_limit": ltv_limit,
            "dscr_limit": dscr_limit,
            "debt_yield_limit": yield_limit,
            "dscr_limit_binding_possible": Decimal(dscr_possible),
            "loan_amount": amount,
            "annual_debt_service": service,
            "dscr_defined": Decimal(bool(service)),
            **({"dscr": assumptions.annual_noi / service} if service else {}),
        },
        code_version=code_version,
    )


@_calculation
def amortize_debt(
    loan: LoanInput,
    terms: LoanTerms,
    *,
    calc_id: str,
    code_version: str,
) -> CalcResult:
    outputs = _schedule(loan, terms)
    service = outputs["stabilized_annual_debt_service"]
    outputs["dscr_defined"] = Decimal(loan.annual_noi is not None and bool(service))
    if loan.annual_noi is not None and service:
        outputs["dscr"] = loan.annual_noi / service
    return CalcResult(
        calc_id=calc_id,
        fn="amortize_debt",
        inputs={"loan": loan.input_id, "terms": terms.input_id},
        outputs=outputs,
        code_version=code_version,
    )


def _cost(proceeds: Decimal, payments: list[Decimal]) -> Decimal:
    def residual(rate: Decimal) -> Decimal:
        discount = ONE / (ONE + rate)
        pv = ZERO
        for payment in reversed(payments):
            pv = (pv + payment) * discount
        return pv - proceeds

    if residual(ZERO) == 0:
        return ZERO
    low = ZERO
    high = max(ONE, Decimal(2) * sum(payments, ZERO) / proceeds)
    if residual(high) > 0:
        raise ValueError("Effective cost could not be bracketed at declared precision")
    iterations = 4 * (getcontext().prec + max(0, high.adjusted()))
    for _ in range(iterations):
        mid = (low + high) / 2
        if mid == low or mid == high:
            break
        if residual(mid) > 0:
            low = mid
        else:
            high = mid
    return (ONE + (low + high) / 2) ** 12 - ONE


def _payoff_month(terms: LoanTerms, requested: int | None) -> int:
    month = terms.term_months if requested is None else requested
    if type(month) is not int or not 1 <= month <= terms.term_months:
        raise ValueError("Payoff month must be a payment month within every quoted term")
    return month


@_calculation
def compare_debt_quotes(
    loan: LoanInput,
    quotes: list[LoanTerms],
    *,
    comparison: QuoteComparisonInput | None = None,
    calc_id: str,
    code_version: str,
) -> CalcResult:
    if not quotes or len({quote.input_id for quote in quotes}) != len(quotes):
        raise ValueError("Provide one or more quotes with unique input IDs")
    inputs = {"loan": loan.input_id}
    if comparison is not None:
        inputs["comparison"] = comparison.input_id
    outputs: dict[str, Decimal] = {}
    costs: list[tuple[Decimal, str]] = []
    amounts = [
        ONE,
        loan.principal,
        *(
            value
            for quote in quotes
            for value in (
                quote.base_rate,
                quote.spread,
                quote.fee_rate,
                quote.fixed_fee,
                quote.prepayment_rate,
            )
            if value
        ),
    ]
    precision = max(
        80,
        max(value.adjusted() for value in amounts)
        - min(int(value.as_tuple().exponent) for value in amounts)
        + len(str(len(amounts)))
        + 41,
    )
    if precision > 256:
        raise ValueError("Quote exponent span requires more than 256 precision digits")
    with localcontext() as context:
        context.prec = precision
        for quote in quotes:
            month = _payoff_month(
                quote, comparison.payoff_month if comparison is not None else None
            )
            schedule = _schedule(loan, quote)
            exact_fees = Fraction(loan.principal) * Fraction(quote.fee_rate) + Fraction(
                quote.fixed_fee
            )
            exact_proceeds = Fraction(loan.principal) - exact_fees
            if exact_proceeds <= 0:
                raise ValueError("Quote fees must leave positive net proceeds")
            fees = Decimal(exact_fees.numerator) / Decimal(exact_fees.denominator)
            proceeds = Decimal(exact_proceeds.numerator) / Decimal(exact_proceeds.denominator)
            balance = schedule[f"month:{month}:balance_before_balloon"]
            prepay = balance * quote.prepayment_rate if month < quote.term_months else ZERO
            payments = [schedule[f"month:{m}:scheduled_payment"] for m in range(1, month + 1)]
            payments[-1] += balance + prepay
            cost = _cost(proceeds, payments)
            costs.append((cost, quote.input_id))
            inputs[f"quote:{quote.input_id}"] = quote.input_id
            values = {
                "effective_annual_cost": cost,
                "fees": fees,
                "prepayment_fee": prepay,
                "balloon_payoff": balance,
                "net_proceeds": proceeds,
                "total_payments": sum(payments, ZERO),
                "payoff_month": Decimal(month),
                "annual_rate": quote.base_rate + quote.spread,
                "io_months": Decimal(quote.io_months),
                "amortization_months": Decimal(quote.amortization_months),
                "term_months": Decimal(quote.term_months),
            }
            outputs.update(
                {f"quote:{quote.input_id}:{key}": value for key, value in values.items()}
            )
    for rank, (_, identifier) in enumerate(sorted(costs), 1):
        outputs[f"quote:{identifier}:rank"] = Decimal(rank)
    return CalcResult(
        calc_id=calc_id,
        fn="compare_debt_quotes",
        inputs=inputs,
        outputs={key: +value for key, value in outputs.items()},
        code_version=code_version,
    )


@_calculation
def refinance_debt(
    loan: LoanInput,
    old_terms: LoanTerms,
    refinance: RefinanceInput,
    new_terms: LoanTerms,
    *,
    calc_id: str,
    code_version: str,
) -> CalcResult:
    month = (
        (refinance.refinance_date.year - loan.close_date.year) * 12
        + refinance.refinance_date.month
        - loan.close_date.month
    )
    if not 1 <= month <= old_terms.term_months or (
        _anniversary(loan.close_date, month) != refinance.refinance_date
    ):
        raise ValueError("Refinance must occur on a contractual payment date within the old term")
    schedule = _schedule(loan, old_terms)
    balance = schedule[f"month:{month}:balance_before_balloon"]
    prepay = balance * old_terms.prepayment_rate if month < old_terms.term_months else ZERO
    fees = refinance.new_principal * new_terms.fee_rate + new_terms.fixed_fee
    if fees >= refinance.new_principal:
        raise ValueError("New loan fees must leave positive net proceeds")
    new_loan = LoanInput(
        input_id=refinance.input_id,
        principal=refinance.new_principal,
        close_date=refinance.refinance_date,
    )
    outputs = {
        "old_balance_payoff": balance,
        "old_prepayment_fee": prepay,
        "new_fees": fees,
        "new_principal": refinance.new_principal,
        "cash_out": refinance.new_principal - balance - prepay - fees,
        "refinance_date_ordinal": Decimal(refinance.refinance_date.toordinal()),
        **{f"new:{key}": value for key, value in _schedule(new_loan, new_terms).items()},
    }
    return CalcResult(
        calc_id=calc_id,
        fn="refinance_debt",
        inputs={
            "loan": loan.input_id,
            "old_terms": old_terms.input_id,
            "refinance": refinance.input_id,
            "new_terms": new_terms.input_id,
        },
        outputs=outputs,
        code_version=code_version,
    )
