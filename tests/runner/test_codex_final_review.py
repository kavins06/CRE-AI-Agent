"""Offline lead regressions: observed usage is not a durable charge."""

import time

import pytest
from tests.runner import test_codex_t033 as fixtures

from cre_brain.runner.state_adapter import RunnerState, token_commitment
from cre_brain.sandbox.base import SandboxError

setup = fixtures.setup


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["before-commit", "after-commit"])
async def test_t035_ac1_lead_usage_journal_failure_reconciles(setup, monkeypatch, failure):
    registry, _, _, ws, seg = setup
    runner, runtime = fixtures.build(setup)
    runner.model_provider = "openai"
    registry.limits = registry.limits.model_copy(update={"max_tokens": 105})
    append = RunnerState.append
    failed = False

    def fail_usage(self, event):
        nonlocal failed
        if event.kind == "usage" and not failed:
            failed = True
            if failure == "after-commit":
                append(self, event)
            raise RuntimeError("Synthetic lead usage journal failure")
        return append(self, event)

    monkeypatch.setattr(RunnerState, "append", fail_usage)
    with pytest.raises(SandboxError):
        await fixtures.collect(runner, seg, ws, registry.context)
    with registry.transaction() as state:
        history = state.history()
        assert failed and runtime.process.cancelled
        assert sum(e.payload.get("host_tokens", 0) for e in history) == 11
        assert token_commitment(history) == 11
        assert history[-1].kind == "segment_end"
        assert history[-1].payload["usage_complete"] is True
    with pytest.raises(SandboxError, match="budget"):
        await fixtures.collect(
            runner, seg.model_copy(update={"segment_no": 1}), ws, registry.context
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["persist", "ack", "ledger-overcharge"])
async def test_t035_ac1_lead_reconciliation_failure_keeps_commitment(setup, monkeypatch, failure):
    from contextlib import contextmanager

    from cre_brain.runner.streaming import CancellationReceipt

    registry, _, _, ws, seg = setup
    runner, runtime = fixtures.build(setup)
    runner.model_provider = "openai"
    append, transaction = RunnerState.append, registry.transaction
    pending_ack = False

    async def cancel():
        return CancellationReceipt(confirmed=True, total_tokens=12)

    runtime.process.cancel = cancel

    def overcharge(self, event):
        result = append(self, event)
        if (
            failure == "ledger-overcharge"
            and event.kind == "usage"
            and event.payload.get("accounting") != "trusted_cancellation_meter"
        ):
            append(
                self,
                event.model_copy(
                    update={
                        "event_id": "extra-charge",
                        "origin": (ws.box.box_id, seg.segment_no, 100),
                        "payload": dict(event.payload, host_tokens=100),
                    }
                ),
            )
        return result

    @contextmanager
    def failing_transaction():
        nonlocal pending_ack
        with transaction() as state:
            original_execute = state.connection.execute

            def execute(statement, *args, **kwargs):
                nonlocal pending_ack
                if getattr(statement, "is_insert", False):
                    params = statement.compile().params
                    payload = params.get("payload", {})
                    if payload.get("payload", {}).get("accounting") == "trusted_cancellation_meter":
                        if failure == "persist":
                            raise RuntimeError("Synthetic lead reconciliation failure")
                        if failure == "ack":
                            pending_ack = True
                return original_execute(statement, *args, **kwargs)

            monkeypatch.setattr(state.connection, "execute", execute)
            yield state
        if pending_ack:
            pending_ack = False
            raise RuntimeError("Synthetic lead reconciliation acknowledgement failure")

    # Also inject failures into the old append path so RED checks the existing seam.
    def failing_append(self, event):
        if event.payload.get("accounting") == "trusted_cancellation_meter":
            if failure == "persist":
                raise RuntimeError("Synthetic lead reconciliation failure")
            if failure == "ack":
                append(self, event)
                raise RuntimeError("Synthetic lead reconciliation acknowledgement failure")
        return overcharge(self, event)

    monkeypatch.setattr(RunnerState, "append", failing_append)
    monkeypatch.setattr(registry, "transaction", failing_transaction)
    with pytest.raises((SandboxError, RuntimeError)):
        await fixtures.collect(runner, seg, ws, registry.context)
    with registry.transaction() as state:
        history = state.history()
        assert not any(
            e.kind == "segment_end" and e.payload.get("usage_complete") is True for e in history
        )
        assert token_commitment(history) >= seg.max_tokens
    with pytest.raises(SandboxError, match="recovery|usage"):
        await fixtures.collect(
            runner, seg.model_copy(update={"segment_no": 1}), ws, registry.context
        )


@pytest.mark.asyncio
async def test_repair_deadline_before_native_start_has_complete_zero_usage(setup, monkeypatch):
    registry, _, _, ws, seg = setup
    runner, runtime = fixtures.build(setup)
    reserve = RunnerState.reserve

    def slow_reserve(self, *args, **kwargs):
        result = reserve(self, *args, **kwargs)
        time.sleep(0.03)
        return result

    with monkeypatch.context() as patch:
        patch.setattr(RunnerState, "reserve", slow_reserve)
        events = await fixtures.collect(
            runner, seg.model_copy(update={"timeout_s": 0.005}), ws, registry.context
        )
    assert runtime.request is None
    assert not runtime.process.cancelled
    assert events[-1].payload["reason"] == "budget"
    assert events[-1].payload["tokens"] == 0
    assert events[-1].payload["usage_complete"] is True
    resumed = await fixtures.collect(
        runner, seg.model_copy(update={"segment_no": 1}), ws, registry.context
    )
    assert resumed[-1].payload["reason"] == "completed"
