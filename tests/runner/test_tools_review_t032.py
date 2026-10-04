"""Five independent review regressions; offline interleavings only."""

from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import openpyxl
import pytest
from sqlalchemy import select
from tests.gates import conftest as gate_fixtures
from tests.gates import test_t037_workbook as workbook_fixtures
from tests.runner import test_tools_t032 as fixtures
from tests.runner.test_tools_t032 import Gates, artifact

from cre_brain.domain import CalcResult, Deliverable, DeliverableKind, Fact
from cre_brain.domain.base import TenantScope
from cre_brain.gates import GatePlan, GateService, TrustedInputs
from cre_brain.runner.policy import HostContext, Limits, Refusal
from cre_brain.runner.tools import files
from cre_brain.runner.tools.contracts import Artifact
from cre_brain.state.store import SqlVersionedStore

tools = fixtures.tools
gate_env = gate_fixtures.gate_env
workbook_env = workbook_fixtures.workbook_env


def test_tools_review_external_body_uses_authenticated_bytes(tools, monkeypatch):
    registry, inputs = tools
    d = artifact(tools, DeliverableKind.BROKER_QUESTIONS)
    approved = b"NOI $100000"
    unapproved = b"NOI $999999"
    Path(d.path).write_bytes(approved)
    inputs.artifacts[d.d_id] = inputs.artifacts[d.d_id].model_copy(
        update={"sha256": files.digest(approved)}
    )
    registry.gates = Gates(registry.context.scope)
    assert registry.call("finalize_deliverable", {"deliverable_id": d.d_id})["status"] == "ok"
    sent = []

    class Connector:
        scope = registry.context.scope
        allowed_recipients = frozenset({"host-recipient"})

        def send(self, **kwargs):
            sent.append(kwargs)
            return "receipt"

    registry.connectors["email_brokers"] = Connector()
    registry.set_host_toggles(email_brokers="on")
    draft = registry.call(
        "draft_external",
        {
            "kind": "email_brokers",
            "to": "host-recipient",
            "body": unapproved.decode(),
            "deliverable_id": d.d_id,
        },
    )
    real_read = files.read
    reads = []

    def interleaved(root, path):
        if str(path) == d.path:
            reads.append(path)
            return approved if len(reads) % 2 else unapproved
        return real_read(root, path)

    monkeypatch.setattr(files, "read", interleaved)
    result = registry.call("send_external", {"draft_id": draft["data"]["draft_id"]})
    assert result["status"] == "refused", result
    assert sent == []
    with registry.transaction() as state:
        assert not any("send_key" in e.payload for e in state.history())


@pytest.mark.parametrize("suffix", [".md", ".xlsx"])
def test_tools_review_real_gates_check_digest_bound_snapshot(tools, workbook_env, suffix):
    registry, inputs = tools
    directory = registry.workspace / "deals" / "deal" / "deliverables"
    directory.mkdir(parents=True)
    path = directory / ("memo" + suffix)
    d = Deliverable(
        d_id="memo",
        deal_ids=["deal"],
        kind=DeliverableKind.BROKER_QUESTIONS,
        version=1,
        status="draft",
        path=str(path),
        gate_results=[],
        depends_on=[],
    )
    gate_inputs = TrustedInputs()
    plan = GatePlan()
    approved = b"No numeric claims"
    unapproved = b"Unsupported NOI $999999"
    if suffix == ".xlsx":
        original_service, workbook_d, output, _ = workbook_env
        approved = output.read_bytes()
        book = openpyxl.load_workbook(BytesIO(approved))
        book["Inputs"]["B20"] = 999999
        stream = BytesIO()
        book.save(stream)
        book.close()
        unapproved = stream.getvalue()
        # Reuse T037's synthetic canonical evidence and saved workbook caches.
        gate_inputs = original_service.inputs
        plan = gate_inputs.plan(registry.context.scope, workbook_d)
        for model in (Fact, CalcResult):
            source = SqlVersionedStore(original_service.engine, model)
            with original_service.engine.connect() as connection:
                payloads = connection.execute(select(source.table.c.payload)).scalars().all()
            for payload in payloads:
                SqlVersionedStore(registry.engine, model).append(
                    model.model_validate(payload), scope=registry.context.scope
                )
    path.write_bytes(unapproved)
    SqlVersionedStore(registry.engine, Deliverable).append(d, scope=registry.context.scope)
    inputs.artifacts[d.d_id] = Artifact(deliverable=d, sha256=files.digest(unapproved))
    gate_inputs.put_plan(registry.context.scope, d, plan)
    service = GateService(
        registry.engine,
        scope=registry.context.scope,
        settings=registry.settings.gates,
        inputs=gate_inputs,
        scratch=registry.workspace.parent / "trusted-scratch",
    )

    path.write_bytes(approved)
    assert service.check("number_provenance", d).passed
    path.write_bytes(unapproved)

    class InterleavingProvider:
        scope = registry.context.scope

        def check(self, name, deliverable):
            path.write_bytes(approved)
            try:
                return service.check(name, deliverable)
            finally:
                path.write_bytes(unapproved)

        def check_bytes(self, name, deliverable, snapshot):
            path.write_bytes(approved)
            try:
                return service.check_bytes(name, deliverable, snapshot)
            finally:
                path.write_bytes(unapproved)

    registry.gates = InterleavingProvider()
    result = registry.call("finalize_deliverable", {"deliverable_id": d.d_id})
    assert result.get("category") == "gate_failure", result
    assert (
        SqlVersionedStore(registry.engine, Deliverable)
        .get(d.d_id, scope=registry.context.scope)
        .status
        == "draft"
    )
    with registry.transaction() as state:
        assert not any(e.kind == "deliverable" for e in state.history())
        assert len([e for e in state.history() if e.kind == "gate_result"]) == 1
    assert not service.scratch.exists() or list(service.scratch.iterdir()) == []
    # The real adapter also releases a valid digest-bound artifact.
    path.write_bytes(approved)
    inputs.artifacts[d.d_id] = Artifact(deliverable=d, sha256=files.digest(approved))
    registry.gates = service
    result = registry.call("finalize_deliverable", {"deliverable_id": d.d_id}, request_id="valid")
    assert result["status"] == "ok", result
    assert list(service.scratch.iterdir()) == []


def test_tools_review_partial_toggles_merge_latest_durable_policy(tools):
    registry, _ = tools
    registry.settings = registry.settings.model_copy(
        update={"toggles": registry.settings.toggles.model_copy(update={"email_brokers": "on"})}
    )
    registry.set_host_toggles(email_brokers="off")
    registry.clone().set_host_toggles(send_loi="ask")
    with registry.transaction() as state:
        updates = [
            e.payload["host_toggles"] for e in state.history() if "host_toggles" in e.payload
        ]
    assert updates[-1]["email_brokers"] == "off"
    assert updates[-1]["send_loi"] == "ask"


def test_tools_review_toggles_shared_but_tenant_and_task_ledgers_isolated(tools, monkeypatch):
    import cre_brain.runner.tools.state as state_module

    registry, _ = tools
    other = registry.clone(
        context=HostContext.model_validate({**registry.context.model_dump(), "task_id": "task-b"})
    )
    outsider = registry.clone(
        context=HostContext.model_validate(
            {
                **registry.context.model_dump(),
                "scope": TenantScope(user_id="other", firm_id="firm"),
            }
        )
    )
    outsider.set_host_toggles(email_brokers="ask")
    frozen = datetime.now(UTC)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen

    monkeypatch.setattr(state_module, "datetime", Clock)
    # Equal clocks, different task sequence lengths: commit order must win.
    with other.transaction() as state:
        for _ in range(5):
            state.event("tool_result", {"padding": True})
    other.set_host_toggles(email_brokers="on")
    registry.set_host_toggles(email_brokers="off")
    registry.clone().set_host_toggles(send_loi="ask")
    draft_args = {"kind": "email_brokers", "to": "host-recipient", "body": "Local draft"}
    draft = other.call("draft_external", draft_args, request_id="same-request")
    response = other.clone().call("send_external", {"draft_id": draft["data"]["draft_id"]})
    assert response.get("category") == "policy_off", response
    outside_draft = outsider.call("draft_external", draft_args, request_id="same-request")
    pending = outsider.call("send_external", {"draft_id": outside_draft["data"]["draft_id"]})
    assert pending["status"] == "pending_confirmation"
    registry.set_host_toggles(email_brokers="ask")
    local_draft = registry.call("draft_external", draft_args, request_id="same-request")
    local_pending = registry.call("send_external", {"draft_id": local_draft["data"]["draft_id"]})
    assert local_pending["status"] == "pending_confirmation"
    with pytest.raises(Refusal):
        other.confirm(local_pending["cid"])
    with pytest.raises(Refusal):
        outsider.confirm(local_pending["cid"])
    other.set_host_toggles(email_brokers="off")
    assert (
        registry.call("send_external", {"draft_id": local_draft["data"]["draft_id"]})["category"]
        == "policy_off"
    )
    registry.confirm(local_pending["cid"])
    with other.transaction() as state:
        assert not other.confirmed(state, local_pending["cid"])
    with outsider.transaction() as state:
        assert not outsider.confirmed(state, local_pending["cid"])
    assert (
        len(
            {
                draft["data"]["draft_id"],
                local_draft["data"]["draft_id"],
                outside_draft["data"]["draft_id"],
            }
        )
        == 3
    )


def test_tools_review_deadline_rechecked_after_last_artifact_read(tools, monkeypatch):
    import cre_brain.runner.policy as policy_module
    import cre_brain.runner.tools.registry as registry_module

    registry, _ = tools
    d = artifact(tools)
    registry.gates = Gates(registry.context.scope)
    registry.limits = Limits(max_wallclock_s=1, max_session_s=1)
    start = datetime.now(UTC)
    elapsed = [timedelta()]
    reads = []
    real_read = files.read

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return start + elapsed[0]

    def expiring_read(root, path):
        data = real_read(root, path)
        if str(path) == d.path:
            reads.append(path)
            if len(reads) == 2:
                elapsed[0] = timedelta(seconds=2)
        return data

    monkeypatch.setattr(policy_module, "datetime", Clock)
    monkeypatch.setattr(registry_module, "datetime", Clock)
    monkeypatch.setattr(files, "read", expiring_read)
    result = registry.call("finalize_deliverable", {"deliverable_id": d.d_id})
    assert result.get("category") == "budget_exceeded", result
    assert (
        SqlVersionedStore(registry.engine, Deliverable)
        .get(d.d_id, scope=registry.context.scope)
        .status
        == "draft"
    )
    with registry.transaction() as state:
        assert not any(e.kind in {"gate_result", "deliverable"} for e in state.history())
