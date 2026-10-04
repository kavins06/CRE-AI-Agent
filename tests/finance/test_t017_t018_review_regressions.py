"""Regressions for the required T017/T018 review findings."""

import json
from decimal import Decimal as D

import pytest

from cre_brain.finance.holdsell import compare_hold_sell
from cre_brain.finance.scenarios import (
    AssumptionRange,
    SensitivityInput,
    assess_fragility,
    joint_downside_scenarios,
    sensitivity_grid,
)
from tests.finance.test_t017_waterfall_exit_holdsell import (
    META,
    START,
    YEAR,
    alternative,
    comparison,
    exit_input,
    flow,
)
from tests.finance.test_t018_scenarios import fragility, joint, result, scenario


def canonical(kind, index, name):
    return f"{kind}:" + json.dumps([index, name], ensure_ascii=True, separators=(",", ":"))


@pytest.mark.parametrize("extra", [D(0), D("1e-40")])
@pytest.mark.parametrize("reverse", [False, True])
def test_t017_ac3_holdsell_published_equal_npvs_tie(extra, reverse):
    immediate = exit_input(
        forward_noi=D(1),
        cap_rate=D(1),
        selling_cost_rate=D(0),
        fixed_selling_cost=D(0),
        debt_payoff=D(0),
    )
    terminal = immediate.model_copy(update={"forward_noi": extra, "debt_payoff": D(".9")})
    alternatives = (
        alternative("sell", START, exit=immediate),
        alternative("hold", YEAR, exit=terminal, operating_flows=(flow(YEAR, "2"),)),
    )
    o = compare_hold_sell(
        comparison(historical_flows=(flow(START, "-1"),)),
        alternatives[::-1] if reverse else alternatives,
        **META,
    ).outputs
    assert o["sell:npv"] == o["hold:npv"] == 1
    assert o["sell:rank"] == o["hold:rank"] == 1
    assert o["hold:incremental_npv"] == o["sell:incremental_npv"] == 0


def assumption(name, index):
    return AssumptionRange(
        input_id=f"range-{index}",
        name=name,
        p10=D(0),
        base=D(1),
        p90=D(2),
        downside="decrease",
    )


@pytest.mark.parametrize("names", [("metric",), ("rent", "assumption:rent", 'a:"\\雪')])
def test_t018_ac1_scenarios_grid_canonical_assumptions_preserve_metric(names):
    source = SensitivityInput(
        input_id="grid",
        ranges=tuple(assumption(n, i) for i, n in enumerate(names)),
        axes={n: (D(1),) for n in names},
        metric_key="return",
    )
    o = sensitivity_grid(source, lambda _: result(".12", source_id="grid"), **META).outputs
    assert o["cell:0:metric"] == D(".12")
    for name in names:
        assert o[canonical("assumption", 0, name)] == 1
        if name != "metric":
            assert o[f"cell:0:{name}"] == 1


@pytest.mark.parametrize("reverse", [False, True])
def test_t018_ac1_scenarios_joint_canonical_names_cannot_overwrite_shocks(reverse):
    names = ("x", "shock:x", "shock:shock:x", 'a:"\\雪')
    if reverse:
        names = names[::-1]
    source = joint(
        ranges=tuple(assumption(n, i) for i, n in enumerate(names)),
        count=1,
        correlation=tuple(tuple(D(i == j) for j in range(4)) for i in range(4)),
    )
    o = joint_downside_scenarios(source, **META).outputs
    for name in names:
        value = o[canonical("assumption", 0, name)]
        shock = o[canonical("shock", 0, name)]
        assert abs((1 - value) - shock) < D("1e-27")
        assert 0 < shock <= 1
    assert "scenario:0:shock:x" not in o  # ambiguous legacy alias
    assert o["scenario:0:x"] == o[canonical("assumption", 0, "x")]


@pytest.mark.parametrize("late", [False, True])
def test_t018_ac1_scenarios_grid_rejects_aggregate_evaluator_id(late):
    source = SensitivityInput(
        input_id="grid",
        ranges=(assumption("rent", 0),),
        axes={"rent": (D(0), D(1))},
        metric_key="return",
    )

    def evaluate(values):
        identifier = "calc" if values["rent"] == int(late) else "other"
        return result(".12", identifier=identifier, source_id="grid")

    with pytest.raises(ValueError, match="aggregate"):
        sensitivity_grid(source, evaluate, **META)


@pytest.mark.parametrize("collision", ["base", "scenario", "dependency"])
def test_t018_ac2_scenarios_fragility_rejects_aggregate_identity_and_cycles(collision):
    base = result(".11", identifier="calc" if collision == "base" else "base")
    stress = scenario(".09")
    if collision == "scenario":
        stress = stress.model_copy(update={"result": result(".09", "calc", "scenario")})
    if collision == "dependency":
        base = base.model_copy(update={"inputs": {"dependency": "calc"}})
    with pytest.raises(ValueError, match="aggregate"):
        assess_fragility(fragility(), base, (stress,), **META)


@pytest.mark.parametrize("kind", ["grid", "policy", "range", "scenario"])
def test_t018_ac1_scenarios_aggregate_direct_provenance_cannot_reference_itself(kind):
    if kind == "grid":
        source = SensitivityInput(
            input_id="calc",
            ranges=(assumption("rent", 0),),
            axes={"rent": (D(1),)},
            metric_key="return",
        )
        with pytest.raises(ValueError, match="aggregate"):
            sensitivity_grid(source, lambda _: result(".12", "evaluation", "calc"), **META)
    else:
        source = fragility()
        stress = scenario(".09")
        if kind == "policy":
            source = source.model_copy(update={"input_id": "calc"})
        elif kind == "range":
            source = source.model_copy(
                update={
                    "ranges": (
                        source.ranges[0].model_copy(update={"input_id": "calc"}),
                        source.ranges[1],
                    ),
                }
            )
        else:
            stress = stress.model_copy(
                update={
                    "input_id": "calc",
                    "result": result(".09", "evaluation", "calc"),
                }
            )
        with pytest.raises(ValueError, match="aggregate"):
            assess_fragility(source, result(".11"), (stress,), **META)


def test_t017_ac3_holdsell_exact_zero_cancellation_must_tie():
    zero = exit_input(
        forward_noi=D(0),
        cap_rate=D(1),
        selling_cost_rate=D(0),
        fixed_selling_cost=D(0),
        debt_payoff=D(0),
    )
    alternatives = (
        alternative("sell", START, exit=zero),
        alternative(
            "hold",
            YEAR,
            exit=zero.model_copy(update={"debt_payoff": D("1.1")}),
            operating_flows=(flow(YEAR, "2", "income"), flow(YEAR, "-.9", "cost")),
        ),
    )
    o = compare_hold_sell(comparison(), alternatives, **META).outputs
    assert o["sell:npv"] == o["hold:npv"] == 0
    assert o["sell:rank"] == o["hold:rank"] == 1
    assert o["hold:incremental_npv"] == 0


def test_t017_ac3_holdsell_exact_annual_cancellation_across_dates_must_tie():
    from datetime import timedelta

    zero = exit_input(
        forward_noi=D(0),
        cap_rate=D(1),
        selling_cost_rate=D(0),
        fixed_selling_cost=D(0),
        debt_payoff=D(0),
    )
    alternatives = (
        alternative("sell", START, exit=zero),
        alternative(
            "hold",
            YEAR + timedelta(days=365),
            exit=zero.model_copy(update={"debt_payoff": D("2.2")}),
            operating_flows=(flow(YEAR, "2", "income"),),
        ),
    )
    o = compare_hold_sell(comparison(), alternatives, **META).outputs
    assert o["sell:npv"] == o["hold:npv"] == 0
    assert o["sell:rank"] == o["hold:rank"] == 1
    assert o["hold:incremental_npv"] == 0


@pytest.mark.parametrize("operation", ["grid", "fragility"])
def test_t018_ac1_scenarios_normalized_aggregate_ids_cannot_alias_evaluators(operation):
    meta = {"calc_id": "  metric  ", "code_version": "test"}
    with pytest.raises(ValueError, match="aggregate"):
        if operation == "grid":
            source = SensitivityInput(
                input_id="grid",
                ranges=(assumption("rent", 0),),
                axes={"rent": (D(1),)},
                metric_key="return",
            )
            sensitivity_grid(source, lambda _: result(".12", source_id="grid"), **meta)
        else:
            assess_fragility(fragility(), result(".11"), (scenario(".09"),), **meta)


def test_t017_ac3_holdsell_exact_nonannual_cancellation_across_years_must_tie():
    from datetime import timedelta

    zero = exit_input(
        forward_noi=D(0),
        cap_rate=D(1),
        selling_cost_rate=D(0),
        fixed_selling_cost=D(0),
        debt_payoff=D(0),
    )
    alternatives = (
        alternative("sell", START, exit=zero),
        alternative(
            "hold",
            START + timedelta(days=545),
            exit=zero.model_copy(update={"debt_payoff": D("2.2")}),
            operating_flows=(flow(START + timedelta(days=180), "2", "income"),),
        ),
    )
    o = compare_hold_sell(comparison(), alternatives, **META).outputs
    assert o["sell:npv"] == o["hold:npv"] == 0
    assert o["sell:rank"] == o["hold:rank"] == 1
    assert o["hold:incremental_npv"] == 0
