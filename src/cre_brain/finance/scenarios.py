"""Bounded correlated downside, grid sensitivities, fragility and price inversion.

Correlation is on signed latent shocks in the supplied range order, not a claim
about empirical post-truncation correlations. Exact rational LDL validates PSD;
Decimal square roots transform seeded integer PRNG draws. Row L1 normalization
bounds shocks without clipping tails. Rejection into the adverse orthant yields
joint downside; impossible/rare orthants fail after a bounded attempt budget.
P10/base/P90 interpolate exactly before 28-digit output rounding and endpoint
clamping. No normal tails or binary64 financial arithmetic are used.

Fragility margin means absolute base-return distance to the policy target (return
percentage points). Equality at target is GO; equality at fragility_margin is NOT
conditional. A flip outside any range remains a sensitivity, never a condition.

Price inversion supports conventional equity flows only: initial equity grows
strictly with price, later cash flows are nonnegative and at least one is positive.
This proves monotonicity and excludes ambiguous IRRs. Bisection brackets target
dated NPV and then certifies the achieved XIRR/tolerance using the returns core.
Nonconventional flows, unbracketed solutions and unresolved tolerances fail closed.

Assumptions and shocks have canonical keys: assumption:[index,"name"] and
shock:[index,"name"], with compact ASCII JSON encoding of the index/name pair.
These namespaces cannot overlap legacy cell/scenario keys, even for names with
colons, quotes or Unicode. Unambiguous legacy aliases remain available; an
ambiguous joint alias is omitted, and the grid metric always owns its legacy key.
Every value remains available canonically, so collisions never discard data.
"""

from collections.abc import Callable
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import product
from json import dumps
from math import prod
from random import Random
from typing import Literal, Self

from pydantic import Field, TypeAdapter, model_validator

from cre_brain.domain import CalcResult
from cre_brain.domain.base import Identifier
from cre_brain.domain.models import DomainModel
from cre_brain.finance._arithmetic import dated_value, decimal_value, working_precision
from cre_brain.finance._context import _calculation
from cre_brain.finance.proforma import NonnegativeDecimal
from cre_brain.finance.returns import DateOnly, FiniteDecimal, PositiveDecimal, Rate
from cre_brain.finance.waterfall import DatedEquityFlow, _return_outputs


class AssumptionRange(DomainModel):
    input_id: Identifier
    name: Identifier
    p10: FiniteDecimal
    base: FiniteDecimal
    p90: FiniteDecimal
    downside: Literal["increase", "decrease"]

    @model_validator(mode="after")
    def ordered_range(self) -> Self:
        if not self.p10 <= self.base <= self.p90:
            raise ValueError("Assumptions require P10 <= base <= P90")
        if self.p10 == self.p90:
            raise ValueError("An assumption range needs a nonzero width")
        return self


class SensitivityInput(DomainModel):
    input_id: Identifier
    ranges: tuple[AssumptionRange, ...] = Field(min_length=1, max_length=20)
    axes: dict[str, tuple[FiniteDecimal, ...]]
    metric_key: Identifier


class JointScenarioInput(DomainModel):
    input_id: Identifier
    ranges: tuple[AssumptionRange, ...] = Field(min_length=1, max_length=20)
    correlation: tuple[tuple[FiniteDecimal, ...], ...]
    seed: int = Field(strict=True, ge=0, le=2**64 - 1)
    count: int = Field(strict=True, ge=1, le=1000)
    max_attempts: int = Field(strict=True, ge=1, le=100000)


class EvaluatedScenario(DomainModel):
    input_id: Identifier
    assumptions: dict[str, FiniteDecimal]
    result: CalcResult


class FragilityInput(DomainModel):
    input_id: Identifier
    ranges: tuple[AssumptionRange, ...] = Field(min_length=1, max_length=20)
    metric_key: Identifier
    target: FiniteDecimal
    fragility_margin: NonnegativeDecimal


class PriceSolveInput(DomainModel):
    input_id: Identifier
    close_date: DateOnly
    future_flows: tuple[DatedEquityFlow, ...] = Field(min_length=1, max_length=599)
    lower_price: PositiveDecimal
    upper_price: PositiveDecimal
    acquisition_cost_rate: NonnegativeDecimal
    fixed_costs: NonnegativeDecimal
    debt_proceeds: NonnegativeDecimal
    target_return: Rate = Field(gt=Decimal("-.99"), lt=10)
    return_tolerance: PositiveDecimal
    price_tolerance: PositiveDecimal
    max_iterations: int = Field(strict=True, ge=1, le=1024)


def _ranges(ranges: tuple[AssumptionRange, ...]) -> dict[str, AssumptionRange]:
    result = {r.name: r for r in ranges}
    if len(result) != len(ranges):
        raise ValueError("Assumption range names must be unique")
    working_precision([v for r in ranges for v in (r.p10, r.base, r.p90)])
    return result


def _metric(result: CalcResult, key: str, input_id: str | None = None) -> Decimal:
    if not result.inputs or any(not v.strip() for v in result.inputs.values()):
        raise ValueError("Metric calculations require stored input provenance")
    if input_id is not None and input_id not in result.inputs.values():
        raise ValueError("Metric calculation provenance does not reference scenario input")
    prefix = key.rsplit(":", 1)[0] + ":" if ":" in key else ""
    if any(
        result.outputs.get(prefix + flag, Decimal(0)) != 0
        for flag in ("ambiguous", "undefined", "infinitely_many_roots")
    ):
        raise ValueError("An ambiguous or undefined return cannot drive a recommendation")
    try:
        value = result.outputs[key]
    except KeyError as error:
        raise ValueError(f"Metric calculation is missing {key!r}") from error
    if not value.is_finite():
        raise ValueError("Metric must be finite")
    working_precision([value])
    return value


def _immutable_result(known: dict[str, CalcResult], result: CalcResult, aggregate_id: str) -> None:
    if result.calc_id == aggregate_id or aggregate_id in result.inputs.values():
        raise ValueError("An aggregate calculation ID cannot alias or feed an evaluator result")
    previous = known.get(result.calc_id)
    if previous is not None and previous != result:
        raise ValueError("A stored calculation ID is immutable across evaluations")
    known[result.calc_id] = result.model_copy(deep=True)


def _check_aggregate_inputs(inputs: dict[str, str], aggregate_id: str) -> None:
    if aggregate_id in inputs.values():
        raise ValueError("An aggregate calculation cannot reference itself in input provenance")


def _canonical_key(kind: str, index: int, name: str) -> str:
    return kind + ":" + dumps([index, name], ensure_ascii=True, separators=(",", ":"))


@_calculation
def sensitivity_grid(
    source: SensitivityInput,
    evaluator: Callable[[dict[str, Decimal]], CalcResult],
    *,
    calc_id: str,
    code_version: str,
) -> CalcResult:
    calc_id = TypeAdapter(Identifier).validate_python(calc_id)
    ranges = _ranges(source.ranges)
    if set(source.axes) != set(ranges):
        raise ValueError("Grid axes must exactly match assumption range names")
    if (
        any(not values for values in source.axes.values())
        or prod(len(v) for v in source.axes.values()) > 4096
    ):
        raise ValueError("Sensitivity grid must contain 1–4096 cells")
    for name, values in source.axes.items():
        working_precision(list(values))
        if any(not ranges[name].p10 <= v <= ranges[name].p90 for v in values):
            raise ValueError(f"Sensitivity axis {name!r} is outside its P10–P90 range")
    inputs = {"grid": source.input_id, **{f"range:{r.name}": r.input_id for r in source.ranges}}
    outputs = {"cell_count": Decimal(prod(len(v) for v in source.axes.values()))}
    names = tuple(ranges)
    known: dict[str, CalcResult] = {}
    for index, values in enumerate(product(*(source.axes[name] for name in names))):
        assumptions = dict(zip(names, values, strict=True))
        result = evaluator(assumptions.copy())
        _immutable_result(known, result, calc_id)
        outputs[f"cell:{index}:metric"] = _metric(result, source.metric_key, source.input_id)
        inputs[f"cell:{index}:result"] = result.calc_id
        for name, value in assumptions.items():
            outputs[_canonical_key("assumption", index, name)] = value
            if name != "metric":
                outputs[f"cell:{index}:{name}"] = value
    _check_aggregate_inputs(inputs, calc_id)
    return CalcResult(
        calc_id=calc_id,
        fn="sensitivity_grid",
        inputs=inputs,
        outputs=outputs,
        code_version=code_version,
    )


def _correlation_factor(source: JointScenarioInput, precision: int) -> list[list[Decimal]]:
    n = len(source.ranges)
    matrix = source.correlation
    if len(matrix) != n or any(len(row) != n for row in matrix):
        raise ValueError("The correlation matrix must match the range dimensions")
    if any(matrix[i][i] != 1 for i in range(n)) or any(
        abs(matrix[i][j]) > 1 or matrix[i][j] != matrix[j][i] for i in range(n) for j in range(n)
    ):
        raise ValueError("The correlation matrix must be symmetric with unit diagonal")
    lower = [[Fraction(0) for _ in range(n)] for _ in range(n)]
    diagonal = [Fraction(0) for _ in range(n)]
    for i in range(n):
        lower[i][i] = Fraction(1)
        for j in range(i):
            residual = Fraction(matrix[i][j]) - sum(
                (lower[i][k] * lower[j][k] * diagonal[k] for k in range(j)), Fraction(0)
            )
            if diagonal[j] == 0:
                if residual:
                    raise ValueError("The correlation matrix must be positive semidefinite")
            else:
                lower[i][j] = residual / diagonal[j]
        diagonal[i] = Fraction(1) - sum(
            (lower[i][k] ** 2 * diagonal[k] for k in range(i)), Fraction(0)
        )
        if diagonal[i] < 0:
            raise ValueError("The correlation matrix must be positive semidefinite")
    with localcontext() as context:
        context.prec = precision
        return [
            [
                decimal_value(lower[i][j], precision) * decimal_value(diagonal[j], precision).sqrt()
                for j in range(n)
            ]
            for i in range(n)
        ]


@_calculation
def joint_downside_scenarios(
    source: JointScenarioInput,
    *,
    calc_id: str,
    code_version: str,
) -> CalcResult:
    ranges = _ranges(source.ranges)
    # Decide aliases from the complete namespace before writing any values.
    ambiguous = set(ranges) & {"shock:" + name for name in ranges}
    precision = working_precision(
        [v for r in source.ranges for v in (r.p10, r.base, r.p90)]
        + [v for row in source.correlation for v in row]
    )
    outputs: dict[str, Decimal] = {}
    random = Random(source.seed)
    accepted = 0
    attempts = 0
    with localcontext() as context:
        context.prec = precision
        factor = _correlation_factor(source, precision)
        norms = [sum((abs(v) for v in row), Decimal(0)) for row in factor]
        while accepted < source.count and attempts < source.max_attempts:
            attempts += 1
            latent = [
                Decimal(random.getrandbits(64)) * 2 / Decimal(2**64 - 1) - 1 for _ in source.ranges
            ]
            signed = [
                sum((v * u for v, u in zip(row, latent, strict=True)), Decimal(0)) / norm
                for row, norm in zip(factor, norms, strict=True)
            ]
            adverse = [
                v if r.downside == "increase" else -v
                for r, v in zip(source.ranges, signed, strict=True)
            ]
            if any(v <= 0 for v in adverse):
                continue
            for r, shock in zip(source.ranges, adverse, strict=True):
                if shock > 1:
                    raise ValueError("A normalized correlation shock exceeded its bound")
                endpoint = r.p90 if r.downside == "increase" else r.p10
                value = decimal_value(
                    Fraction(r.base) + Fraction(shock) * (Fraction(endpoint) - Fraction(r.base))
                )
                value = min(r.p90, max(r.p10, value))
                shock_value = decimal_value(Fraction(shock))
                outputs[_canonical_key("assumption", accepted, r.name)] = value
                outputs[_canonical_key("shock", accepted, r.name)] = shock_value
                if r.name not in ambiguous:
                    outputs[f"scenario:{accepted}:{r.name}"] = value
                if "shock:" + r.name not in ambiguous:
                    outputs[f"scenario:{accepted}:shock:{r.name}"] = shock_value
            accepted += 1
    if accepted != source.count:
        raise ValueError("Could not generate joint downside within the bounded attempt budget")
    outputs.update(
        scenario_count=Decimal(accepted), attempts=Decimal(attempts), seed=Decimal(source.seed)
    )
    return CalcResult(
        calc_id=calc_id,
        fn="joint_downside_scenarios",
        inputs={
            "joint_scenarios": source.input_id,
            **{f"range:{r.name}": r.input_id for r in source.ranges},
        },
        outputs=outputs,
        code_version=code_version,
    )


@_calculation
def assess_fragility(
    source: FragilityInput,
    base: CalcResult,
    scenarios: tuple[EvaluatedScenario, ...],
    *,
    calc_id: str,
    code_version: str,
) -> CalcResult:
    calc_id = TypeAdapter(Identifier).validate_python(calc_id)
    ranges = _ranges(source.ranges)
    if not 1 <= len(scenarios) <= 4096:
        raise ValueError("Fragility requires 1–4096 evaluated scenarios")
    base_value = _metric(base, source.metric_key)
    working_precision([base_value, source.target, source.fragility_margin])
    base_go = base_value >= source.target
    margin = abs(Fraction(base_value) - Fraction(source.target))
    inputs = {
        "fragility_policy": source.input_id,
        "base_result": base.calc_id,
        **{f"range:{r.name}": r.input_id for r in source.ranges},
    }
    outputs = {"base_go": Decimal(base_go), "margin_to_flip": decimal_value(margin)}
    flip = False
    known: dict[str, CalcResult] = {}
    _immutable_result(known, base, calc_id)
    scenario_ids: set[str] = set()
    for i, scenario in enumerate(scenarios):
        if scenario.input_id in scenario_ids:
            raise ValueError("Evaluated scenario input IDs must be unique")
        scenario_ids.add(scenario.input_id)
        if set(scenario.assumptions) != set(ranges):
            raise ValueError("Scenario assumptions must exactly cover every policy range")
        working_precision(list(scenario.assumptions.values()))
        value = _metric(scenario.result, source.metric_key, scenario.input_id)
        _immutable_result(known, scenario.result, calc_id)
        within = all(
            ranges[name].p10 <= value <= ranges[name].p90
            for name, value in scenario.assumptions.items()
        )
        adverse = all(
            value <= ranges[name].base
            if ranges[name].downside == "decrease"
            else value >= ranges[name].base
            for name, value in scenario.assumptions.items()
        ) and any(value != ranges[name].base for name, value in scenario.assumptions.items())
        changed = (value >= source.target) != base_go
        flip |= within and adverse and changed
        inputs[f"scenario:{i}"] = scenario.input_id
        inputs[f"scenario:{i}:result"] = scenario.result.calc_id
        outputs.update(
            {
                f"scenario:{i}:within_ranges": Decimal(within),
                f"scenario:{i}:joint_downside": Decimal(adverse),
                f"scenario:{i}:flipped": Decimal(changed),
                f"scenario:{i}:metric": value,
            }
        )
    conditional = flip and margin < Fraction(source.fragility_margin)
    outputs.update(
        flip_within_ranges=Decimal(flip),
        conditional=Decimal(conditional),
        sensitivity_only=Decimal(not conditional),
    )
    _check_aggregate_inputs(inputs, calc_id)
    return CalcResult(
        calc_id=calc_id,
        fn="assess_fragility",
        inputs=inputs,
        outputs=outputs,
        code_version=code_version,
    )


@_calculation
def max_supportable_price(
    source: PriceSolveInput,
    *,
    calc_id: str,
    code_version: str,
) -> CalcResult:
    if source.lower_price >= source.upper_price:
        raise ValueError("Price solver requires an increasing bracket")
    if any(f.date <= source.close_date or f.amount < 0 for f in source.future_flows) or not any(
        f.amount > 0 for f in source.future_flows
    ):
        raise ValueError("Price solving requires conventional positive future dated equity flows")
    precision = working_precision(
        [
            source.lower_price,
            source.upper_price,
            source.acquisition_cost_rate,
            source.fixed_costs,
            source.debt_proceeds,
            source.target_return,
            source.return_tolerance,
            source.price_tolerance,
        ]
        + [f.amount for f in source.future_flows]
    )
    multiplier = 1 + Fraction(source.acquisition_cost_rate)
    fixed = Fraction(source.fixed_costs) - Fraction(source.debt_proceeds)
    equity_lower = Fraction(source.lower_price) * multiplier + fixed
    if equity_lower <= 0:
        raise ValueError("Lower price must require positive invested equity")
    future = [(f.date, Fraction(f.amount)) for f in source.future_flows]
    pv = Fraction(dated_value(future, source.target_return, source.close_date, precision))
    lower, upper = Fraction(source.lower_price), Fraction(source.upper_price)
    if pv - (lower * multiplier + fixed) < 0 or pv - (upper * multiplier + fixed) > 0:
        raise ValueError("Target return is not bracketed by the supplied prices")
    final: dict[str, Decimal] | None = None
    for iteration in range(source.max_iterations):
        low_gap = pv - (lower * multiplier + fixed)
        high_gap = pv - (upper * multiplier + fixed)
        exact = lower if low_gap == 0 else upper if high_gap == 0 else None
        if exact is not None or upper - lower <= Fraction(source.price_tolerance):
            price = decimal_value(exact if exact is not None else lower)
            if Fraction(price) * multiplier + fixed > pv:
                price = price.next_minus()
            equity = Fraction(price) * multiplier + fixed
            returns = _return_outputs(
                [(source.close_date, -equity), *future],
                source.target_return,
                source.target_return,
                source.input_id,
                calc_id,
                code_version,
            )
            if returns["unique"] != 1 or "xirr" not in returns:
                raise ValueError("Price solution does not have a certified unique XIRR")
            achieved = returns["xirr"]
            error = Fraction(achieved) - Fraction(source.target_return)
            if abs(error) <= Fraction(source.return_tolerance) and error >= 0:
                final = {
                    "max_price": price,
                    "achieved_return": achieved,
                    "return_error": decimal_value(error),
                    "target_return": source.target_return,
                    "target_npv": decimal_value(pv - equity),
                    "invested_equity": decimal_value(equity),
                    "bracket_lower": decimal_value(lower),
                    "bracket_upper": decimal_value(upper),
                    "iterations": Decimal(iteration + 1),
                }
                break
            if exact is not None:
                raise ValueError("Endpoint return cannot meet the requested output tolerance")
        middle = (lower + upper) / 2
        if pv - (middle * multiplier + fixed) >= 0:
            lower = middle
        else:
            upper = middle
    if final is None:
        raise ValueError("Price solver did not converge within the iteration/tolerance budget")
    return CalcResult(
        calc_id=calc_id,
        fn="max_supportable_price",
        inputs={
            "price_model": source.input_id,
            **{f"flow:{i}": f.input_id for i, f in enumerate(source.future_flows)},
        },
        outputs=final,
        code_version=code_version,
    )
