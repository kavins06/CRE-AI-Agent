"""New T032 policy contracts: caller identities and PASS never confer authority."""

from datetime import UTC, datetime, timedelta

import pytest
from tests.runner import test_tools_t032 as tool_fixtures
from tests.runner.test_tools_t032 import Gates, artifact, exit_args, put

from cre_brain.runner.policy import HostContext, Limits
from cre_brain.runner.tools.contracts import FactAnchor

tools = tool_fixtures.tools


def test_t032_ac4_policy_contract_cross_scope_and_forged_context(tools):
    registry, _ = tools
    assert (
        registry.call("facts_get", {"scope": {"user_id": "other"}})["category"] == "invalid_input"
    )
    forged = registry.context.model_copy(update={"role": "administrator"})
    with pytest.raises(ValueError):
        registry.clone(context=forged)
    forged = HostContext.model_construct(**{**registry.context.model_dump(), "task_id": ""})
    with pytest.raises(ValueError):
        registry.clone(context=forged)


def test_t032_ac4_policy_contract_anchor_revalidation(tools):
    registry, inputs = tools
    put(tools, "noi", "100")
    anchor = inputs.anchors["noi"]
    inputs.anchors["forged"] = FactAnchor.model_construct(
        fact=anchor.fact.model_copy(update={"version": 0}), authority="verified_source"
    )
    assert registry.call("facts_put", {"anchor_id": "forged"})["category"] == "invalid_input"


@pytest.mark.parametrize("field", ["gates", "gate_results", "status", "path", "scope", "kind"])
def test_t032_ac4_policy_contract_caller_cannot_choose_gates(tools, field):
    registry, _ = tools
    artifact(tools)
    registry.gates = Gates(registry.context.scope)
    assert (
        registry.call("finalize_deliverable", {"deliverable_id": "memo", field: "PASS"})["category"]
        == "invalid_input"
    )


def test_t032_ac4_policy_contract_modified_artifact_and_advisory(tools):
    registry, _ = tools
    d = artifact(tools)
    registry.gates = Gates(registry.context.scope)
    from pathlib import Path

    Path(d.path).write_text("Changed artifact")
    assert registry.call("finalize_deliverable", {"deliverable_id": "memo"})["status"] == "refused"
    assert registry.gates.calls == []


def test_t032_ac4_policy_contract_time_and_host_limits(tools):
    registry, _ = tools
    expired = registry.context.model_copy(
        update={"started_at": datetime.now(UTC) - timedelta(hours=2)}
    )
    assert registry.clone(context=expired).call("facts_get", {})["category"] == "budget_exceeded"
    with pytest.raises(ValueError):
        registry.clone(limits=Limits.model_construct(max_tool_calls=-1))


def test_t032_ac4_policy_contract_concurrent_finalize(tools):
    from concurrent.futures import ThreadPoolExecutor

    registry, _ = tools
    artifact(tools)
    registry.gates = Gates(registry.context.scope)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda _: registry.clone().call(
                    "finalize_deliverable", {"deliverable_id": "memo"}, request_id="final"
                ),
                range(4),
            )
        )
    assert all(r == results[0] for r in results)
    assert results[0]["data"]["status"] == "final"
    assert len(registry.gates.calls) == 3


def test_t032_ac4_policy_contract_outbox_symlink_and_errors_redacted(tools):
    registry, inputs = tools
    outside = registry.workspace.parent / "outside"
    outside.mkdir()
    (registry.workspace / "outbox").symlink_to(outside, target_is_directory=True)
    response = registry.call(
        "draft_external", {"kind": "email_brokers", "to": "host-recipient", "body": "safe"}
    )
    assert response["status"] == "refused"
    assert list(outside.iterdir()) == []

    def broken(*args):
        raise RuntimeError("credential=DO_NOT_ECHO seller@example.invalid")

    inputs.fact = broken
    response = registry.call("facts_put", {"anchor_id": "x"})
    assert "DO_NOT_ECHO" not in str(response)
    assert "seller@" not in str(response)


def test_t032_ac4_policy_contract_calculation_refuses_changed_or_divergent_sources(tools):
    from decimal import Decimal

    from cre_brain.domain import CalcResult, Fact
    from cre_brain.state.store import SqlVersionedStore

    registry, inputs = tools
    args = exit_args(tools)
    result = registry.call("finance_run", {"fn": "calculate_exit", "args": args})
    identity = result["data"]["calc_id"]
    calc = SqlVersionedStore(registry.engine, CalcResult).get(
        identity, scope=registry.context.scope
    )
    poisoned = CalcResult.model_validate(
        {**calc.model_dump(), "outputs": {**calc.outputs, "net_equity_proceeds": Decimal("999999")}}
    )
    SqlVersionedStore(registry.engine, CalcResult).append(poisoned, scope=registry.context.scope)
    assert (
        registry.call("finance_run", {"fn": "calculate_exit", "args": args})["status"] == "refused"
    )
    old = inputs.anchors["forward_noi"].fact
    inputs.anchors["new-noi"] = FactAnchor(
        fact=Fact.model_validate({**old.model_dump(), "version": 2, "value": Decimal("1200")}),
        authority="verified_source",
    )
    assert registry.call("facts_put", {"anchor_id": "new-noi"})["status"] == "ok"
    assert (
        registry.call("finance_run", {"fn": "calculate_exit", "args": args})["category"]
        == "stale_evidence"
    )


def test_t032_ac4_policy_contract_unbound_sql_fact_and_user_authorized_fact(tools):
    from cre_brain.domain import Fact
    from cre_brain.state.store import SqlVersionedStore

    registry, inputs = tools
    ref = put(tools, "noi", "100")
    existing = inputs.anchors["noi"].fact
    unknown = Fact.model_validate({**existing.model_dump(), "fact_id": "unknown", "key": "unknown"})
    SqlVersionedStore(registry.engine, Fact).append(unknown, scope=registry.context.scope)
    assert (
        registry.call(
            "facts_get", {"reference": {**ref, "record_id": "unknown", "key": "unknown"}}
        )["category"]
        == "untrusted_evidence"
    )
    inputs.anchors["user-value"] = FactAnchor(
        fact=Fact.model_validate(
            {
                **existing.model_dump(),
                "fact_id": "user-value",
                "key": "user-value",
                "provenance": [],
            }
        ),
        authority="authorized_user",
    )
    assert registry.call("facts_put", {"anchor_id": "user-value"})["status"] == "ok"
    assert (
        registry.call(
            "facts_get", {"reference": {**ref, "record_id": "user-value", "key": "user-value"}}
        )["status"]
        == "ok"
    )


def test_t032_ac4_policy_contract_finalize_budget_expiration_and_missing_gates(tools):
    from datetime import UTC, datetime, timedelta

    registry, _ = tools
    artifact(tools)

    class ExpiringGates(Gates):
        def check(self, name, deliverable):
            registry.context = HostContext.model_validate(
                {
                    **registry.context.model_dump(),
                    "started_at": datetime.now(UTC) - timedelta(hours=2),
                }
            )
            return super().check(name, deliverable)

    registry.gates = ExpiringGates(registry.context.scope)
    assert registry.call("finalize_deliverable", {"deliverable_id": "memo"})["status"] == "refused"


def test_t032_ac4_policy_contract_final_replay_cannot_bless_new_draft(tools):
    import hashlib
    from pathlib import Path

    from cre_brain.domain import Deliverable
    from cre_brain.runner.tools.contracts import Artifact
    from cre_brain.state.store import SqlVersionedStore

    registry, inputs = tools
    d = artifact(tools)
    registry.gates = Gates(registry.context.scope)
    assert (
        registry.call("finalize_deliverable", {"deliverable_id": "memo"}, request_id="final")[
            "status"
        ]
        == "ok"
    )
    Path(d.path).write_text("New canonical draft")
    new_d = Deliverable.model_validate({**d.model_dump(), "version": 3})
    SqlVersionedStore(registry.engine, Deliverable).append(new_d, scope=registry.context.scope)
    inputs.artifacts["memo"] = Artifact(
        deliverable=new_d, sha256=hashlib.sha256(Path(d.path).read_bytes()).hexdigest()
    )
    assert (
        registry.call("finalize_deliverable", {"deliverable_id": "memo"}, request_id="final")[
            "status"
        ]
        == "refused"
    )


def test_t032_ac4_policy_contract_scope_and_gate_provider_cannot_forge_pass(tools):
    from cre_brain.domain import GateResult
    from cre_brain.domain.base import TenantScope

    registry, _ = tools
    artifact(tools)
    registry.gates = Gates(TenantScope(user_id="other", firm_id="firm"))
    assert (
        registry.call("finalize_deliverable", {"deliverable_id": "memo"})["category"]
        == "unauthorized_scope"
    )

    class ForgedGates(Gates):
        def check(self, name, deliverable):
            self.calls.append(name)
            return GateResult.model_construct(passed=True, failures=[], metrics={"bad": "NaN"})

    registry.gates = ForgedGates(registry.context.scope)
    response = registry.call("finalize_deliverable", {"deliverable_id": "memo"})
    assert response["category"] == "gate_failure"
    assert len(registry.gates.calls) == 3


def test_t032_ac4_policy_contract_forged_models_never_log_low_level_values(tools):
    import warnings

    from cre_brain.domain import GateResult

    registry, _ = tools
    artifact(tools)

    class InvalidGates(Gates):
        def check(self, name, deliverable):
            return GateResult.model_construct(
                passed=True, failures=[], metrics={"bad": "password=DO_NOT_ECHO"}
            )

    registry.gates = InvalidGates(registry.context.scope)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        response = registry.call("finalize_deliverable", {"deliverable_id": "memo"})
    assert response["category"] == "gate_failure"
    assert not any("DO_NOT_ECHO" in str(w.message) for w in caught)


def test_t032_ac4_policy_contract_confirmed_send_still_requires_released_artifact(tools):
    registry, _ = tools

    class RefuseExecution:
        scope = registry.context.scope
        allowed_recipients = frozenset({"host-recipient"})

        def send(self, **kwargs):
            raise AssertionError("No connector sends are allowed in this offline test")

    registry.connectors["send_loi"] = RefuseExecution()
    draft = registry.call(
        "draft_external",
        {"kind": "send_loi", "to": "host-recipient", "body": "Model-authored price 999999"},
    )
    registry.set_host_toggles(send_loi="on")
    response = registry.call("send_external", {"draft_id": draft["data"]["draft_id"]})
    assert response["category"] == "untrusted_artifact"


def test_t032_ac4_policy_contract_task_deadline_cannot_elapse_inside_gates(tools, monkeypatch):
    import cre_brain.runner.policy as policy_module
    import cre_brain.runner.tools.registry as registry_module

    registry, _ = tools
    artifact(tools)
    registry.limits = Limits(max_wallclock_s=1, max_session_s=3600)
    elapsed = [timedelta()]
    real_datetime = datetime

    class Clock(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return real_datetime.now(tz) + elapsed[0]

    class SlowGates(Gates):
        def check(self, name, deliverable):
            elapsed[0] = timedelta(seconds=2)
            return super().check(name, deliverable)

    monkeypatch.setattr(policy_module, "datetime", Clock)
    monkeypatch.setattr(registry_module, "datetime", Clock)
    registry.gates = SlowGates(registry.context.scope)
    response = registry.call("finalize_deliverable", {"deliverable_id": "memo"})
    assert response["category"] == "budget_exceeded"
