from datetime import timedelta
from decimal import Decimal as D

import pytest

from cre_brain.finance.holdsell import compare_hold_sell
from cre_brain.finance.scenarios import (
    AssumptionRange,
    SensitivityInput,
    joint_downside_scenarios,
    max_supportable_price,
    sensitivity_grid,
)
from tests.finance.test_t017_waterfall_exit_holdsell import (
    START,
    alternative,
    comparison,
    exit_input,
    flow,
)
from tests.finance.test_t018_scenarios import joint, price_input, result

META = dict(calc_id="aggregate", code_version="review")


@pytest.mark.parametrize("base,endpoint", [("1", "1"), ("1", "0.99999999999999999999999999999")])
def test_review_downside_requires_reportable_movement(base, endpoint):
    r = AssumptionRange(
        input_id="range", name="x", p10=D(endpoint), base=D(base), p90=D(2), downside="decrease"
    )
    with pytest.raises(ValueError, match="movement|precision"):
        joint_downside_scenarios(joint(ranges=(r,), correlation=((D(1),),), count=1), **META)


def test_review_price_output_accuracy_certified():
    huge = "10000000000000000000000000000000000000000"
    source = price_input(
        lower_price=D(huge),
        upper_price=D(huge[:-1] + "2"),
        future_flows=(flow(START + timedelta(days=365), huge[:-1] + "1"),),
        target_return=D(0),
        price_tolerance=D("1e-10"),
        acquisition_cost_rate=D(0),
        fixed_costs=D(0),
        debt_proceeds=D(0),
    )
    with pytest.raises(ValueError, match="price.*precision|price.*tolerance"):
        max_supportable_price(source, **META)


@pytest.mark.parametrize("key", ["root:0", "lp:root:0"])
@pytest.mark.parametrize("flag", ["ambiguous", "undefined", "infinitely_many_roots"])
def test_review_indexed_root_rejects_invalid_return(key, flag):
    prefix = "lp:" if key.startswith("lp:") else ""
    evaluated = result(".1", source_id="grid").model_copy(
        update={"outputs": {key: D(".1"), prefix + flag: D(1)}}
    )
    source = SensitivityInput(
        input_id="grid",
        ranges=(
            AssumptionRange(
                input_id="r", name="x", p10=D(0), base=D(1), p90=D(2), downside="decrease"
            ),
        ),
        axes={"x": (D(1),)},
        metric_key=key,
    )
    with pytest.raises(ValueError, match="ambiguous or undefined"):
        sensitivity_grid(source, lambda _: evaluated, **META)


def test_review_fractional_date_exact_cancellation_ties():
    zero = exit_input(
        forward_noi=D(0),
        cap_rate=D(1),
        selling_cost_rate=D(0),
        fixed_selling_cost=D(0),
        debt_payoff=D(0),
    )
    o = compare_hold_sell(
        comparison(historical_flows=()),
        (
            alternative("sell", START, exit=zero),
            alternative(
                "hold",
                START + timedelta(days=382),
                exit=zero.model_copy(update={"debt_payoff": D("1.1")}),
                operating_flows=(flow(START + timedelta(days=17), "1"),),
            ),
        ),
        **META,
    ).outputs
    assert o["hold:npv"] == 0
    assert o["hold:rank"] == o["sell:rank"] == 1


@pytest.mark.parametrize("dependency", [" aggregate ", "aggregate"])
def test_review_normalized_dependency_cycle_rejected(dependency):
    source = SensitivityInput(
        input_id="grid",
        ranges=(
            AssumptionRange(
                input_id="r", name="x", p10=D(0), base=D(1), p90=D(2), downside="decrease"
            ),
        ),
        axes={"x": (D(1),)},
        metric_key="return",
    )
    evaluated = result(".1", source_id=" grid ").model_copy(
        update={"inputs": {"source": "grid", "dependency": dependency}}
    )
    with pytest.raises(ValueError, match="aggregate"):
        sensitivity_grid(source, lambda _: evaluated, **META)


@pytest.mark.parametrize("flag", ["ambiguous", "undefined", "infinitely_many_roots"])
def test_review_prefixed_root_rejects_global_invalid_return(flag):
    from cre_brain.finance.scenarios import assess_fragility
    from tests.finance.test_t018_scenarios import fragility, scenario

    base = result(".12").model_copy(update={"outputs": {"lp:root:0": D(".12"), flag: D(1)}})
    stress = scenario(".09")
    stress = stress.model_copy(
        update={"result": stress.result.model_copy(update={"outputs": {"lp:root:0": D(".09")}})}
    )
    with pytest.raises(ValueError, match="ambiguous or undefined"):
        assess_fragility(fragility(metric_key="lp:root:0"), base, (stress,), **META)
