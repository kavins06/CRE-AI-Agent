"""Offline causal regressions for durable charging and lead lifetime ownership."""

import json
from contextlib import contextmanager
from pathlib import Path

import pytest
from tests.extraction import test_quarantine as fixtures
from tests.extraction.test_quarantine_repair3 import repair3_lead_probe
from tests.runner.test_codex_t033 import Streaming, collect

from cre_brain.domain import Fact
from cre_brain.domain.base import TenantScope
from cre_brain.runner.codex import CodexRunner
from cre_brain.runner.state_adapter import RunnerState, require_recovered, token_commitment
from cre_brain.runner.streaming import CancellationReceipt
from cre_brain.runner.tools.state import ToolState
from cre_brain.sandbox.base import SandboxError

setup = fixtures.setup


def metered_extraction(inputs, runtime, total=100):
    lines = fixtures.frames(fixtures.output(inputs.docs["roll"]))
    lines[-1] = (
        json.dumps(
            {"type": "turn.completed", "usage": {"input_tokens": 60, "output_tokens": 40}}
        ).encode()
        + b"\n"
    )
    runtime.override["roll"] = lines
    start = runtime.start

    async def metered_start(*args):
        process = await start(*args)

        async def cancel():
            return CancellationReceipt(confirmed=True, total_tokens=total)

        process.cancel = cancel
        return process

    runtime.start = metered_start


@pytest.mark.asyncio
@pytest.mark.parametrize("component", [60, 40])
@pytest.mark.parametrize("failure", ["before-commit", "after-commit"])
async def test_t035_ac1_extraction_reconciles_durable_charge(
    setup, monkeypatch, component, failure
):
    extractor, registry, inputs, provider, runtime = setup
    metered_extraction(inputs, runtime)
    registry.limits = registry.limits.model_copy(update={"max_tokens": 20050})
    event, transaction = ToolState.event, registry.transaction
    failed = pending_ack = False

    def fail_usage(self, kind, payload):
        nonlocal failed, pending_ack
        if (
            not failed
            and payload.get("accounting") == "extraction_observed_usage"
            and payload.get("host_tokens") == component
        ):
            failed = True
            if failure == "before-commit":
                raise RuntimeError("Synthetic usage append failure")
            pending_ack = True
        return event(self, kind, payload)

    @contextmanager
    def lost_ack():
        nonlocal pending_ack
        with transaction() as state:
            yield state
        if pending_ack:
            pending_ack = False
            raise RuntimeError("Synthetic acknowledgement lost after commit")

    monkeypatch.setattr(ToolState, "event", fail_usage)
    monkeypatch.setattr(registry, "transaction", lost_ack)
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    with registry.transaction() as state:
        history = state.history()
        assert failed
        assert sum(e.payload.get("host_tokens", 0) for e in history) == 100
        assert token_commitment(history) == 100
        assert any(e.payload.get("phase") == "end" for e in history)
        assert not state.all_current(Fact)
    with pytest.raises(SandboxError, match="budget"):
        await extractor.extract(("roll",))
    assert len(provider.created) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["receipt-mismatch", "ledger-overcharge", "persist", "ack"])
async def test_t035_ac1_extraction_failed_reconciliation_retains_reservation(
    setup, monkeypatch, failure
):
    extractor, registry, inputs, provider, runtime = setup
    metered_extraction(inputs, runtime, total=50 if failure == "receipt-mismatch" else 110)
    event, transaction = ToolState.event, registry.transaction
    pending_ack = False

    def fail_reconciliation(self, kind, payload):
        nonlocal pending_ack
        if payload.get("accounting") == "extraction_native_meter":
            if failure == "persist":
                raise RuntimeError("Synthetic reconciliation append failure")
            if failure == "ack":
                pending_ack = True
        result = event(self, kind, payload)
        if failure == "ledger-overcharge" and payload.get("host_tokens") == 60:
            event(self, "usage", dict(payload, host_tokens=100))
        return result

    @contextmanager
    def lost_ack():
        nonlocal pending_ack
        with transaction() as state:
            yield state
        if pending_ack:
            pending_ack = False
            raise RuntimeError("Synthetic reconciliation acknowledgement failure")

    monkeypatch.setattr(ToolState, "event", fail_reconciliation)
    monkeypatch.setattr(registry, "transaction", lost_ack)
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    with registry.transaction() as state:
        history = state.history()
        assert not any(e.payload.get("phase") == "end" for e in history)
        assert not state.all_current(Fact)
        assert any(e.payload.get("phase") == "start" for e in history)
    with pytest.raises(SandboxError, match="recovery"):
        await extractor.extract(("roll",))
    assert len(provider.created) == len(provider.destroyed) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("other_task", [False, True])
async def test_t035_ac1_lost_lead_handle_and_marker_block_extraction(
    setup, monkeypatch, other_task
):
    extractor, registry, inputs, provider, runtime = setup
    lead_runtime = Streaming(provider, registry)
    seg, ws, _ = repair3_lead_probe(registry)
    lead = CodexRunner(
        provider=provider,
        registry=registry,
        runtime=lead_runtime,
        brain_root=Path("brain").absolute(),
        model_provider="openai",
    )

    async def lost_start(*args):
        lead_runtime.process.metered_tokens = 100
        raise RuntimeError("Synthetic native launch lost handle")

    append = RunnerState.append

    def failed_marker(self, event):
        if event.payload.get("category") == "cleanup_unverified":
            raise RuntimeError("Synthetic marker append failure")
        return append(self, event)

    lead_runtime.start = lost_start
    monkeypatch.setattr(RunnerState, "append", failed_marker)
    with pytest.raises((SandboxError, RuntimeError)):
        await collect(lead, seg, ws, registry.context)
    with registry.transaction() as state:
        history = state.history()
        assert [e.kind for e in history] == ["segment_start"]
        with pytest.raises(SandboxError, match="recovery"):
            require_recovered(history)
    if other_task:
        registry.context = registry.context.model_copy(update={"task_id": "task-b"})
    with pytest.raises(SandboxError, match="recovery"):
        await extractor.extract(("roll",))
    assert not provider.created
    registry.context = registry.context.model_copy(
        update={"scope": TenantScope(user_id="other", firm_id="firm"), "task_id": "task-c"}
    )
    inputs.docs["roll"] = runtime.docs["roll"] = fixtures.source(registry.context.scope)
    assert len((await extractor.extract(("roll",))).facts) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("evidence", ["isolated_runtime", "synthetic_plumbing_only"])
@pytest.mark.parametrize(
    "collision", ["task", "box", "segment", "release", "pending", "none", "fixture"]
)
async def test_t035_ac1_lead_lifetime_matching_and_fixture_semantics(setup, collision, evidence):
    extractor, registry, _, provider, _ = setup
    _, _, start = repair3_lead_probe(registry)
    start = start.model_copy(update={"payload": {"max_tokens": 100, "evidence": evidence}})
    if collision == "fixture":
        start = start.model_copy(update={"payload": {"max_tokens": 100}})
    RunnerState(registry).append(start)
    if collision not in {"fixture", "pending"}:
        end = start.model_copy(
            update={
                "event_id": "ended-lead",
                "kind": "segment_end",
                "origin": ("lead", 0, 1),
                "payload": {"usage_complete": True},
            }
        )
        updates = {
            "task": {"task_id": "other-task"},
            "box": {"origin": ("other-box", 0, 1)},
            "segment": {"origin": ("lead", 1, 1)},
            "release": {"release_id": "other-release"},
            "none": {},
        }
        RunnerState(registry).append(end.model_copy(update=updates[collision]))
    if collision in {"none", "fixture"}:
        assert len((await extractor.extract(("roll",))).facts) == 3
    else:
        with registry.transaction() as state:
            assert token_commitment(state.history(task_only=False)) >= 100
        with pytest.raises(SandboxError, match="recovery"):
            await extractor.extract(("roll",))
        assert not provider.created
