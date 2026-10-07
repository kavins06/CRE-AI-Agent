"""Second-review recovery, launch, deadline and source-freshness regressions."""

from datetime import UTC, datetime

import pytest
from tests.extraction import test_quarantine as fixtures

from cre_brain.domain import Fact
from cre_brain.domain.base import TenantScope
from cre_brain.runner.streaming import CancellationReceipt
from cre_brain.sandbox.base import Box, SandboxError

setup = fixtures.setup
source = fixtures.source


def repair3_lead_probe(registry):
    from cre_brain.domain import AgentEvent
    from cre_brain.runner.segment import SegmentSpec, Workspace

    context = registry.context
    seg = SegmentSpec(
        task_id=context.task_id,
        deal_id=context.deal_id,
        release_id=context.release_id,
        segment_no=0,
        prompt="Synthetic recovery probe",
        max_turns=1,
        max_tokens=1,
    )
    ws = Workspace(box=Box(user_id=context.scope.user_id, box_id="lead"), scope=context.scope)
    event = AgentEvent(
        event_id="repair3-lead-" + context.task_id,
        task_id=context.task_id,
        seq=None,
        origin=("lead", 0, 0),
        ts=datetime.now(UTC),
        source="system",
        kind="segment_start",
        cause_id=None,
        release_id=context.release_id,
        runner="codex",
        payload={"max_tokens": 1},
    )
    return seg, ws, event


@pytest.mark.asyncio
@pytest.mark.parametrize("barrier", ["marker", "lead-marker", "reservation"])
async def test_t035_ac1_recovery_barrier_covers_other_task_same_tenant(setup, barrier):
    from cre_brain.runner.state_adapter import RunnerState

    extractor, registry, inputs, provider, runtime = setup
    with registry.transaction() as state:
        if barrier in {"marker", "lead-marker"}:
            state.event(
                "error",
                {
                    "category": (
                        "cleanup_unverified"
                        if barrier == "lead-marker"
                        else "extraction_cleanup_unverified"
                    ),
                    "box_id": "roll",
                },
            )
        else:
            state.event(
                "tool_result",
                {
                    "binding": "extraction_attempt",
                    "identity": "lost",
                    "phase": "start",
                    "reserved_tokens": 100,
                },
            )
    registry.context = registry.context.model_copy(update={"task_id": "task-b", "session_id": "b"})
    with pytest.raises(SandboxError, match="recovery"):
        RunnerState(registry).reserve(*repair3_lead_probe(registry))
    with pytest.raises(SandboxError, match="recovery"):
        await extractor.extract(("roll",))
    assert not provider.created
    registry.context = registry.context.model_copy(
        update={
            "scope": TenantScope(user_id="unaffected", firm_id="firm"),
            "task_id": "unaffected-task",
        }
    )
    unaffected = source(registry.context.scope)
    inputs.docs["roll"] = runtime.docs["roll"] = unaffected
    RunnerState(registry).reserve(*repair3_lead_probe(registry))
    result = await extractor.extract(("roll",))
    assert len(result.facts) == 3
    with registry.transaction() as state:
        assert all(e.task_id == "unaffected-task" for e in state.history(task_only=False))


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["start", "create"])
async def test_t035_ac1_unknown_launch_outcome_retains_reservation(setup, operation):
    extractor, registry, inputs, provider, runtime = setup
    launch = runtime.start if operation == "start" else provider.create_extraction
    calls = 0
    native_tokens = 0

    async def lose_handle(*args):
        nonlocal calls, native_tokens
        calls += 1
        handle = await launch(*args)
        if operation == "start":
            native_tokens = 100
            handle.metered_tokens = native_tokens
        raise RuntimeError("Synthetic launch lost its handle")

    if operation == "start":
        runtime.start = lose_handle
    else:
        provider.create_extraction = lose_handle
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    with registry.transaction() as state:
        history = state.history()
        starts = [e for e in history if e.payload.get("phase") == "start"]
        ends = [e for e in history if e.payload.get("phase") == "end"]
        assert len(starts) == 1 and not ends
        assert starts[0].payload["reserved_tokens"] == extractor.limits.max_tokens
        assert not state.all_current(Fact)
    with pytest.raises(SandboxError, match="recovery"):
        await extractor.extract(("roll",))
    assert calls == 1
    assert native_tokens == (100 if operation == "start" else 0)


@pytest.mark.asyncio
async def test_t035_ac1_marker_write_failure_cannot_release_reservation(setup, monkeypatch):
    from cre_brain.runner.state_adapter import RunnerState, token_commitment
    from cre_brain.runner.tools.state import ToolState

    extractor, registry, inputs, provider, runtime = setup
    start, event = runtime.start, ToolState.event
    failed = False

    async def unconfirmed(*args):
        process = await start(*args)

        async def cancel():
            return CancellationReceipt(confirmed=False, total_tokens=None)

        process.cancel = cancel
        return process

    def failed_marker(self, kind, payload):
        nonlocal failed
        if payload.get("category") == "extraction_cleanup_unverified" and not failed:
            failed = True
            raise RuntimeError("Synthetic one-shot marker transaction failure")
        return event(self, kind, payload)

    runtime.start = unconfirmed
    monkeypatch.setattr(ToolState, "event", failed_marker)
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    with registry.transaction() as state:
        history = state.history()
        assert failed
        assert not any(
            e.payload.get("category") == "extraction_cleanup_unverified" for e in history
        )
        assert not any(e.payload.get("phase") == "end" for e in history)
        assert token_commitment(history) == extractor.limits.max_tokens
    registry.context = registry.context.model_copy(update={"task_id": "task-b"})
    with pytest.raises(SandboxError, match="recovery"):
        RunnerState(registry).reserve(*repair3_lead_probe(registry))
    with pytest.raises(SandboxError, match="recovery"):
        await extractor.extract(("roll",))
    assert len(provider.created) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["cache", "tools", "extraction"])
async def test_t035_ac3_all_publication_paths_share_codex_deadline(setup, path):
    from datetime import timedelta

    from cre_brain.runner.policy import Refusal, charge
    from cre_brain.runner.state_adapter import RunnerState

    extractor, registry, inputs, provider, runtime = setup
    if path == "cache":
        await extractor.extract(("roll",))
    seg, ws, event = repair3_lead_probe(registry)
    old = event.model_copy(update={"ts": datetime.now(UTC) - timedelta(seconds=20)})
    RunnerState(registry).append(old)
    registry.limits = registry.limits.model_copy(update={"max_wallclock_s": 10})
    assert RunnerState(registry).remaining_seconds() < 0
    if path == "tools":
        with registry.transaction() as state:
            with pytest.raises(Refusal, match="budget"):
                charge(state, registry.context, registry.limits)
    else:
        with pytest.raises(SandboxError):
            await extractor.extract(("roll",))
        assert len(provider.created) == (1 if path == "cache" else 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["source", "cache", "commit", "gates"])
async def test_t035_ac2_document_staleness_bound_through_publication(setup, monkeypatch, phase):
    from cre_brain.gates.service import GateService

    extractor, registry, inputs, provider, runtime = setup
    if phase == "cache":
        await extractor.extract(("roll",))

    def stale():
        with registry.transaction() as state:
            state.event("stale", {"item_id": "roll"})

    if phase in {"source", "cache"}:
        stale()
    elif phase == "commit":
        destroy = provider.destroy

        async def stale_destroy(box):
            await destroy(box)
            stale()

        provider.destroy = stale_destroy
    else:
        check = GateService.check_bytes

        def stale_check(service, *args):
            from cre_brain.runner.tools.state import ToolState

            result = check(service, *args)
            ToolState(service.state.connection, registry.context).event(
                "stale", {"item_id": "roll"}
            )
            return result

        monkeypatch.setattr(GateService, "check_bytes", stale_check)
    if phase == "source":
        with pytest.raises((SandboxError, ValueError), match="stale"):
            extractor._source("roll")
    else:
        with pytest.raises(SandboxError):
            await extractor.extract(("roll",))
    if phase != "cache":
        with registry.transaction() as state:
            assert not state.all_current(Fact)
    assert len(provider.created) == (0 if phase == "source" else 1)


@pytest.mark.asyncio
async def test_t035_ac2_document_invalidation_reaches_facts_and_dependents(setup):
    extractor, registry, inputs, provider, runtime = setup
    result = await extractor.extract(("roll",))
    with registry.transaction() as state:
        state.edge(result.facts[0].fact_id, "dependent-calculation")
        state.invalidate("roll")
        assert all(not state.fresh(f.fact_id) for f in result.facts)
        assert not state.fresh("dependent-calculation")
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    assert len(provider.created) == 1
