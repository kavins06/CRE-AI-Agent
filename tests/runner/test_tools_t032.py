"""Offline T032 plumbing and adversarial boundary evidence; no analyst-quality claim."""

import hashlib
import io
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from typer.testing import CliRunner

from cre_brain.config import load
from cre_brain.domain import CalcResult, ClaimType, Deliverable, DeliverableKind, Fact, GateResult
from cre_brain.domain.base import TenantScope
from cre_brain.domain.models import Provenance
from cre_brain.runner.policy import HostContext, Limits
from cre_brain.runner.tools.contracts import Artifact, FactAnchor, Template
from cre_brain.runner.tools.registry import CORE_TOOLS, ToolRegistry
from cre_brain.state.schema import metadata
from cre_brain.state.store import SqlVersionedStore


class Inputs:
    def __init__(self):
        self.anchors = {}
        self.artifacts = {}
        self.templates = {}
        self.policies = {}

    def fact(self, context, identity):
        return self.anchors.get(identity)

    def artifact(self, context, identity):
        return self.artifacts.get(identity)

    def template(self, context, identity):
        return self.templates.get(identity)

    def rule_policy(self, context, table):
        return self.policies.get(table)


class Gates:
    def __init__(self, scope, fail=None):
        self.scope = scope
        self.fail = fail
        self.calls = []

    def check(self, name, deliverable):
        self.calls.append(name)
        return GateResult(
            passed=name != self.fail, failures=["denied"] if name == self.fail else [], metrics={}
        )


@pytest.fixture
def tools(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'state.db'}", connect_args={"check_same_thread": False}
    )
    metadata.create_all(engine)
    context = HostContext(
        scope=TenantScope(user_id="user", firm_id="firm"),
        task_id="task",
        deal_id="deal",
        role="lead",
        session_id="session",
        release_id="release",
        started_at=datetime.now(UTC),
    )
    root = tmp_path / "workspace"
    root.mkdir()
    inputs = Inputs()
    registry = ToolRegistry(
        engine=engine,
        context=context,
        workspace=root,
        inputs=inputs,
        settings=load(apply_environment=False),
    )
    yield registry, inputs
    engine.dispose()


def put(tools, key, value, unit="USD", claim=ClaimType.VERIFIED_FACT):
    registry, inputs = tools
    fact = Fact(
        fact_id=key,
        deal_id="deal",
        key=key,
        value=Decimal(value),
        unit=unit,
        claim_type=claim,
        provenance=[Provenance(doc_id="host-source", page=1)],
        known_at=datetime.now(UTC),
        version=1,
    )
    inputs.anchors[key] = FactAnchor(fact=fact, authority="verified_source")
    response = registry.call("facts_put", {"anchor_id": key}, request_id=f"put-{key}")
    assert response["status"] == "ok", response
    return {"kind": "fact", "record_id": key, "version": 1, "key": key, "unit": unit}


def artifact(tools, kind=DeliverableKind.SCREEN):
    registry, inputs = tools
    directory = registry.workspace / "deals" / "deal" / "deliverables"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "memo.md"
    path.write_text("Host composed artifact")
    d = Deliverable(
        d_id="memo",
        deal_ids=["deal"],
        kind=kind,
        version=1,
        status="draft",
        path=str(path),
        gate_results=[],
        depends_on=[],
    )
    SqlVersionedStore(registry.engine, Deliverable).append(d, scope=registry.context.scope)
    inputs.artifacts["memo"] = Artifact(
        deliverable=d, sha256=hashlib.sha256(path.read_bytes()).hexdigest()
    )
    return d


def test_t032_ac1_tools_registry_and_fact_authority(tools):
    registry, _ = tools
    assert set(CORE_TOOLS) == {
        "facts_get",
        "facts_put",
        "assumption_set",
        "finance_run",
        "excel_build",
        "excel_recalc_parity",
        "rules_eval",
        "ask_user",
        "finalize_deliverable",
        "draft_external",
        "send_external",
    }
    ref = put(tools, "noi", "1000")
    assert registry.call("facts_get", {"reference": ref})["data"]["value"] == {
        "type": "decimal",
        "value": "1000",
    }
    assert (
        registry.call("facts_put", {"fact": {"claim_type": "verified_fact"}})["category"]
        == "invalid_input"
    )


@pytest.mark.parametrize(
    "change", [{"version": 2}, {"unit": "ratio"}, {"key": "price"}, {"deal_id": "other"}]
)
def test_t032_ac1_tools_reject_reference_forgery(tools, change):
    registry, _ = tools
    ref = put(tools, "noi", "1000")
    assert registry.call("facts_get", {"reference": {**ref, **change}})["status"] == "refused"


def test_t032_ac1_tools_unverified_fact_cannot_feed_finance(tools):
    registry, _ = tools
    ref = put(tools, "noi", "1000", claim=ClaimType.SELLER_ASSERTION)
    assert (
        registry.call("finance_run", {"fn": "calculate_exit", "args": {"forward_noi": ref}})[
            "status"
        ]
        == "refused"
    )


def exit_args(tools):
    return {
        key: put(tools, key, value, unit)
        for key, value, unit in [
            ("forward_noi", "1000", "USD"),
            ("cap_rate", "0.05", "ratio"),
            ("selling_cost_rate", "0.02", "ratio"),
            ("fixed_selling_cost", "100", "USD"),
            ("debt_payoff", "1000", "USD"),
        ]
    }


def test_t032_ac1_tools_deterministic_finance_lineage_and_no_dispatch(tools):
    registry, _ = tools
    response = registry.call(
        "finance_run", {"fn": "calculate_exit", "args": exit_args(tools)}, request_id="exit"
    )
    assert response["data"]["outputs"]["net_equity_proceeds"] == "18500"
    calc = SqlVersionedStore(registry.engine, CalcResult).get(
        response["data"]["calc_id"], scope=registry.context.scope
    )
    assert set(calc.inputs.values()) == {
        "forward_noi",
        "cap_rate",
        "selling_cost_rate",
        "fixed_selling_cost",
        "debt_payoff",
    }
    assert calc.code_version
    assert registry.call("finance_run", {"fn": "os.system", "args": {}})["status"] == "refused"
    assert (
        registry.call(
            "finance_run", {"fn": "calculate_exit", "args": {"forward_noi": "1000"}, "outputs": {}}
        )["category"]
        == "invalid_input"
    )


def test_t032_ac1_tools_proforma_preserves_below_noi_reserves(tools):
    registry, _ = tools
    args = {
        k: put(tools, k, v, u)
        for k, v, u in [
            ("base_monthly_revenue", "10000", "USD/month"),
            ("base_monthly_operating_expenses", "4000", "USD/month"),
            ("annual_revenue_growth", "0", "ratio"),
            ("annual_expense_growth", "0", "ratio"),
            ("vacancy_rate", "0", "ratio"),
            ("credit_loss_rate", "0", "ratio"),
            ("monthly_reserves", "500", "USD/month"),
            ("projection_months", "60", "count"),
        ]
    }
    response = registry.call("finance_run", {"fn": "build_proforma", "args": args})
    assert response["data"]["outputs"]["month:1:noi"] == "6000"
    assert response["data"]["outputs"]["month:1:cash_flow"] == "5500"


def test_t032_ac1_tools_ask_records_default_and_lineage(tools):
    registry, _ = tools
    default = put(tools, "cap_rate", "0.05", "ratio")
    artifact(tools)
    response = registry.call(
        "ask_user",
        {
            "question": "Confirm cap rate",
            "why": "Exit value",
            "default": default,
            "affects": ["memo"],
        },
        request_id="question",
    )
    assert response["status"] == "ok"
    assert response["data"]["status"] == "open"
    assert (
        registry.call(
            "ask_user",
            {"question": "Confirm", "why": "Why", "default": default, "affects": ["other-deal"]},
        )["status"]
        == "refused"
    )


def test_t032_ac1_tools_excel_refuses_untrusted_descriptor_and_missing_engine(tools):
    registry, _ = tools
    assert (
        registry.call("excel_build", {"template": "../../seller.xlsm", "calculation": "fake"})[
            "status"
        ]
        == "refused"
    )
    assert (
        registry.call("excel_recalc_parity", {"build": {"expected": {"x": "1"}}})["category"]
        == "invalid_input"
    )
    assert registry.call("excel_recalc_parity", {"artifact_id": "untrusted"})["status"] == "refused"


def test_t032_ac1_tools_rules_cannot_supply_policy_or_numbers(tools):
    registry, inputs = tools
    from cre_brain.rules.models import BuyBoxPolicy

    inputs.policies["buy_box.default"] = BuyBoxPolicy()
    units = put(tools, "units", "100", "count")
    response = registry.call("rules_eval", {"table": "buy_box.default", "input": {"units": units}})
    assert response["status"] == "ok"
    assert "trace" in response["data"]
    assert (
        registry.call(
            "rules_eval", {"table": "buy_box.default", "input": {"policy": {"min_dscr": "0"}}}
        )["status"]
        == "refused"
    )


def test_t032_ac2_tools_finalize_all_gates_and_idempotency(tools):
    registry, _ = tools
    artifact(tools)
    assert (
        registry.call("finalize_deliverable", {"deliverable_id": "memo"})["category"]
        == "missing_provider"
    )
    provider = Gates(registry.context.scope, "buy_box")
    registry.gates = provider
    denied = registry.call("finalize_deliverable", {"deliverable_id": "memo"})
    assert denied["category"] == "gate_failure"
    assert set(provider.calls) == {"coverage", "buy_box", "number_provenance"}
    provider.fail = None
    response = registry.call("finalize_deliverable", {"deliverable_id": "memo"}, request_id="final")
    assert response["data"]["status"] == "final"
    count = len(provider.calls)
    assert (
        registry.call("finalize_deliverable", {"deliverable_id": "memo"}, request_id="final")
        == response
    )
    assert len(provider.calls) == count
    assert (
        registry.call("finalize_deliverable", {"deliverable_id": "memo", "passed": True})[
            "category"
        ]
        == "invalid_input"
    )


def test_t032_ac2_tools_off_ask_and_confirmation_survive_registry_restart(tools):
    registry, _ = tools
    draft = registry.call(
        "draft_external",
        {"kind": "email_brokers", "to": "host-recipient", "body": "Local draft"},
        request_id="draft",
    )
    assert draft["status"] == "ok"
    draft_id = draft["data"]["draft_id"]
    assert registry.call("send_external", {"draft_id": draft_id})["category"] == "policy_off"
    registry.set_host_toggles(email_brokers="ask")
    pending = registry.call("send_external", {"draft_id": draft_id}, request_id="send")
    assert pending["status"] == "pending_confirmation"
    assert pending["cid"]
    again = registry.clone()
    assert again.call("send_external", {"draft_id": draft_id}, request_id="send") == pending
    assert (
        registry.call("send_external", {"draft_id": draft_id, "confirmed": True})["category"]
        == "invalid_input"
    )
    registry.confirm(pending["cid"])
    assert (
        registry.call("send_external", {"draft_id": draft_id}, request_id="send")["category"]
        == "missing_connector"
    )


def test_t032_ac2_tools_budget_concurrent_and_persistent(tools):
    registry, _ = tools
    registry.limits = Limits(max_tool_calls=3, max_session_calls=3)
    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(
            pool.map(
                lambda i: registry.clone().call("facts_get", {}, request_id=f"call-{i}"), range(8)
            )
        )
    assert sum(r.get("category") == "budget_exceeded" for r in responses) == 5
    assert registry.clone().call("facts_get", {})["category"] == "budget_exceeded"


def test_t032_ac3_tools_cli_mcp_identical_canonical_json(tools, monkeypatch):
    from cre_brain.cli import create_app
    from cre_brain.runner.tools import tools_commands
    from cre_brain.runner.tools.transport import handle_message, serve

    registry, _ = tools
    monkeypatch.setattr(tools_commands, "host_registry", lambda: registry)
    payload = {
        "reference": {
            "kind": "fact",
            "record_id": "missing",
            "version": 1,
            "key": "noi",
            "unit": "USD",
        }
    }
    result = CliRunner().invoke(create_app(), ["tool", "facts_get", "--args", json.dumps(payload)])
    rpc = handle_message(
        registry,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "facts_get", "arguments": payload},
        },
    )
    assert result.exit_code == 0
    assert result.output.strip() == rpc["result"]["content"][0]["text"]
    stdin = io.StringIO(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}) + "\n")
    stdout = io.StringIO()
    serve(registry, stdin, stdout)
    assert len(json.loads(stdout.getvalue())["result"]["tools"]) == len(CORE_TOOLS)


@pytest.mark.parametrize(
    "raw", ['{"x":1,"x":2}', "[" * 40 + "0" + "]" * 40, '{"x":NaN}', '{"x":1e999}']
)
def test_t032_ac3_tools_json_fail_closed(tools, raw):
    assert tools[0].call_json("facts_get", raw)["category"] == "invalid_input"


def test_t032_ac3_tools_root_help_and_missing_context(monkeypatch):
    from cre_brain.cli import create_app
    from cre_brain.runner.tools import tools_commands

    monkeypatch.setattr(tools_commands, "_host_factory", None)
    assert CliRunner().invoke(create_app(), ["--help"]).exit_code == 0
    result = CliRunner().invoke(create_app(), ["tool", "facts_get", "--args", "{}"])
    assert json.loads(result.output)["category"] == "missing_context"


def proforma_args(tools):
    return {
        k: put(tools, k, v, u)
        for k, v, u in [
            ("base_monthly_revenue", "10000", "USD/month"),
            ("base_monthly_operating_expenses", "4000", "USD/month"),
            ("annual_revenue_growth", "0", "ratio"),
            ("annual_expense_growth", "0", "ratio"),
            ("vacancy_rate", "0", "ratio"),
            ("credit_loss_rate", "0", "ratio"),
            ("monthly_reserves", "500", "USD/month"),
            ("projection_months", "60", "count"),
        ]
    }


def test_t032_ac1_tools_excel_build_and_parity_are_server_owned(tools):
    from cre_brain.excel.build_template import build_template

    registry, inputs = tools
    path, mapping = build_template(
        registry.workspace.parent / "templates", gates=registry.settings.gates
    )
    inputs.templates["mf_standard"] = Template(
        path=path, mapping=mapping, sha256=hashlib.sha256(path.read_bytes()).hexdigest()
    )
    calc = registry.call("finance_run", {"fn": "build_proforma", "args": proforma_args(tools)})
    response = registry.call(
        "excel_build",
        {"template": "mf_standard", "calculation": calc["data"]["calc_id"]},
        request_id="build",
    )
    assert response["status"] == "ok", response
    artifact_id = response["data"]["artifact_id"]
    assert (
        registry.call("excel_recalc_parity", {"artifact_id": artifact_id})["category"]
        == "missing_provider"
    )

    class NoRecalc:
        def recalc(self, path):
            return path

    registry.excel_engine = NoRecalc()
    parity = registry.call("excel_recalc_parity", {"artifact_id": artifact_id})
    assert parity["status"] == "ok", parity
    assert (
        parity["data"]["parity"]["passed"] is False
    )  # No cached values means no invented parity PASS.
    path.write_bytes(b"changed host template")
    assert (
        registry.call(
            "excel_build",
            {"template": "mf_standard", "calculation": calc["data"]["calc_id"]},
            request_id="changed-template",
        )["status"]
        == "refused"
    )


@pytest.mark.parametrize(
    "flows,flag", [(["-100", "230", "-132"], "ambiguous"), (["1", "2"], "undefined")]
)
def test_t032_ac1_tools_returns_keep_ambiguous_and_undefined(tools, flows, flag):
    registry, _ = tools
    refs = [put(tools, f"flow-{i}", value) for i, value in enumerate(flows)]
    rate = put(tools, "finance_rate", "0.05", "ratio")
    response = registry.call(
        "finance_run",
        {
            "fn": "calculate_returns",
            "args": {"cash_flows": refs, "finance_rate": rate, "reinvest_rate": rate},
        },
    )
    assert response["status"] == "ok", response
    assert response["data"]["outputs"][flag] == "1"
    assert "irr" not in response["data"]["outputs"]
    if flag == "ambiguous":
        assert "mirr" in response["data"]["outputs"]


def test_t032_ac1_tools_assumption_revision_uses_fresh_identity(tools):
    registry, inputs = tools
    ref = put(tools, "cap_rate", "0.05", "ratio")
    request = {
        "key": "exit_cap",
        "value": ref,
        "low": ref,
        "high": ref,
        "rationale": "Host default",
    }
    first = registry.call("assumption_set", request, request_id="assumption-1")
    old = inputs.anchors["cap_rate"].fact
    updated = Fact.model_validate({**old.model_dump(), "version": 2, "value": Decimal("0.06")})
    inputs.anchors["revision"] = FactAnchor(fact=updated, authority="verified_source")
    assert (
        registry.call("facts_put", {"anchor_id": "revision"}, request_id="revision")["status"]
        == "ok"
    )
    next_ref = {**ref, "version": 2}
    second = registry.call(
        "assumption_set",
        {**request, "value": next_ref, "low": next_ref, "high": next_ref},
        request_id="assumption-2",
    )
    assert second["status"] == "ok", second
    assert first["data"]["record_id"] != second["data"]["record_id"]
    args = {
        key: put(tools, key, value, unit)
        for key, value, unit in [
            ("forward_noi", "1000", "USD"),
            ("selling_cost_rate", "0.02", "ratio"),
            ("fixed_selling_cost", "100", "USD"),
            ("debt_payoff", "1000", "USD"),
        ]
    }
    args["cap_rate"] = {
        "kind": "assumption",
        "record_id": second["data"]["record_id"],
        "version": 1,
        "key": "exit_cap",
        "unit": "ratio",
    }
    result = registry.call("finance_run", {"fn": "calculate_exit", "args": args})
    assert result["status"] == "ok", result


def test_t032_ac2_tools_advisory_does_not_block_and_missing_checker_fails(tools):
    registry, _ = tools
    artifact(tools, kind=DeliverableKind.IC_MEMO)
    registry.gates = Gates(registry.context.scope, "entailment")
    response = registry.call("finalize_deliverable", {"deliverable_id": "memo"})
    assert response["status"] == "ok", response
    assert set(registry.gates.calls) == {
        "number_provenance",
        "numbers_match_model",
        "required_sections",
        "entailment",
    }


def test_t032_ac2_tools_finalize_new_request_id_cannot_duplicate_transition(tools):
    registry, _ = tools
    artifact(tools)
    registry.gates = Gates(registry.context.scope)
    first = registry.call("finalize_deliverable", {"deliverable_id": "memo"}, request_id="final-1")
    second = registry.call("finalize_deliverable", {"deliverable_id": "memo"}, request_id="final-2")
    assert first == second
    assert len(registry.gates.calls) == 3


def test_t032_ac2_tools_host_usage_and_session_policy_cannot_reset(tools):
    registry, _ = tools
    registry.limits = Limits(max_tokens=5)
    registry.record_host_tokens(5)
    assert registry.clone().call("facts_get", {})["category"] == "budget_exceeded"
    with pytest.raises(ValueError):
        registry.record_host_tokens(-1)


def test_t032_ac3_tools_stdio_duplicate_keys_and_oversize_are_errors(tools):
    from cre_brain.runner.tools.transport import serve

    for raw in [
        '{"jsonrpc":"2.0","id":1,"method":"tools/list","method":"tools/call"}\n',
        '{"x":"' + "a" * 150000 + '"}\n',
    ]:
        output = io.StringIO()
        serve(tools[0], io.StringIO(raw), output)
        assert json.loads(output.getvalue())["error"]["code"] == -32700


def test_t032_ac3_tools_cli_host_failure_is_sanitized(monkeypatch):
    from cre_brain.cli import create_app
    from cre_brain.runner.tools import tools_commands

    def broken():
        raise RuntimeError("password=DO_NOT_ECHO")

    monkeypatch.setattr(tools_commands, "host_registry", broken)
    response = CliRunner().invoke(create_app(), ["tool", "facts_get", "--args", "{}"])
    assert response.exception is None
    assert json.loads(response.output)["category"] == "missing_context"
    assert "DO_NOT_ECHO" not in response.output


def test_t032_ac1_tools_ambiguous_fact_keys_refuse(tools):
    registry, inputs = tools
    reference = put(tools, "noi", "1000")
    fact = inputs.anchors["noi"].fact
    alternate = Fact.model_validate({**fact.model_dump(), "fact_id": "alternate-noi"})
    inputs.anchors["alternate-noi"] = FactAnchor(fact=alternate, authority="verified_source")
    assert registry.call("facts_put", {"anchor_id": "alternate-noi"})["status"] == "ok"
    assert registry.call("facts_get", {"reference": reference})["category"] == "ambiguous_evidence"


def test_t032_ac2_tools_question_and_outbox_ids_are_task_scoped(tools):
    registry, _ = tools
    ref = put(tools, "cap_rate", "0.05", "ratio")
    other = registry.clone(
        context=HostContext.model_validate(
            {
                **registry.context.model_dump(),
                "task_id": "other-task",
                "session_id": "other-session",
            }
        )
    )
    question = {"question": "Confirm default", "why": "Exit", "default": ref, "affects": []}
    first = registry.call("ask_user", question, request_id="same-id")
    second = other.call("ask_user", question, request_id="same-id")
    assert first["data"]["q_id"] != second["data"]["q_id"]
    draft = {"kind": "email_brokers", "to": "host-recipient", "body": "Local draft"}
    first = registry.call("draft_external", draft, request_id="same-draft")
    second = other.call("draft_external", draft, request_id="same-draft")
    assert first["data"]["draft_id"] != second["data"]["draft_id"]


def test_t032_ac2_tools_binding_uses_latest_event_even_if_database_order_changes(
    tools, monkeypatch
):
    registry, _ = tools
    with registry.transaction() as state:
        state.event("tool_result", {"binding": "draft", "identity": "draft", "revision": 1})
        state.event("tool_result", {"binding": "draft", "identity": "draft", "revision": 2})
        history = sorted(state.history(), key=lambda event: event.ts, reverse=True)
        monkeypatch.setattr(state, "history", lambda **kwargs: history)
        assert state.binding("draft", "draft")["revision"] == 2


def test_t032_ac1_tools_diagnostic_flag_cannot_be_used_as_money(tools):
    registry, _ = tools
    args = exit_args(tools)
    flow = put(tools, "npv-flow", "100")
    npv = registry.call(
        "finance_run",
        {"fn": "excel_npv", "args": {"cash_flows": [flow], "discount_rate": args["cap_rate"]}},
    )
    assert npv["status"] == "ok", npv
    args["forward_noi"] = {
        "kind": "calc",
        "record_id": npv["data"]["calc_id"],
        "version": 1,
        "key": "pyxirr_consistent",
        "unit": "USD",
    }
    response = registry.call("finance_run", {"fn": "calculate_exit", "args": args})
    assert response["category"] == "incompatible_evidence"


def test_t032_ac1_tools_ask_returns_a_canonical_default_reference(tools):
    registry, _ = tools
    ref = put(tools, "cap_rate", "0.05", "ratio")
    response = registry.call(
        "ask_user", {"question": "Confirm default", "why": "Exit", "default": ref, "affects": []}
    )
    default = response["data"]["default_reference"]
    assert default["kind"] == "assumption"
    assert default["version"] == 1
    args = {
        key: put(tools, key, value, unit)
        for key, value, unit in [
            ("forward_noi", "1000", "USD"),
            ("selling_cost_rate", "0.02", "ratio"),
            ("fixed_selling_cost", "100", "USD"),
            ("debt_payoff", "1000", "USD"),
        ]
    }
    args["cap_rate"] = default
    assert registry.call("finance_run", {"fn": "calculate_exit", "args": args})["status"] == "ok"


def test_t032_ac1_tools_ask_supports_anchored_nonnumeric_defaults(tools):
    registry, inputs = tools
    fact = Fact(
        fact_id="market_tier",
        deal_id="deal",
        key="market_tier",
        value="unknown",
        unit="text",
        claim_type=ClaimType.VERIFIED_FACT,
        provenance=[],
        known_at=datetime.now(UTC),
        version=1,
    )
    inputs.anchors["user-tier"] = FactAnchor(fact=fact, authority="authorized_user")
    assert registry.call("facts_put", {"anchor_id": "user-tier"})["status"] == "ok"
    ref = {
        "kind": "fact",
        "record_id": "market_tier",
        "key": "market_tier",
        "unit": "text",
        "version": 1,
    }
    response = registry.call(
        "ask_user", {"question": "Confirm tier", "why": "Screening", "default": ref, "affects": []}
    )
    assert response["status"] == "ok", response
    assert response["data"]["default_used"] == "unknown"


def test_t032_ac1_tools_excel_engine_output_cannot_escape_before_parity(tools, monkeypatch):
    import cre_brain.excel.deliverable as product_excel
    from cre_brain.excel.build_template import build_template

    registry, inputs = tools
    path, mapping = build_template(
        registry.workspace.parent / "templates", gates=registry.settings.gates
    )
    inputs.templates["mf_standard"] = Template(
        path=path, mapping=mapping, sha256=hashlib.sha256(path.read_bytes()).hexdigest()
    )
    calc = registry.call("finance_run", {"fn": "build_proforma", "args": proforma_args(tools)})
    built = registry.call(
        "excel_build", {"template": "mf_standard", "calculation": calc["data"]["calc_id"]}
    )
    seen = []

    class EscapingEngine:
        def recalc(self, path):
            return registry.workspace.parent / "outside.xlsx"

    def forbid_read(path, *args, **kwargs):
        seen.append(path)
        raise AssertionError("Out-of-scope engine output must never reach the parity reader")

    monkeypatch.setattr(product_excel, "check_parity", forbid_read)
    registry.excel_engine = EscapingEngine()
    result = registry.call("excel_recalc_parity", {"artifact_id": built["data"]["artifact_id"]})
    assert result["category"] == "unauthorized_path"
    assert seen == []


def test_t032_ac1_tools_existing_fact_identity_cannot_move_between_deals(tools):
    registry, inputs = tools
    put(tools, "noi", "1000")
    old = inputs.anchors["noi"].fact
    inputs.anchors["moved"] = FactAnchor(
        fact=Fact.model_validate({**old.model_dump(), "deal_id": "other-deal", "version": 2}),
        authority="verified_source",
    )
    other = registry.clone(
        context=HostContext.model_validate(
            {
                **registry.context.model_dump(),
                "task_id": "other-task",
                "deal_id": "other-deal",
                "session_id": "other-session",
            }
        )
    )
    assert other.call("facts_put", {"anchor_id": "moved"})["category"] == "unauthorized_scope"
