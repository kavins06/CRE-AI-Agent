"""Bounded detector over committed normalized events, with host-attested progress."""

import hashlib
from datetime import UTC, datetime
from typing import Self

from pydantic import Field, TypeAdapter, model_validator

from cre_brain.control.jobs import Digest, JobIdentity
from cre_brain.domain import AgentEvent
from cre_brain.runner.orchestration.signals import HostSignal, Reason
from cre_brain.runner.tools.contracts import ID, Boundary
from cre_brain.runner.tools.json_io import canonical, parse


class StuckLimits(Boundary):
    repeat_limit: int = Field(default=3, strict=True, ge=1, le=10000)
    idle_limit: int = Field(default=20, strict=True, ge=1, le=10000)
    window_s: int = Field(default=120, strict=True, ge=1, le=86400)
    max_pending: int = Field(default=32, strict=True, ge=1, le=64)


class VerifiedProgress(Boundary):
    """Trusted host proof of committed progress, never an agent progress claim."""

    identity: JobIdentity
    event_id: ID
    seq: int = Field(strict=True, ge=1, le=9223372036854775807)
    proof_id: ID


class StuckState(Boundary):
    identity: JobIdentity
    limits: StuckLimits
    last_progress_at: datetime  # Host watchdog baseline, reset by progress or a nudge.
    clock_at: datetime
    last_seq: int = Field(default=0, strict=True, ge=0, le=9223372036854775807)
    last_event: Digest | None = None
    last_pair: Digest | None = None
    last_error: Digest | None = None
    pair_count: int = Field(default=0, strict=True, ge=0, le=10000)
    error_count: int = Field(default=0, strict=True, ge=0, le=10000)
    idle_count: int = Field(default=0, strict=True, ge=0, le=10000)
    pending: dict[Digest, Digest] = Field(default_factory=dict, max_length=64)
    nudged: bool = Field(default=False, strict=True)
    last_signal: HostSignal | None = None
    stopped: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def bounded(self) -> Self:
        if (
            self.last_progress_at.utcoffset() is None
            or self.clock_at.utcoffset() is None
            or self.last_progress_at > self.clock_at
            or len(self.pending) > self.limits.max_pending
            or self.pair_count > self.limits.repeat_limit
            or self.error_count > self.limits.repeat_limit
            or self.idle_count > self.limits.idle_limit
            or (self.last_seq == 0) != (self.last_event is None)
        ):
            raise ValueError("Detector checkpoint is inconsistent or exceeds configured bounds")
        return self


def _digest(value: object) -> str:
    # Existing JSON boundary supplies byte, depth, key and nonfinite bounds.
    try:
        encoded = canonical(value)
        parse(encoded)
    except (ValueError, TypeError, RecursionError):
        raise ValueError("Detector event exceeds canonical serialization bounds") from None
    return hashlib.sha256(encoded.encode()).hexdigest()


def _host_clock(now: datetime, previous: datetime) -> None:
    if not isinstance(now, datetime) or now.utcoffset() is None or now < previous:
        raise ValueError("Detector host clock must be aware and monotonic")


class StuckDetector:
    def __init__(
        self,
        identity: JobIdentity,
        limits: StuckLimits,
        *,
        state: StuckState | None = None,
        started_at: datetime | None = None,
    ) -> None:
        self.identity = JobIdentity.model_validate(identity.model_dump())
        self.limits = StuckLimits.model_validate(limits.model_dump())
        started_at = started_at or datetime.now(UTC)
        self._state = (
            StuckState(
                identity=self.identity,
                limits=self.limits,
                last_progress_at=started_at,
                clock_at=started_at,
            )
            if state is None
            else (StuckState.model_validate(state.model_dump()))
        )
        if self._state.identity != self.identity or self._state.limits != self.limits:
            raise ValueError("Detector checkpoint identity or configuration conflicts")

    def snapshot(self) -> StuckState:
        return StuckState.model_validate(self._state.model_dump())

    def tick(self, now: datetime) -> HostSignal | None:
        """Trusted host clock; required even when no canonical events arrive."""
        state = self.snapshot()
        _host_clock(now, state.clock_at)
        if state.stopped:
            return None
        data = state.model_dump() | {"clock_at": now}
        signal = None
        if (now - state.last_progress_at).total_seconds() >= self.limits.window_s:
            signal = HostSignal(
                actions=("stop", "escalate") if state.nudged else ("nudge",), reason="no_progress"
            )
            data.update(
                last_signal=signal,
                stopped=state.nudged,
                nudged=True,
                last_progress_at=now,
                idle_count=0,
                pair_count=0,
                error_count=0,
                last_pair=None,
                last_error=None,
                pending={},
            )
        self._state = StuckState.model_validate(data)
        return signal

    def observe(
        self,
        event: AgentEvent,
        *,
        now: datetime,
        progress: VerifiedProgress | None = None,
    ) -> HostSignal | None:
        """now is an explicit trusted host observation time, never event/model time."""
        state = self.snapshot()
        _host_clock(now, state.clock_at)
        event = AgentEvent.model_validate(event.model_dump())
        if (
            event.task_id != self.identity.task_id
            or event.release_id != self.identity.release_id
            or event.runner != self.identity.runtime
            or event.seq is None
            or type(event.seq) is not int
            or not 0 < event.seq <= 9223372036854775807
            or event.origin is None
            or event.origin[:2] != (self.identity.box_id, self.identity.segment_no)
            or event.ts.utcoffset() is None
        ):
            raise ValueError("Detector requires committed events in the trusted host binding")
        digest = _digest(event.model_dump(mode="json"))
        if progress is not None:
            progress = VerifiedProgress.model_validate(progress.model_dump())
            if (
                progress.identity != self.identity
                or progress.event_id != event.event_id
                or progress.seq != event.seq
            ):
                raise ValueError("Verified progress does not bind this canonical event")
        if event.seq <= state.last_seq:
            if event.seq == state.last_seq and digest == state.last_event:
                self._state = StuckState.model_validate(state.model_dump() | {"clock_at": now})
                return None
            raise ValueError("Detector event replay conflicts with its bounded checkpoint")
        if state.stopped:
            return None
        data = state.model_dump() | {"last_seq": event.seq, "last_event": digest, "clock_at": now}
        signal: HostSignal | None = None
        if progress is not None:
            data.update(
                last_progress_at=now,
                pair_count=0,
                error_count=0,
                idle_count=0,
                last_pair=None,
                last_error=None,
                pending={},
            )
        else:
            reason: Reason | None = None
            pending = dict(state.pending)
            if event.kind == "tool_call":
                call_id = TypeAdapter(ID).validate_python(event.payload.get("call_id"))
                key = _digest({"call_id": call_id})
                call = _digest(
                    {"tool": event.payload.get("tool"), "arguments": event.payload.get("arguments")}
                )
                if key in pending:
                    raise ValueError("Detector tool call identity is already pending")
                if len(pending) >= self.limits.max_pending:
                    reason = "history_bound"
                else:
                    pending[key] = call
            elif event.kind == "tool_result" and event.payload.get("call_id") is not None:
                call_id = TypeAdapter(ID).validate_python(event.payload["call_id"])
                key = _digest({"call_id": call_id})
                paired_call = pending.pop(key) if key in pending else None
                if paired_call is not None:
                    pair = _digest(
                        {
                            "call": paired_call,
                            "result": {k: v for k, v in event.payload.items() if k != "call_id"},
                        }
                    )
                    count = state.pair_count + 1 if pair == state.last_pair else 1
                    data.update(last_pair=pair, pair_count=count)
                    if count >= self.limits.repeat_limit:
                        reason = "repeated_call"
            if event.kind == "error" or (
                event.kind == "tool_result" and event.payload.get("error") is not None
            ):
                error = _digest(
                    event.payload
                    if event.kind == "error"
                    else {
                        "error": event.payload["error"],
                    }
                )
                count = state.error_count + 1 if error == state.last_error else 1
                data.update(last_error=error, error_count=count)
                if count >= self.limits.repeat_limit:
                    reason = "repeated_error"
            if event.kind in {"message", "tool_result", "error", "usage", "gate_result"}:
                data["idle_count"] = state.idle_count + 1
                if data["idle_count"] >= self.limits.idle_limit and reason is None:
                    reason = "no_progress"
            data["pending"] = pending
            if reason is not None:
                stop = state.nudged or reason == "history_bound"
                signal = HostSignal(
                    actions=("stop", "escalate") if stop else ("nudge",), reason=reason
                )
                data.update(
                    last_signal=signal,
                    last_progress_at=now,
                    stopped=stop,
                    nudged=True,
                    pair_count=0,
                    error_count=0,
                    idle_count=0,
                    last_pair=None,
                    last_error=None,
                    pending={},
                )
        self._state = StuckState.model_validate(data)
        return signal
