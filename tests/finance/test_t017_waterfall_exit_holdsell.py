from datetime import date, timedelta
from decimal import ROUND_DOWN, Decimal, Inexact, getcontext, localcontext

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from cre_brain.finance.exit import ExitInput, calculate_exit
from cre_brain.finance.holdsell import (
    DispositionScenario,
    HoldSellInput,
    RefinanceEvent,
    compare_hold_sell,
)
from cre_brain.finance.waterfall import (
    DatedEquityFlow,
    PromoteTier,
    WaterfallTerms,
    distribute_waterfall,
)

D = Decimal
META = {"calc_id": "calc", "code_version": "test"}
START = date(2023, 1, 1)
YEAR = START + timedelta(days=365)


def flow(day, amount, identifier="flow"):
    return DatedEquityFlow(input_id=identifier, date=day, amount=D(amount))


def terms(**changes):
    return WaterfallTerms(
        **dict(
            input_id="terms",
            lp_ownership=D(".9"),
            preferred_rate=D(".08"),
            catch_up_share=D(".2"),
            tiers=(PromoteTier(hurdle_rate=None, lp_share=D(".8")),),
            finance_rate=D(".1"),
            reinvest_rate=D(".1"),
        )
        | changes
    )


def exit_input(**changes):
    return ExitInput(
        **dict(
            input_id="exit",
            forward_noi=D("100"),
            cap_rate=D(".1"),
            selling_cost_rate=D(".05"),
            fixed_selling_cost=D("10"),
            debt_payoff=D("400"),
        )
        | changes
    )


def test_t017_ac1_waterfall_pref_capital_catchup_and_promote():
    result = distribute_waterfall(
        (flow(START, "-1000", "initial"), flow(YEAR, "1500")), terms(), **META
    )
    o = result.outputs
    assert o["event:1:pref:lp"] == 72
    assert o["event:1:capital:lp"] == 900
    assert o["event:1:capital:gp"] == 100
    assert o["event:1:catchup:gp"] == 18
    assert o["event:1:tier:0:lp"] == 328
    assert o["event:1:tier:0:gp"] == 82
    assert o["lp_distributions"] == 1300
    assert o["gp_distributions"] == 200
    assert o["lp:unique"] == 1
    assert result.inputs == {"terms": "terms", "flow:0": "initial", "flow:1": "flow"}


@given(capital=st.integers(1, 1000000), distribution=st.integers(0, 3000000))
@settings(max_examples=35, deadline=None)
def test_t017_ac1_waterfall_tiers_conserve_property(capital, distribution):
    o = distribute_waterfall(
        (flow(START, str(-capital)), flow(YEAR, str(distribution))),
        terms(
            tiers=(
                PromoteTier(hurdle_rate=D(".12"), lp_share=D(".8")),
                PromoteTier(hurdle_rate=None, lp_share=D(".6")),
            )
        ),
        **META,
    ).outputs
    tiers = sum(
        (
            v
            for k, v in o.items()
            if k.startswith("event:1:") and (k.endswith(":lp") or k.endswith(":gp"))
        ),
        D(0),
    )
    assert abs(tiers - distribution) < D("1e-20")
    assert abs(o["lp_distributions"] + o["gp_distributions"] - distribution) < D("1e-20")
    assert o["unreturned_lp_capital"] >= 0
    assert o["unreturned_gp_capital"] >= 0


def test_t017_ac1_waterfall_dated_hurdle_exact_boundary_and_next_tier():
    t = terms(
        lp_ownership=D(1),
        preferred_rate=D(0),
        catch_up_share=D(0),
        tiers=(
            PromoteTier(hurdle_rate=D(".1"), lp_share=D(1)),
            PromoteTier(hurdle_rate=None, lp_share=D(".5")),
        ),
    )
    at = distribute_waterfall((flow(START, "-100"), flow(YEAR, "110")), t, **META).outputs
    above = distribute_waterfall((flow(START, "-100"), flow(YEAR, "130")), t, **META).outputs
    assert at["event:1:tier:0:lp"] == 10
    assert at["event:1:tier:1:lp"] == 0
    assert above["event:1:tier:0:lp"] == 10
    assert above["event:1:tier:1:lp"] == 10
    assert above["event:1:tier:1:gp"] == 10


def test_t017_ac1_waterfall_multiple_contributions_and_losses():
    t = terms(
        lp_ownership=D(1),
        catch_up_share=D(0),
        tiers=(PromoteTier(hurdle_rate=None, lp_share=D(1)),),
    )
    o = distribute_waterfall(
        (
            flow(START, "-100"),
            flow(YEAR, "-50", "additional"),
            flow(YEAR + timedelta(days=365), "10"),
        ),
        t,
        **META,
    ).outputs
    assert o["event:2:pref:lp"] == 10
    assert o["unpaid_pref"] == 10
    assert o["unreturned_lp_capital"] == 150
    assert o["lp_distributions"] == 10
    loss = distribute_waterfall((flow(START, "-100"), flow(YEAR, "40")), t, **META).outputs
    assert loss["unreturned_lp_capital"] == 68
    assert loss["lp:unique"] == 1
    assert loss["lp:xirr"] < 0


def test_t017_ac1_waterfall_never_hides_ambiguous_or_undefined_irr():
    t = terms(
        lp_ownership=D(1),
        preferred_rate=D(0),
        catch_up_share=D(0),
        tiers=(PromoteTier(hurdle_rate=None, lp_share=D(1)),),
    )
    o = distribute_waterfall(
        (flow(START, "-100"), flow(YEAR, "230"), flow(YEAR + timedelta(days=365), "-132")),
        t,
        **META,
    ).outputs
    assert o["lp:ambiguous"] == 1
    assert o["lp:root_count"] == 2
    assert "lp:xirr" not in o
    assert o["lp:mirr_defined"] == 1
    undefined = distribute_waterfall((flow(START, "-100"), flow(YEAR, "0")), t, **META).outputs
    assert undefined["lp:undefined"] == 1
    assert "lp:xirr" not in undefined


def test_t017_ac1_waterfall_same_day_order_is_explicit_and_bad_terms_rejected():
    with pytest.raises(ValueError, match="chronological"):
        distribute_waterfall((flow(YEAR, "100"), flow(START, "-100")), terms(), **META)
    with pytest.raises(ValueError, match="contribution"):
        distribute_waterfall((flow(START, "100"), flow(YEAR, "-100")), terms(), **META)
    with pytest.raises(ValidationError):
        terms(
            tiers=(
                PromoteTier(hurdle_rate=D(".2"), lp_share=D(".8")),
                PromoteTier(hurdle_rate=D(".1"), lp_share=D(".6")),
            )
        )
    with pytest.raises(ValidationError):
        terms(lp_ownership=0.9)


def test_t017_ac2_exit_cap_selling_costs_and_negative_equity():
    result = calculate_exit(exit_input(), **META)
    assert result.outputs == {
        "gross_value": D(1000),
        "selling_costs": D(60),
        "net_sale_proceeds": D(940),
        "net_equity_proceeds": D(540),
    }
    assert result.inputs == {"exit": "exit"}
    assert (
        calculate_exit(exit_input(debt_payoff=D(2000)), **META).outputs["net_equity_proceeds"]
        == -1060
    )
    with pytest.raises(ValidationError):
        exit_input(cap_rate=D(0))
    with pytest.raises(ValidationError):
        exit_input(forward_noi=D(-1))


def test_t017_ac2_exit_context_and_provenance_are_isolated():
    expected = calculate_exit(exit_input(), **META)
    with localcontext() as c:
        c.prec = 3
        c.rounding = ROUND_DOWN
        c.traps[Inexact] = True
        before = getcontext().copy()
        actual = calculate_exit(exit_input(), **META)
        assert getcontext().flags == before.flags
    assert actual == expected
    assert actual.model_validate_json(actual.model_dump_json()) == actual


def alternative(kind, end, **changes):
    return DispositionScenario(
        **dict(
            input_id=kind,
            kind=kind,
            terminal_date=end,
            exit=exit_input(),
            operating_flows=(),
            refinance=None,
        )
        | changes
    )


def comparison(**changes):
    return HoldSellInput(
        **dict(
            input_id="comparison",
            decision_date=START,
            discount_rate=D(".1"),
            historical_flows=(flow(START, "-500", "investment"),),
            finance_rate=D(".1"),
            reinvest_rate=D(".1"),
        )
        | changes
    )


def test_t017_ac3_holdsell_comparison_dates_costs_refi_and_ranking():
    refi = RefinanceEvent(
        input_id="refi",
        date=START,
        new_principal=D(500),
        old_debt_payoff=D(400),
        fees=D(10),
        prepayment_cost=D(5),
    )
    alts = (
        alternative("sell", START),
        alternative("hold", YEAR, operating_flows=(flow(YEAR, "100", "noi"),)),
        alternative(
            "refinance",
            YEAR,
            refinance=refi,
            exit=exit_input(input_id="refi_exit", debt_payoff=D(500)),
            operating_flows=(flow(YEAR, "100", "refi_noi"),),
        ),
    )
    result = compare_hold_sell(comparison(), alts, **META)
    o = result.outputs
    assert o["sell:npv"] == 540
    assert abs(o["hold:npv"] - D(640) / D("1.1")) < D("1e-24")
    assert abs(o["refinance:npv"] - (D(85) + D(540) / D("1.1"))) < D("1e-24")
    assert o["hold:rank"] == 1
    assert o["refinance:rank"] == 2
    assert o["sell:rank"] == 3
    assert o["refinance:refinance_proceeds"] == 85
    assert result.inputs["refinance:refinance"] == "refi"
    assert result.inputs["hold:operating:0"] == "noi"


def test_t017_ac3_holdsell_rejects_invalid_timelines_and_keeps_ties():
    with pytest.raises(ValueError, match="sell"):
        compare_hold_sell(comparison(), (alternative("sell", YEAR),), **META)
    with pytest.raises(ValueError, match="timeline"):
        compare_hold_sell(
            comparison(),
            (alternative("hold", YEAR, operating_flows=(flow(YEAR + timedelta(days=1), "5"),)),),
            **META,
        )
    o = compare_hold_sell(
        comparison(discount_rate=D(0)),
        (alternative("hold", YEAR), alternative("sell", START)),
        **META,
    ).outputs
    assert o["sell:rank"] == o["hold:rank"] == 1
    assert o["hold:incremental_npv"] == 0


def test_t017_ac3_holdsell_return_status_not_fabricated():
    history = (flow(START - timedelta(days=730), "-100"), flow(START - timedelta(days=365), "230"))
    o = compare_hold_sell(
        comparison(historical_flows=history),
        (
            alternative(
                "sell",
                START,
                exit=exit_input(
                    forward_noi=D(0),
                    selling_cost_rate=D(0),
                    fixed_selling_cost=D(0),
                    debt_payoff=D(132),
                ),
            ),
        ),
        **META,
    ).outputs
    assert o["sell:returns:ambiguous"] == 1
    assert "sell:returns:xirr" not in o


def test_t017_ac1_waterfall_partial_catchup_and_pref_capital_reduction():
    partial = distribute_waterfall(
        (flow(START, "-1000"), flow(YEAR, "1080")), terms(), **META
    ).outputs
    assert partial["event:1:catchup:gp"] == 8
    assert partial["event:1:tier:0:gp"] == 0
    t = terms(
        lp_ownership=D(1),
        catch_up_share=D(0),
        tiers=(PromoteTier(hurdle_rate=None, lp_share=D(1)),),
    )
    o = distribute_waterfall(
        (flow(START, "-100"), flow(YEAR, "58"), flow(YEAR + timedelta(days=365), "54")), t, **META
    ).outputs
    assert o["event:1:pref:lp"] == 8
    assert o["event:1:capital:lp"] == 50
    assert o["event:2:pref:lp"] == 4
    assert o["unpaid_pref"] == o["unreturned_lp_capital"] == 0


def test_t017_ac1_waterfall_nonannual_hurdle_and_hostile_caller_context():
    day = START + timedelta(days=180)
    t = terms(
        lp_ownership=D(1),
        preferred_rate=D(0),
        catch_up_share=D(0),
        tiers=(
            PromoteTier(hurdle_rate=D(".1"), lp_share=D(1)),
            PromoteTier(hurdle_rate=None, lp_share=D(".5")),
        ),
    )
    source = (flow(START, "-100"), flow(day, "150"))
    expected = distribute_waterfall(source, t, **META)
    with localcontext() as c:
        c.prec = 3
        c.Emax = 9
        c.Emin = -9
        c.rounding = ROUND_DOWN
        c.traps[Inexact] = True
        c.flags[Inexact] = True
        before = getcontext().copy()
        actual = distribute_waterfall(source, t, **META)
        assert getcontext().flags == before.flags
    assert actual == expected
    o = actual.outputs
    with localcontext() as c:
        c.prec = 50
        target = D(100) * (D("1.1").ln() * D(180) / 365).exp() - 100
    assert abs(o["event:1:tier:0:lp"] - target) < D("1e-25")
    assert abs(
        sum(
            (
                v
                for k, v in o.items()
                if k.startswith("event:1:") and (k.endswith(":lp") or k.endswith(":gp"))
            ),
            D(0),
        )
        - 150
    ) < D("1e-24")


def test_t017_ac1_waterfall_tiny_scaled_money_and_exact_same_day_events():
    t = terms(
        lp_ownership=D(1),
        preferred_rate=D(0),
        catch_up_share=D(0),
        tiers=(PromoteTier(hurdle_rate=None, lp_share=D(1)),),
    )
    source = (
        flow(START, "-1e-100", "first"),
        flow(START, "-2e-100", "second"),
        flow(YEAR, "4e-100", "sale"),
    )
    o = distribute_waterfall(source, t, **META).outputs
    assert o["lp_distributions"] == D("4e-100")
    assert o["event:2:capital:lp"] == D("3e-100")
    assert o["event:2:tier:0:lp"] == D("1e-100")
    assert abs(o["lp:xirr"] - D(1) / 3) < D("1e-27")


def test_t017_ac2_exit_exact_cancellation_and_unsupported_span():
    x = D("1e-70")
    with localcontext() as c:
        c.prec = 200
        source = exit_input(
            forward_noi=1 - x,
            cap_rate=D(1),
            selling_cost_rate=x,
            fixed_selling_cost=1 - 2 * x,
            debt_payoff=D(0),
        )
    assert calculate_exit(source, **META).outputs["net_equity_proceeds"] == D("1e-140")
    with pytest.raises(ValueError, match="precision"):
        calculate_exit(exit_input(cap_rate=D("1e-300")), **META)
