from __future__ import annotations

import hashlib
import json
from decimal import Decimal, localcontext
from importlib import metadata, resources

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from cre_brain import rules
from cre_brain.rules import engine
from cre_brain.rules.models import (
    AssumptionPolicy,
    AssumptionProfile,
    BuyBoxInput,
    BuyBoxPolicy,
    EscalationPolicy,
    EvaluationResult,
    LoiPolicy,
    MissingDataPolicy,
    RentPolicy,
    TaxPolicy,
    scaled,
)

D = Decimal
TABLES = (
    "buy_box.default",
    "assumption_ranges.mf",
    "loi_policy.default",
    "missing_data_policy",
    "escalation_policy",
    "rent_regulation",
    "tax_reassessment",
)


def buy(**changes):
    return {"units": 120, "dscr": D("1.31"), "price": D("20000000"), "market_tier": "B", **changes}


def assumption(**changes):
    return {
        "market_tier": "B",
        "asset_class": "B",
        "vintage": 1990,
        "rent_growth": D("0.03"),
        "cap_rate": D("0.055"),
        **changes,
    }


def loi(**changes):
    return {
        "price": D("20000000"),
        "dd_days": 30,
        "close_days": 60,
        "deposit_percent": D("0.01"),
        "financing_contingency": True,
        **changes,
    }


def rent_policy(status="regulated", **changes):
    return RentPolicy(
        **{
            "jurisdiction": "synthetic-jurisdiction",
            "status": status,
            "verified": True,
            "source_ids": ("synthetic-policy-evidence",),
            **changes,
        }
    )


def tax_policy(status="on_transfer", **changes):
    return TaxPolicy(
        **{
            "jurisdiction": "synthetic-jurisdiction",
            "status": status,
            "verified": True,
            "source_ids": ("synthetic-policy-evidence",),
            **changes,
        }
    )


def test_t021_ac1_typed_deterministic_audit_trace():
    payload = buy(source_ids=("fact-rentroll-1",), assumption_ids=("assumption-debt-2",))
    first = rules.evaluate("buy_box.default", payload)
    assert isinstance(first, EvaluationResult)
    assert first.decision.classification == "eligible"
    assert first.trace == rules.evaluate("buy_box.default", payload).trace
    assert [node.node_id for node in first.trace.nodes] == ["input", "rules", "output"]
    assert first.trace.matched_rules[0].rule_id == "eligible"
    assert first.trace.table_id == "buy_box.default"
    assert first.trace.table_version == "1.0.0"
    assert first.trace.engine_version == metadata.version("zen-engine") == "2.1.2"
    raw = resources.files("cre_brain.rules").joinpath("tables/buy_box.default.json").read_bytes()
    assert first.trace.table_sha256 == hashlib.sha256(raw).hexdigest()
    assert first.trace.source_ids == ("fact-rentroll-1",)
    assert first.trace.assumption_ids == ("assumption-debt-2",)
    snapshot = json.loads(first.trace.input_json)
    assert snapshot["dscr"] == "1.31"
    assert snapshot["policy"]["policy_id"] == first.trace.policy_id
    assert len(first.trace.input_sha256) == len(first.trace.policy_sha256) == 64
    assert "performance" not in first.model_dump_json()
    assert EvaluationResult.model_validate_json(first.model_dump_json()) == first


def test_t021_ac1_uses_real_zen_engine(monkeypatch):
    original = engine.zen.ZenEngine
    calls = []

    class Spy:
        def __init__(self, options):
            self.delegate = original(options)

        def evaluate(self, key, context, options):
            calls.append((key, context, options))
            return self.delegate.evaluate(key, context, options)

    monkeypatch.setattr(engine.zen, "ZenEngine", Spy)
    assert rules.evaluate("buy_box.default", buy()).decision.classification == "eligible"
    assert calls[0][0] == "buy_box.default"
    assert calls[0][1]["dscr"] == 1310000
    assert calls[0][1]["price"] == 2000000000
    assert calls[0][2] == {"trace": True}


@pytest.mark.parametrize(
    "dscr,expected",
    [
        ("1.249999", "ineligible"),
        ("1.25", "eligible"),
        ("1.250001", "eligible"),
    ],
)
def test_t021_ac1_exact_decimal_boundary_independent_of_context(dscr, expected):
    with localcontext() as ctx:
        ctx.prec = 2
        result = rules.evaluate("buy_box.default", buy(dscr=D(dscr)))
    assert result.decision.classification == expected


@pytest.mark.parametrize(
    "bad", [1.25, "1.25", True, D("NaN"), D("Infinity"), D("1.2500001"), D("1E100")]
)
def test_t021_ac1_rejects_lossy_numeric_types_or_precision(bad):
    with pytest.raises((ValidationError, ValueError)):
        rules.evaluate("buy_box.default", buy(dscr=bad))


def test_t021_ac1_no_arbitrary_input_or_credentials_in_trace():
    with pytest.raises(ValidationError):
        rules.evaluate("buy_box.default", buy(api_key="must-not-appear"))
    with pytest.raises(ValidationError):
        rules.evaluate("buy_box.default", buy(source_ids=("https://private/?token=secret",)))
    with pytest.raises(ValidationError):
        rules.evaluate("buy_box.default", buy(units=True))
    with pytest.raises(ValidationError):
        rules.evaluate("buy_box.default", buy(price=D("0.001")))
    with pytest.raises(ValidationError):
        rules.evaluate("buy_box.default", buy(policy=BuyBoxPolicy(min_units=600, max_units=500)))


@pytest.mark.parametrize("table_id", TABLES)
def test_t021_ac2_all_bundled_tables_are_portable_jdm(table_id):
    assert rules.TABLE_IDS == TABLES
    table = json.loads(
        resources.files("cre_brain.rules").joinpath(f"tables/{table_id}.json").read_text()
    )
    assert [n["type"] for n in table["nodes"]] == ["inputNode", "decisionTableNode", "outputNode"]
    assert table["nodes"][1]["content"]["hitPolicy"] == "first"
    assert table["metadata"]["version"] == "1.0.0"
    assert table["metadata"]["table_id"] == table_id


@pytest.mark.parametrize(
    "table_id",
    [
        "../secret",
        "buy_box.default.json",
        "/etc/passwd",
        "unknown",
        "tables/../buy_box.default",
        "",
    ],
)
def test_t021_ac2_unknown_or_path_like_table_ids_are_rejected(table_id):
    with pytest.raises(ValueError, match="Unknown table"):
        rules.evaluate(table_id, buy())


def test_t021_ac2_untrusted_code_nodes_rejected_before_zen(monkeypatch):
    data = json.loads(
        resources.files("cre_brain.rules").joinpath("tables/buy_box.default.json").read_text()
    )
    data["nodes"][1]["type"] = "functionNode"
    monkeypatch.setattr(engine, "_read_table", lambda _: json.dumps(data).encode())
    with pytest.raises(ValueError, match="Bundled table"):
        rules.evaluate("buy_box.default", buy())


@pytest.mark.parametrize(
    "payload,expected",
    [
        (buy(), "eligible"),
        (buy(units=49), "ineligible"),
        (buy(units=501), "ineligible"),
        (buy(dscr=D("1.249999")), "ineligible"),
        (buy(price=D("100000000.01")), "ineligible"),
        (buy(market_tier="C"), "ineligible"),
        (buy(market_tier="unknown"), "review_required"),
        (buy(dscr=None), "review_required"),
        (buy(units=500, price=D("100000000"), dscr=D("1.25")), "eligible"),
        (
            buy(
                units=40, policy=BuyBoxPolicy(min_units=30, policy_id="firm-smaller", version="2.0")
            ),
            "eligible",
        ),
    ],
)
def test_t021_ac3_buy_box_examples(payload, expected):
    assert rules.evaluate("buy_box.default", payload).decision.classification == expected


@pytest.mark.parametrize(
    "payload,expected",
    [
        (assumption(), "within_policy"),
        (assumption(rent_growth=D("0.060001")), "outside_policy"),
        (assumption(cap_rate=D("0.034999")), "outside_policy"),
        (assumption(rent_growth=D("-0.01"), cap_rate=D("0.09")), "within_policy"),
        (
            assumption(market_tier="C", asset_class="C", vintage=1960, cap_rate=D("0.07")),
            "within_policy",
        ),
        (assumption(asset_class="unknown"), "review_required"),
        (assumption(market_tier="unknown"), "review_required"),
        (assumption(vintage=1900), "review_required"),
        (assumption(policy=AssumptionPolicy(profiles=())), "review_required"),
    ],
)
def test_t021_ac3_assumption_range_examples(payload, expected):
    result = rules.evaluate("assumption_ranges.mf", payload)
    assert result.decision.classification == expected
    if expected == "review_required":
        assert "verify_assumption_profile" in result.decision.required_checks


@pytest.mark.parametrize(
    "payload,expected",
    [
        (loi(), "within_policy"),
        (loi(price=D("100000000.01")), "approval_required"),
        (loi(dd_days=14), "approval_required"),
        (loi(dd_days=61), "approval_required"),
        (loi(close_days=29), "approval_required"),
        (loi(deposit_percent=D("0.030001")), "approval_required"),
        (loi(financing_contingency=False), "approval_required"),
        (
            loi(price=D("100000000"), dd_days=60, close_days=120, deposit_percent=D("0.03")),
            "within_policy",
        ),
        (
            loi(financing_contingency=False, policy=LoiPolicy(require_financing_contingency=False)),
            "within_policy",
        ),
    ],
)
def test_t021_ac3_loi_policy_examples(payload, expected):
    assert rules.evaluate("loi_policy.default", payload).decision.classification == expected


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"missing_fields": ()}, "complete"),
        ({"missing_fields": ("rent_roll",)}, "blocked"),
        ({"missing_fields": ("t12", "market_rent")}, "blocked"),
        ({"missing_fields": ("price",)}, "blocked"),
        ({"missing_fields": ("market_rent",)}, "proceed_with_assumptions"),
        (
            {"missing_fields": ("capex",), "policy": MissingDataPolicy(allow_defaults=False)},
            "clarification_required",
        ),
        (
            {
                "missing_fields": ("market_rent",),
                "policy": MissingDataPolicy(critical_fields=("market_rent",)),
            },
            "blocked",
        ),
    ],
)
def test_t021_ac3_missing_data_examples(payload, expected):
    assert rules.evaluate("missing_data_policy", payload).decision.classification == expected


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({}, "continue"),
        ({"evidence_conflict": True}, "stop"),
        ({"legal_uncertainty": True}, "legal_review"),
        ({"policy_exception": True}, "approval_required"),
        ({"external_action": True}, "approval_required"),
        ({"material_uncertainty": True}, "clarification_required"),
        ({"evidence_conflict": True, "external_action": True}, "stop"),
        (
            {"external_action": True, "policy": EscalationPolicy(require_external_approval=False)},
            "continue",
        ),
    ],
)
def test_t021_ac3_escalation_examples(payload, expected):
    assert rules.evaluate("escalation_policy", payload).decision.classification == expected


@pytest.mark.parametrize(
    "jurisdiction,policy,expected,check",
    [
        ("unknown", None, "review_required", "verify_jurisdiction_policy"),
        ("synthetic-jurisdiction", None, "review_required", "verify_jurisdiction_policy"),
        ("synthetic-jurisdiction", rent_policy(), "regulated", "review_rent_limits"),
        (
            "synthetic-jurisdiction",
            rent_policy("unregulated"),
            "unregulated",
            "confirm_policy_scope",
        ),
        ("synthetic-jurisdiction", rent_policy("exempt"), "exempt", "verify_property_exemption"),
        (
            "other-jurisdiction",
            rent_policy("unregulated"),
            "review_required",
            "verify_jurisdiction_policy",
        ),
        (
            "synthetic-jurisdiction",
            rent_policy(verified=False),
            "review_required",
            "verify_jurisdiction_policy",
        ),
        (
            "synthetic-jurisdiction",
            rent_policy(source_ids=()),
            "review_required",
            "verify_jurisdiction_policy",
        ),
    ],
)
def test_t021_ac3_rent_regulation_examples(jurisdiction, policy, expected, check):
    result = rules.evaluate("rent_regulation", {"jurisdiction": jurisdiction, "policy": policy})
    assert result.decision.classification == expected
    assert check in result.decision.required_checks
    if policy and policy.source_ids:
        assert policy.source_ids[0] in result.trace.source_ids


@pytest.mark.parametrize(
    "jurisdiction,policy,expected,check",
    [
        ("unknown", None, "review_required", "verify_jurisdiction_policy"),
        ("synthetic-jurisdiction", None, "review_required", "verify_jurisdiction_policy"),
        (
            "synthetic-jurisdiction",
            tax_policy(),
            "reassessment_required",
            "model_verified_tax_basis",
        ),
        (
            "synthetic-jurisdiction",
            tax_policy("periodic"),
            "periodic_review",
            "verify_reassessment_schedule",
        ),
        (
            "synthetic-jurisdiction",
            tax_policy("none_on_transfer"),
            "no_transfer_reassessment",
            "confirm_policy_scope",
        ),
        (
            "other-jurisdiction",
            tax_policy("none_on_transfer"),
            "review_required",
            "verify_jurisdiction_policy",
        ),
        (
            "synthetic-jurisdiction",
            tax_policy(verified=False),
            "review_required",
            "verify_jurisdiction_policy",
        ),
        (
            "synthetic-jurisdiction",
            tax_policy(source_ids=()),
            "review_required",
            "verify_jurisdiction_policy",
        ),
    ],
)
def test_t021_ac3_tax_reassessment_examples(jurisdiction, policy, expected, check):
    result = rules.evaluate("tax_reassessment", {"jurisdiction": jurisdiction, "policy": policy})
    assert result.decision.classification == expected
    assert check in result.decision.required_checks


def test_t021_ac1_configurable_policy_identity_and_hash():
    default = rules.evaluate("buy_box.default", buy())
    modified = rules.evaluate(
        "buy_box.default",
        buy(policy=BuyBoxPolicy(min_dscr=D("1.5"), policy_id="firm-policy-2", version="7")),
    )
    assert modified.decision.classification == "ineligible"
    assert modified.trace.policy_id == "firm-policy-2"
    assert modified.trace.policy_version == "7"
    assert modified.trace.policy_sha256 != default.trace.policy_sha256
    assert modified.trace.table_sha256 == default.trace.table_sha256


@given(st.integers(min_value=-(2**53 - 1), max_value=2**53 - 1))
def test_t021_ac1_exact_scaled_integer_transport(integer):
    digits = tuple(int(d) for d in str(abs(integer)))
    with localcontext() as ctx:
        ctx.prec = 2
        assert scaled(D((int(integer < 0), digits, -6)), 6) == integer


def test_t021_ac1_boundaries_at_maximum_exact_integer():
    policy = BuyBoxPolicy(max_price=D("90071992547409.90"))
    assert (
        rules.evaluate(
            "buy_box.default", buy(price=D("90071992547409.90"), policy=policy)
        ).decision.classification
        == "eligible"
    )
    assert (
        rules.evaluate(
            "buy_box.default", buy(price=D("90071992547409.91"), policy=policy)
        ).decision.classification
        == "ineligible"
    )
    with pytest.raises(ValidationError, match="exact integer range"):
        rules.evaluate("buy_box.default", buy(price=D("90071992547409.92")))


def test_t021_ac1_typed_replay_without_mutation():
    item = BuyBoxInput(**buy(source_ids=("fact-1",)))
    before = item.model_dump()
    result = rules.evaluate("buy_box.default", item)
    replay = BuyBoxInput.model_validate_json(result.trace.input_json)
    assert rules.evaluate("buy_box.default", replay) == result
    assert item.model_dump() == before
    with pytest.raises(ValidationError):
        item.units = 1
    with pytest.raises(ValidationError):
        rules.evaluate("buy_box.default", BuyBoxInput.model_construct(**buy(dscr=1.25)))


def test_t021_ac1_configurable_assumption_profiles_and_ambiguity():
    profile = AssumptionProfile(
        profile_id="firm-C-modern",
        market_tier="C",
        asset_class="B",
        min_vintage=1980,
        min_rent_growth=D("0"),
        max_rent_growth=D("0.02"),
        min_cap_rate=D("0.04"),
        max_cap_rate=D("0.07"),
    )
    policy = AssumptionPolicy(policy_id="firm-range", version="4", profiles=(profile,))
    result = rules.evaluate(
        "assumption_ranges.mf", assumption(market_tier="C", rent_growth=D("0.02"), policy=policy)
    )
    assert result.decision.classification == "within_policy"
    assert result.trace.profile_id == "firm-C-modern"
    assert (
        rules.evaluate(
            "assumption_ranges.mf",
            assumption(market_tier="C", rent_growth=D("0.020001"), policy=policy),
        ).decision.classification
        == "outside_policy"
    )
    with pytest.raises(ValidationError, match="overlap"):
        AssumptionPolicy(profiles=(profile, profile.model_copy(update={"profile_id": "other"})))
    with pytest.raises(ValidationError, match="upper bounds"):
        AssumptionProfile(
            profile_id="bad",
            market_tier="A",
            asset_class="A",
            min_rent_growth=D("0.07"),
            max_rent_growth=D("0.06"),
        )


@pytest.mark.parametrize("table", ["rent_regulation", "tax_reassessment"])
def test_t021_ac2_unknown_jurisdiction_never_becomes_cleared(table):
    cls = RentPolicy if table == "rent_regulation" else TaxPolicy
    status = "unregulated" if table == "rent_regulation" else "none_on_transfer"
    policy = cls(jurisdiction="unknown", status=status, verified=True, source_ids=("evidence-1",))
    assert (
        rules.evaluate(table, {"jurisdiction": "unknown", "policy": policy}).decision.classification
        == "review_required"
    )
