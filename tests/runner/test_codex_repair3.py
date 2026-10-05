"""Offline regressions for the shared lead/extractor runtime lifetime seam."""

import asyncio
from pathlib import Path

import pytest
from tests.runner import test_codex_t033 as fixtures

from cre_brain.runner.codex import CodexRunner
from cre_brain.runner.streaming import CancellationReceipt
from cre_brain.sandbox.base import SandboxError
from cre_brain.state.events import EventStore

setup = fixtures.setup
build = fixtures.build
collect = fixtures.collect
Streaming = fixtures.Streaming


def test_t035_ac1_lead_isolated_runtime_rejects_non_openai_provider(setup):
    registry, _, provider, ws, seg = setup
    # A valid synthetic owner configuration, so the model-placeholder guard
    # cannot hide the unsupported-provider failure. Production IDs stay intact.
    role = registry.settings.models.roles["lead"]
    registry.settings.models.roles["lead"] = role.model_copy(update={"model": seg.task_id})
    runtime = Streaming(provider, registry)
    runtime.caps = runtime.caps.model_copy(update={"evidence": "isolated_runtime"})
    runner = CodexRunner(
        provider=provider,
        registry=registry,
        runtime=runtime,
        brain_root=Path("brain").absolute(),
        model_provider="unsupported-provider",
    )
    with pytest.raises(SandboxError, match="OpenAI"):
        asyncio.run(runner.ready(ws, seg))
    assert runtime.assets is None and runtime.request is None


@pytest.mark.asyncio
async def test_t035_ac1_lead_cancellation_suppression_is_bounded(setup, monkeypatch):
    registry, _, _, ws, seg = setup
    runner, runtime = build(setup)
    release, entered = asyncio.Event(), asyncio.Event()
    wait, wait_for = asyncio.wait, asyncio.wait_for

    async def short_wait(tasks, *, timeout=None, **kwargs):
        return await wait(tasks, timeout=min(timeout or 0.01, 0.01), **kwargs)

    async def short_wait_for(awaitable, timeout):
        return await wait_for(awaitable, min(timeout, 0.01))

    monkeypatch.setattr(asyncio, "wait", short_wait)
    monkeypatch.setattr(asyncio, "wait_for", short_wait_for)

    async def suppressed_cancel():
        entered.set()
        while not release.is_set():
            try:
                await release.wait()
            except asyncio.CancelledError:
                pass
        return CancellationReceipt(confirmed=True, total_tokens=11)

    runtime.process.cancel = suppressed_cancel
    consumer = asyncio.create_task(collect(runner, seg, ws, registry.context))
    waiter = asyncio.create_task(entered.wait())
    try:
        await wait({waiter}, timeout=1)
        done, _ = await wait({consumer}, timeout=0.15)
        bounded = consumer in done
    finally:
        release.set()
        results = await asyncio.gather(consumer, return_exceptions=True)
        await waiter
        await asyncio.sleep(0)
    assert bounded, "Lead cancellation waited for a cancellation-suppressing adapter"
    assert isinstance(results[0], SandboxError)
    history = EventStore(registry.engine).list(seg.task_id, scope=ws.scope)
    assert not any(e.kind == "segment_end" for e in history)
    with pytest.raises(SandboxError, match="recovery"):
        await collect(runner, seg.model_copy(update={"segment_no": 1}), ws, registry.context)


@pytest.mark.asyncio
async def test_t035_ac1_lead_unknown_start_keeps_durable_reservation(setup):
    from cre_brain.runner.state_adapter import RunnerState

    registry, _, _, ws, seg = setup
    runner, runtime = build(setup)

    async def lost_start(*args):
        runtime.process.metered_tokens = 100
        raise RuntimeError("Synthetic launched process lost its handle")

    runtime.start = lost_start
    with pytest.raises(SandboxError):
        await collect(runner, seg, ws, registry.context)
    history = EventStore(registry.engine).list(seg.task_id, scope=ws.scope)
    assert any(e.kind == "segment_start" for e in history)
    assert not any(e.kind == "segment_end" for e in history)
    registry.context = registry.context.model_copy(update={"task_id": "next-task"})
    with pytest.raises(SandboxError, match="recovery"):
        RunnerState(registry).reserve(
            seg.model_copy(update={"task_id": "next-task"}),
            ws,
            history[0].model_copy(update={"event_id": "next-start", "task_id": "next-task"}),
        )


@pytest.mark.asyncio
async def test_t035_ac1_incomplete_lead_meter_keeps_token_commitment(setup):
    from cre_brain.runner.state_adapter import token_commitment

    registry, _, _, ws, seg = setup
    runner, runtime = build(setup)

    async def incomplete_meter():
        return CancellationReceipt(confirmed=True, total_tokens=None)

    runtime.process.cancel = incomplete_meter
    await collect(runner, seg, ws, registry.context)
    with registry.transaction() as state:
        assert token_commitment(state.history()) == seg.max_tokens
