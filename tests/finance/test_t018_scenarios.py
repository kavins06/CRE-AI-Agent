from datetime import date, timedelta
from decimal import ROUND_DOWN, Decimal, Inexact, getcontext, localcontext

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from cre_brain.domain import CalcResult
from cre_brain.finance.scenarios import (
    AssumptionRange,
    EvaluatedScenario,
    FragilityInput,
    JointScenarioInput,
    PriceSolveInput,
    SensitivityInput,
    assess_fragility,
    joint_downside_scenarios,
    max_supportable_price,
    sensitivity_grid,
)
from cre_brain.finance.waterfall import DatedEquityFlow

D = Decimal
META = {"calc_id": "calc", "code_version": "test"}
START = date(2023, 1, 1)


def ranges():
    return (
        AssumptionRange(
            input_id="rent_range",
            name="rent",
            p10=D(80),
            base=D(100),
            p90=D(120),
            downside="decrease",
        ),
        AssumptionRange(
            input_id="cap_range",
            name="cap",
            p10=D(".04"),
            base=D(".05"),
            p90=D(".07"),
            downside="increase",
        ),
    )


def joint(**changes):
    return JointScenarioInput(
        **dict(
            input_id="joint",
            ranges=ranges(),
            correlation=((D(1), D("-.5")), (D("-.5"), D(1))),
            seed=42,
            count=40,
            max_attempts=10000,
        )
        | changes
    )


def result(value, identifier="metric", source_id="base_input"):
    return CalcResult(
        calc_id=identifier,
        fn="return_model",
        inputs={"assumptions": source_id},
        outputs={"return": D(value)},
        code_version="test",
    )


def test_t018_ac1_scenarios_sensitivity_grid_stored_calc_ids_and_values():
    source = SensitivityInput(
        input_id="grid",
        ranges=ranges(),
        axes={"rent": (D(80), D(100)), "cap": (D(".05"), D(".07"))},
        metric_key="return",
    )
    calls = []

    def evaluate(values):
        calls.append(values.copy())
        return result(values["rent"] / values["cap"], f"model_{len(calls)}", "grid")

    actual = sensitivity_grid(source, evaluate, **META)
    assert len(calls) == 4
    assert calls == [
        {"rent": D(80), "cap": D(".05")},
        {"rent": D(80), "cap": D(".07")},
        {"rent": D(100), "cap": D(".05")},
        {"rent": D(100), "cap": D(".07")},
    ]
    assert actual.outputs["cell:0:metric"] == 1600
    assert actual.inputs["cell:3:result"] == "model_4"
    assert actual.inputs["range:rent"] == "rent_range"
    with pytest.raises(ValueError, match="range"):
        sensitivity_grid(
            source.model_copy(update={"axes": {"rent": (D(1),), "cap": (D(".05"),)}}),
            evaluate,
            **META,
        )


def test_t018_ac1_scenarios_joint_deterministic_bounded_and_correlated():
    first = joint_downside_scenarios(joint(count=300), **META)
    assert first == joint_downside_scenarios(joint(count=300), **META)
    assert first != joint_downside_scenarios(joint(seed=99, count=300), **META)
    o = first.outputs
    shocks = []
    for i in range(300):
        rent = o[f"scenario:{i}:rent"]
        cap = o[f"scenario:{i}:cap"]
        assert 80 <= rent <= 100
        assert D(".05") <= cap <= D(".07")
        shocks.append(((100 - rent) / 20, (cap - D(".05")) / D(".02")))
    xmean = sum(x for x, _ in shocks) / 300
    ymean = sum(y for _, y in shocks) / 300
    covariance = sum((x - xmean) * (y - ymean) for x, y in shocks)
    assert covariance > 0
    assert first.inputs["range:cap"] == "cap_range"


@given(seed=st.integers(0, 100000))
@settings(max_examples=20, deadline=None)
def test_t018_ac1_scenarios_perfect_correlation_and_singular_psd(seed):
    source = joint(seed=seed, count=8, correlation=((D(1), D(-1)), (D(-1), D(1))))
    o = joint_downside_scenarios(source, **META).outputs
    for i in range(8):
        a = (D(100) - o[f"scenario:{i}:rent"]) / 20
        b = (o[f"scenario:{i}:cap"] - D(".05")) / D(".02")
        assert abs(a - b) < D("1e-25")
        assert 0 <= a <= 1


@pytest.mark.parametrize(
    "correlation",
    [
        ((D(1), D(".2")), (D(".3"), D(1))),
        ((D(1), D(2)), (D(2), D(1))),
        ((D(1),),),
    ],
)
def test_t018_ac1_scenarios_bad_correlation_fails_closed(correlation):
    with pytest.raises(ValueError, match="correlation"):
        joint_downside_scenarios(joint(correlation=correlation), **META)


def test_t018_ac1_scenarios_impossible_joint_downside_and_non_psd():
    with pytest.raises(ValueError, match="joint downside"):
        joint_downside_scenarios(
            joint(correlation=((D(1), D(1)), (D(1), D(1))), count=2, max_attempts=50), **META
        )
    r = (
        *ranges(),
        AssumptionRange(
            input_id="expense", name="expense", p10=D(1), base=D(2), p90=D(3), downside="increase"
        ),
    )
    with pytest.raises(ValueError, match="positive semidefinite"):
        joint_downside_scenarios(
            joint(
                ranges=r,
                correlation=(
                    (D(1), D(".9"), D(".9")),
                    (D(".9"), D(1), D("-.9")),
                    (D(".9"), D("-.9"), D(1)),
                ),
            ),
            **META,
        )


def fragility(**changes):
    return FragilityInput(
        **dict(
            input_id="policy",
            ranges=ranges(),
            metric_key="return",
            target=D(".10"),
            fragility_margin=D(".02"),
        )
        | changes
    )


def scenario(value, rent="90", cap=".06"):
    return EvaluatedScenario(
        input_id="scenario",
        assumptions={"rent": D(rent), "cap": D(cap)},
        result=result(value, "downside", "scenario"),
    )


@pytest.mark.parametrize(
    ("base", "stress", "rent", "conditional", "flip", "margin"),
    [
        (".119", ".09", "90", 1, 1, ".019"),
        (".12", ".09", "90", 0, 1, ".02"),
        (".15", ".09", "90", 0, 1, ".05"),
        (".119", ".11", "90", 0, 0, ".019"),
        (".119", ".09", "79", 0, 0, ".019"),
        (".10", ".099", "80", 1, 1, "0"),
        (".09", ".10", "90", 1, 1, ".01"),
    ],
)
def test_t018_ac2_scenarios_fragility_exact_strict_predicate(
    base, stress, rent, conditional, flip, margin
):
    actual = assess_fragility(fragility(), result(base), (scenario(stress, rent),), **META)
    assert actual.outputs["conditional"] == conditional
    assert actual.outputs["flip_within_ranges"] == flip
    assert actual.outputs["margin_to_flip"] == D(margin)
    assert actual.inputs["base_result"] == "metric"
    assert actual.inputs["scenario:0:result"] == "downside"


def test_t018_ac2_scenarios_fragility_requires_all_assumptions_and_no_ambiguous_return():
    with pytest.raises(ValueError, match="assumptions"):
        assess_fragility(
            fragility(),
            result(".11"),
            (scenario(".09").model_copy(update={"assumptions": {"rent": D(90)}}),),
            **META,
        )
    ambiguous = result(".11").model_copy(
        update={"outputs": {"return": D(".11"), "ambiguous": D(1)}}
    )
    with pytest.raises(ValueError, match="ambiguous"):
        assess_fragility(fragility(), ambiguous, (scenario(".09"),), **META)
    unlinked = scenario(".09").model_copy(update={"result": result(".09", source_id="other")})
    with pytest.raises(ValueError, match="provenance"):
        assess_fragility(fragility(), result(".11"), (unlinked,), **META)


def price_input(**changes):
    return PriceSolveInput(
        **dict(
            input_id="price_model",
            close_date=START,
            future_flows=(
                DatedEquityFlow(input_id="exit", date=START + timedelta(days=365), amount=D(120)),
            ),
            lower_price=D(10),
            upper_price=D(200),
            acquisition_cost_rate=D(".02"),
            fixed_costs=D(3),
            debt_proceeds=D(0),
            target_return=D(".1"),
            return_tolerance=D("1e-12"),
            price_tolerance=D("1e-10"),
            max_iterations=256,
        )
        | changes
    )


def test_t018_ac3_scenarios_price_solver_hits_target_dated_return_and_costs():
    actual = max_supportable_price(price_input(), **META)
    o = actual.outputs
    expected = (D(120) / D("1.1") - 3) / D("1.02")
    assert abs(o["max_price"] - expected) < D("1e-10")
    assert D(".1") <= o["achieved_return"] <= D(".100000000001")
    assert abs(o["return_error"]) <= D("1e-12")
    assert o["bracket_upper"] - o["bracket_lower"] <= D("1e-10")
    assert actual.inputs == {"price_model": "price_model", "flow:0": "exit"}


@pytest.mark.parametrize(
    "changes",
    [
        {"lower_price": D(150)},
        {"upper_price": D(50)},
        {"max_iterations": 1},
        {
            "future_flows": (
                DatedEquityFlow(input_id="bad", date=START + timedelta(days=365), amount=D(-1)),
            )
        },
        {"future_flows": (DatedEquityFlow(input_id="bad", date=START, amount=D(120)),)},
        {"debt_proceeds": D(200)},
    ],
)
def test_t018_ac3_scenarios_price_solver_unbracketed_undefined_or_unconverged_fails(changes):
    with pytest.raises(ValueError):
        max_supportable_price(price_input(**changes), **META)


def test_t018_ac3_scenarios_price_solver_endpoint_negative_target_and_multiple_dates():
    simple = price_input(
        acquisition_cost_rate=D(0), fixed_costs=D(0), target_return=D(0), upper_price=D(120)
    )
    assert max_supportable_price(simple, **META).outputs["max_price"] == 120
    negative = price_input(acquisition_cost_rate=D(0), fixed_costs=D(0), target_return=D("-.1"))
    assert abs(max_supportable_price(negative, **META).outputs["max_price"] - D(120) / D(".9")) < D(
        "1e-10"
    )
    dated = price_input(
        future_flows=(
            DatedEquityFlow(input_id="interim", date=START + timedelta(days=180), amount=D(20)),
            DatedEquityFlow(input_id="terminal", date=START + timedelta(days=730), amount=D(110)),
        )
    )
    assert abs(max_supportable_price(dated, **META).outputs["return_error"]) <= D("1e-12")


def test_t018_ac1_scenarios_context_isolated_and_float_inputs_rejected():
    expected = joint_downside_scenarios(joint(), **META)
    price = max_supportable_price(price_input(), **META)
    with localcontext() as c:
        c.prec = 3
        c.rounding = ROUND_DOWN
        c.traps[Inexact] = True
        c.flags[Inexact] = True
        before = getcontext().copy()
        actual = joint_downside_scenarios(joint(), **META)
        actual_price = max_supportable_price(price_input(), **META)
        assert getcontext().flags == before.flags
    assert actual == expected
    assert actual_price == price
    with pytest.raises(ValidationError):
        joint(correlation=((1.0, 0.0), (0.0, 1.0)))


def test_t018_ac2_scenarios_upside_or_unchanged_assumptions_are_not_joint_downside():
    for s in (
        scenario(".09", rent="110", cap=".04"),
        scenario(".09", rent="100", cap=".05"),
        scenario(".09", rent="90", cap=".04"),
    ):
        o = assess_fragility(fragility(), result(".11"), (s,), **META).outputs
        assert o["conditional"] == 0
        assert o["scenario:0:joint_downside"] == 0


def test_t018_ac1_scenarios_sensitivity_rejects_conflicting_immutable_calc_ids():
    source = SensitivityInput(
        input_id="grid",
        ranges=ranges(),
        axes={"rent": (D(80), D(100)), "cap": (D(".05"),)},
        metric_key="return",
    )
    with pytest.raises(ValueError, match="immutable"):
        sensitivity_grid(
            source,
            lambda values: result(values["rent"], identifier="same", source_id="grid"),
            **META,
        )


def test_t018_ac2_scenarios_fragility_rejects_conflicting_calc_identity():
    with pytest.raises(ValueError, match="immutable"):
        assess_fragility(
            fragility(),
            result(".11", identifier="same"),
            (
                scenario(".09").model_copy(
                    update={"result": result(".09", identifier="same", source_id="scenario")}
                ),
            ),
            **META,
        )


def test_t018_ac3_scenarios_price_solver_tiny_scaled_cashflows_and_price_monotonicity():
    small = price_input(
        future_flows=(
            DatedEquityFlow(input_id="tiny", date=START + timedelta(days=365), amount=D("120e-70")),
        ),
        lower_price=D("10e-70"),
        upper_price=D("200e-70"),
        fixed_costs=D("3e-70"),
        price_tolerance=D("1e-80"),
    )
    o = max_supportable_price(small, **META).outputs
    expected = (D("120e-70") / D("1.1") - D("3e-70")) / D("1.02")
    assert abs(o["max_price"] - expected) < D("1e-80")
    assert abs(o["return_error"]) <= D("1e-12")
    high = max_supportable_price(price_input(target_return=D(".2")), **META).outputs
    low = max_supportable_price(price_input(target_return=D(".05")), **META).outputs
    assert high["max_price"] < low["max_price"]


def test_t018_ac2_scenarios_fragility_precision_boundary_and_isolated_context():
    base = result(".12000000000000000000000000000000000001")
    o = assess_fragility(fragility(), base, (scenario(".09"),), **META).outputs
    assert o["conditional"] == 0
    with localcontext() as c:
        c.prec = 2
        c.traps[Inexact] = True
        before = getcontext().copy()
        actual = assess_fragility(fragility(), base, (scenario(".09"),), **META).outputs
        assert getcontext().flags == before.flags
    assert actual == o


def test_t018_ac1_scenarios_sensitivity_rejects_missing_or_ambiguous_metrics():
    source = SensitivityInput(
        input_id="grid",
        ranges=ranges(),
        axes={"rent": (D(80),), "cap": (D(".05"),)},
        metric_key="return",
    )
    with pytest.raises(ValueError, match="provenance"):
        sensitivity_grid(source, lambda _: result(".1"), **META)
    with pytest.raises(ValueError, match="ambiguous"):
        sensitivity_grid(
            source,
            lambda _: result(".1", source_id="grid").model_copy(
                update={"outputs": {"return": D(".1"), "ambiguous": D(1)}}
            ),
            **META,
        )
