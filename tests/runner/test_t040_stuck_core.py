"""Canonical synthetic events only; no live runner or product acceptance claims."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine

from cre_brain.config import load
from cre_brain.control.jobs import JobIdentity
from cre_brain.domain import AgentEvent
from cre_brain.domain.base import TenantScope
from cre_brain.runner.orchestration.budget import budget_snapshot
from cre_brain.runner.orchestration.stuck import (
    StuckDetector,
    StuckLimits,
    StuckState,
    VerifiedProgress,
)
from cre_brain.runner.policy import HostContext, Limits
from cre_brain.runner.state_adapter import RunnerState
from cre_brain.runner.tools.registry import ToolRegistry
from cre_brain.sandbox.base import SandboxError
from cre_brain.state.schema import metadata

NOW = datetime(2026, 10, 5, tzinfo=UTC)
IDENTITY = JobIdentity(
    scope=TenantScope(user_id="fixture-u", firm_id="fixture-f"),
    task_id="task",
    deal_id="deal",
    release_id="release",
    box_id="box",
    runtime="codex",
    request_id="request",
    request_sha256="a" * 64,
    segment_no=0,
)


def event(number, kind="message", payload=None, **updates):
    return AgentEvent.model_validate(
        dict(
            event_id=f"event-{number}",
            task_id=IDENTITY.task_id,
            seq=number,
            origin=(IDENTITY.box_id, 0, number),
            ts=NOW,
            source="agent",
            kind=kind,
            cause_id=None,
            release_id=IDENTITY.release_id,
            runner=IDENTITY.runtime,
            payload=payload or {},
        )
        | updates
    )


def pair(detector, n, result="same seller content"):
    detector.observe(
        event(
            n * 2 - 1,
            "tool_call",
            {"tool": "facts_get", "arguments": {"opaque": "seller fixture"}, "call_id": f"c-{n}"},
        ),
        now=NOW,
    )
    return detector.observe(
        event(n * 2, "tool_result", {"tool": "facts_get", "result": result, "call_id": f"c-{n}"}),
        now=NOW,
    )


def test_stuck_identical_pairs_nudge_once_then_terminal_stop_and_durable_restart():
    d = StuckDetector(IDENTITY, StuckLimits(repeat_limit=3, idle_limit=100), started_at=NOW)
    assert pair(d, 1) is None
    assert pair(d, 2) is None
    assert pair(d, 3).actions == ("nudge",)
    snapshot = d.snapshot().model_dump_json()
    assert "seller" not in snapshot and "facts_get" not in snapshot
    d = StuckDetector(IDENTITY, d.limits, state=StuckState.model_validate_json(snapshot))
    assert pair(d, 4) is None
    assert pair(d, 5) is None
    signal = pair(d, 6)
    assert signal.actions == ("stop", "escalate")
    assert signal.reason == "repeated_call"
    assert d.observe(event(13), now=NOW) is None
    assert d.snapshot().stopped
    assert len(d.snapshot().model_dump_json()) < 12000


def test_stuck_changed_pairs_and_verified_progress_reset_detectors_but_not_nudge():
    d = StuckDetector(IDENTITY, StuckLimits(repeat_limit=2, idle_limit=20), started_at=NOW)
    assert pair(d, 1) is None
    assert pair(d, 2, result="changed") is None
    assert pair(d, 3, result="changed").actions == ("nudge",)
    progress_event = event(7, "tool_result", {"result": "changed"})
    progress = VerifiedProgress(
        identity=IDENTITY, event_id=progress_event.event_id, seq=7, proof_id="trusted-commit"
    )
    assert d.observe(progress_event, progress=progress, now=NOW) is None
    assert d.snapshot().idle_count == 0
    assert d.observe(event(8, "error", {"category": "provider_error"}), now=NOW) is None
    assert d.observe(event(9, "error", {"category": "provider_error"}), now=NOW).actions == (
        "stop",
        "escalate",
    )


def test_stuck_repeated_errors_and_no_progress_ignore_raw_and_false_progress():
    d = StuckDetector(IDENTITY, StuckLimits(repeat_limit=2, idle_limit=20), started_at=NOW)
    assert d.observe(event(1, "error", {"category": "fixture"}), now=NOW) is None
    assert d.observe(event(2, "error", {"category": "fixture"}), now=NOW).reason == "repeated_error"
    d = StuckDetector(IDENTITY, StuckLimits(repeat_limit=10, idle_limit=2), started_at=NOW)
    for n in range(1, 50):
        assert d.observe(event(n, "runner_raw", {"progress": True}), now=NOW) is None
    assert d.observe(event(50, payload={"progress": True}), now=NOW) is None
    assert d.observe(event(51, payload={"progress": True}), now=NOW).reason == "no_progress"
    assert d.observe(event(52), now=NOW) is None
    assert d.observe(event(53), now=NOW).actions == ("stop", "escalate")


def test_stuck_replay_does_not_double_count_and_conflicting_scope_fails_closed():
    d = StuckDetector(IDENTITY, StuckLimits(repeat_limit=2, idle_limit=2), started_at=NOW)
    first = event(1)
    d.observe(first, now=NOW)
    assert d.observe(first, now=NOW) is None
    assert d.snapshot().idle_count == 1
    for update in [
        dict(task_id="other"),
        dict(release_id="other"),
        dict(runner="other"),
        dict(origin=("other", 0, 2)),
        dict(origin=("box", 1, 2)),
        dict(seq=None),
        dict(seq=1, payload={"changed": True}),
    ]:
        with pytest.raises(ValueError):
            d.observe(event(2, **update), now=NOW)
    assert d.snapshot().idle_count == 1
    wrong = VerifiedProgress(identity=IDENTITY, event_id="wrong", seq=2, proof_id="host")
    with pytest.raises(ValueError):
        d.observe(event(2), progress=wrong, now=NOW)


def test_stuck_pending_history_and_payload_serialization_are_bounded():
    d = StuckDetector(
        IDENTITY, StuckLimits(repeat_limit=10, idle_limit=100, max_pending=2), started_at=NOW
    )
    for n in [1, 2]:
        d.observe(
            event(n, "tool_call", {"call_id": f"c-{n}", "tool": "read", "arguments": {}}), now=NOW
        )
    signal = d.observe(
        event(3, "tool_call", {"call_id": "c-3", "tool": "read", "arguments": {}}), now=NOW
    )
    assert signal.actions == ("stop", "escalate")
    assert signal.reason == "history_bound"
    d = StuckDetector(IDENTITY, StuckLimits(repeat_limit=3, idle_limit=100), started_at=NOW)
    with pytest.raises(ValueError):
        d.observe(event(1, payload={"text": "x" * 131073}), now=NOW)
    assert d.snapshot().last_seq == 0


@pytest.mark.parametrize("bad", [True, -1, 0, 1.5, "3", 10001])
def test_stuck_strict_configuration_bounds(bad):
    with pytest.raises(ValidationError):
        StuckLimits(repeat_limit=bad)


class EmptyInputs:
    def fact(self, *args):
        return None

    def artifact(self, *args):
        return None

    def template(self, *args):
        return None

    def rule_policy(self, *args):
        return None


@pytest.fixture
def runner_state(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'budget.db'}")
    metadata.create_all(engine)
    context = HostContext(
        scope=IDENTITY.scope,
        task_id=IDENTITY.task_id,
        deal_id=IDENTITY.deal_id,
        role="lead",
        session_id="tools-session",
        release_id=IDENTITY.release_id,
        started_at=NOW,
    )
    registry = ToolRegistry(
        engine=engine,
        context=context,
        workspace=tmp_path,
        inputs=EmptyInputs(),
        settings=load(),
        limits=Limits(max_tokens=100),
    )
    yield RunnerState(registry)
    engine.dispose()


class SyntheticAccounting:
    """Host seam test double, not a replacement production reservation ledger."""

    def __init__(self, committed, recovered=True):
        self.committed = committed
        self.recovered = recovered

    def require_recovered(self, history):
        if not self.recovered:
            raise SandboxError("Synthetic incomplete accounting")

    def token_commitment(self, history):
        return self.committed


def test_budget_missing_adapter_and_unknown_usage_fail_closed(runner_state):
    view = budget_snapshot(runner_state, requested_tokens=1)
    assert view.spent is None and view.reserved is None
    assert view.signal.actions == ("recover",)
    runner_state.append(event(1, "segment_end", {"usage_complete": False}))
    view = budget_snapshot(
        runner_state, requested_tokens=1, accounting=SyntheticAccounting(80, recovered=False)
    )
    assert view.status == "incomplete"
    assert view.commitment is None and view.reserved is None
    assert view.signal.reason == "accounting_incomplete"


def test_budget_uses_total_commitment_including_pending_reservations(runner_state):
    runner_state.append(
        event(
            1,
            "usage",
            {
                "host_tokens": 20,
                "input_tokens": 15,
                "output_tokens": 5,
                "cached_input_tokens": 2,
                "session_id": "session",
                "turn": 1,
            },
        )
    )
    accounting = SyntheticAccounting(80)
    view = budget_snapshot(runner_state, requested_tokens=20, accounting=accounting)
    assert (view.spent, view.reserved, view.commitment) == (20, 60, 80)
    assert view.signal is None
    view = budget_snapshot(runner_state, requested_tokens=21, accounting=accounting)
    assert view.signal.actions == ("stop", "escalate")
    assert view.signal.reason == "budget_cap"
    assert (
        budget_snapshot(
            runner_state, requested_tokens=0, accounting=SyntheticAccounting(100)
        ).signal.reason
        == "budget_cap"
    )


@pytest.mark.parametrize("bad", [True, -1, 1.5, "20", 2000000001])
def test_budget_host_usage_strict_nonnegative_bounds(runner_state, bad):
    runner_state.append(event(1, "usage", {"host_tokens": bad}))
    view = budget_snapshot(runner_state, requested_tokens=1, accounting=SyntheticAccounting(90))
    assert view.status == "incomplete" and view.signal.actions == ("recover",)


@pytest.mark.parametrize("bad", [True, -1, 1.5, "1", 100000001])
def test_budget_requested_usage_strict_bounds(runner_state, bad):
    with pytest.raises(ValidationError):
        budget_snapshot(runner_state, requested_tokens=bad, accounting=SyntheticAccounting(10))


@pytest.mark.parametrize("commitment", [True, -1, "80", 19])
def test_budget_invalid_canonical_commitment_blocks_admission(runner_state, commitment):
    runner_state.append(event(1, "usage", {"host_tokens": 20}))
    view = budget_snapshot(
        runner_state, requested_tokens=1, accounting=SyntheticAccounting(commitment)
    )
    assert view.status == "incomplete"
    assert view.signal.actions == ("recover",)


def test_stuck_wallclock_bounds_silent_or_raw_only_stream_and_progress_reset():
    d = StuckDetector(IDENTITY, StuckLimits(window_s=10), started_at=NOW)
    assert d.tick(NOW + timedelta(seconds=9)) is None
    assert d.tick(NOW + timedelta(seconds=10)).actions == ("nudge",)
    d = StuckDetector(IDENTITY, d.limits, state=d.snapshot())
    e = event(1)
    e = e.model_copy(update={"ts": NOW + timedelta(seconds=15)})
    d.observe(
        e,
        progress=VerifiedProgress(
            identity=IDENTITY, event_id=e.event_id, seq=1, proof_id="host-proof"
        ),
        now=NOW + timedelta(seconds=15),
    )
    assert d.tick(NOW + timedelta(seconds=24)) is None
    assert d.tick(NOW + timedelta(seconds=25)).actions == ("stop", "escalate")
    assert d.tick(NOW + timedelta(seconds=100)) is None


def test_stuck_checkpoint_identity_limits_and_clock_rollback_rejected():
    d = StuckDetector(IDENTITY, StuckLimits(), started_at=NOW)
    with pytest.raises(ValueError):
        d.tick(NOW - timedelta(seconds=1))
    with pytest.raises(ValueError):
        StuckDetector(
            IDENTITY.model_copy(update={"release_id": "other"}), d.limits, state=d.snapshot()
        )
    with pytest.raises(ValueError):
        StuckDetector(IDENTITY, StuckLimits(repeat_limit=2), state=d.snapshot())


def test_stuck_repeated_tool_errors_across_different_calls():
    d = StuckDetector(IDENTITY, StuckLimits(repeat_limit=2, idle_limit=100), started_at=NOW)
    d.observe(
        event(1, "tool_result", {"call_id": "a", "tool": "read", "error": "fixture"}), now=NOW
    )
    signal = d.observe(
        event(2, "tool_result", {"call_id": "b", "tool": "write", "error": "fixture"}), now=NOW
    )
    assert signal.reason == "repeated_error"
    assert d.snapshot().last_signal == signal


def test_stuck_verified_committed_progress_can_arrive_after_a_clock_tick():
    d = StuckDetector(IDENTITY, StuckLimits(window_s=10), started_at=NOW)
    assert d.tick(NOW + timedelta(seconds=6)) is None
    e = event(1).model_copy(update={"ts": NOW + timedelta(seconds=5)})
    assert (
        d.observe(
            e,
            progress=VerifiedProgress(
                identity=IDENTITY, event_id=e.event_id, seq=1, proof_id="trusted-commit"
            ),
            now=NOW + timedelta(seconds=6),
        )
        is None
    )
    assert d.tick(NOW + timedelta(seconds=14)) is None
    assert d.tick(NOW + timedelta(seconds=16)).actions == ("nudge",)


def test_budget_conflicting_usage_components_fail_closed_and_reads_do_not_mutate(runner_state):
    runner_state.append(
        event(
            1,
            "usage",
            {"host_tokens": 20, "input_tokens": 15, "output_tokens": 10, "cached_input_tokens": 0},
        )
    )
    before = runner_state.events.list(IDENTITY.task_id, scope=IDENTITY.scope)
    view = budget_snapshot(runner_state, requested_tokens=1, accounting=SyntheticAccounting(80))
    assert view.status == "incomplete" and view.signal.reason == "accounting_incomplete"
    assert runner_state.events.list(IDENTITY.task_id, scope=IDENTITY.scope) == before


def test_budget_unbounded_canonical_commitment_fails_closed(runner_state):
    view = budget_snapshot(runner_state, requested_tokens=1, accounting=SyntheticAccounting(2**63))
    assert view.status == "incomplete" and view.commitment is None


def test_stuck_event_nudge_roundtrip_gets_full_host_watchdog_interval():
    detector = StuckDetector(IDENTITY, StuckLimits(repeat_limit=2, window_s=10), started_at=NOW)
    first = event(1, "error", {"category": "same-error"}, ts=NOW + timedelta(seconds=8))
    second = event(2, "error", {"category": "same-error"}, ts=NOW + timedelta(seconds=10))
    assert detector.observe(first, now=NOW + timedelta(seconds=8)) is None
    assert detector.observe(second, now=NOW + timedelta(seconds=10)).actions == ("nudge",)
    restored = StuckDetector(
        IDENTITY,
        detector.limits,
        state=StuckState.model_validate_json(detector.snapshot().model_dump_json()),
    )
    assert restored.tick(NOW + timedelta(seconds=10)) is None
    assert restored.tick(NOW + timedelta(seconds=19)) is None
    assert restored.tick(NOW + timedelta(seconds=20)).actions == ("stop", "escalate")
    assert restored.tick(NOW + timedelta(seconds=30)) is None


def test_stuck_event_timestamps_and_replay_cannot_extend_host_nudge_deadline():
    detector = StuckDetector(IDENTITY, StuckLimits(repeat_limit=2, window_s=10), started_at=NOW)
    future = NOW + timedelta(days=100)
    first = event(1, "error", {"category": "same-error"}, ts=future)
    second = event(2, "error", {"category": "same-error"}, ts=future)
    assert detector.observe(first, now=NOW + timedelta(seconds=8)) is None
    assert detector.observe(second, now=NOW + timedelta(seconds=10)).actions == ("nudge",)
    checkpoint = StuckState.model_validate_json(detector.snapshot().model_dump_json())
    assert checkpoint.clock_at == checkpoint.last_progress_at == NOW + timedelta(seconds=10)
    restored = StuckDetector(IDENTITY, detector.limits, state=checkpoint)
    assert restored.observe(second, now=NOW + timedelta(seconds=19)) is None
    assert restored.snapshot().last_progress_at == NOW + timedelta(seconds=10)
    assert restored.tick(NOW + timedelta(seconds=20)).actions == ("stop", "escalate")


def test_stuck_verified_progress_watchdog_uses_host_observation_not_event_timestamp():
    detector = StuckDetector(IDENTITY, StuckLimits(window_s=10), started_at=NOW)
    e = event(1, ts=NOW + timedelta(days=100))
    progress = VerifiedProgress(identity=IDENTITY, event_id=e.event_id, seq=1, proof_id="host")
    assert detector.observe(e, now=NOW + timedelta(seconds=5), progress=progress) is None
    assert detector.snapshot().last_progress_at == NOW + timedelta(seconds=5)
    assert detector.tick(NOW + timedelta(seconds=14)) is None
    assert detector.tick(NOW + timedelta(seconds=15)).actions == ("nudge",)


def test_stuck_host_observation_clock_rollback_or_naive_time_does_not_mutate_checkpoint():
    detector = StuckDetector(IDENTITY, StuckLimits(), started_at=NOW)
    detector.observe(event(1), now=NOW + timedelta(seconds=8))
    checkpoint = detector.snapshot()
    for invalid in [NOW + timedelta(seconds=7), NOW.replace(tzinfo=None)]:
        with pytest.raises(ValueError):
            detector.observe(event(2), now=invalid)
        assert detector.snapshot() == checkpoint
    with pytest.raises(TypeError):
        detector.observe(event(2))
    assert detector.snapshot() == checkpoint
