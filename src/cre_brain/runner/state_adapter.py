"""Runner adapter to the existing tenant event ledger and T032 policy/state seams."""

from datetime import UTC, datetime

from cre_brain.domain import AgentEvent
from cre_brain.runner.policy import HostContext, Limits
from cre_brain.runner.segment import SegmentSpec, Workspace
from cre_brain.runner.tools.registry import ToolRegistry
from cre_brain.sandbox.base import SandboxError
from cre_brain.state.events import EventStore, _append_locked


class RunnerState:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry
        self.events = EventStore(registry.engine)

    def validate(self, seg: SegmentSpec, ws: Workspace, policy: HostContext) -> None:
        context = HostContext.model_validate(self.registry.context.model_dump())
        Limits.model_validate(self.registry.limits.model_dump())
        if (
            policy != context
            or ws.scope != context.scope
            or ws.box.user_id != context.scope.user_id
            or (seg.task_id, seg.deal_id, seg.release_id)
            != (context.task_id, context.deal_id, context.release_id)
            or context.role != "lead"
        ):
            raise SandboxError("Runner scope must match the authenticated tool registry")

    def append(self, event: AgentEvent) -> AgentEvent:
        return self.events.append(event, scope=self.registry.context.scope)

    def reserve(self, seg: SegmentSpec, ws: Workspace, start: AgentEvent) -> AgentEvent:
        """Lock and reserve once; never regenerate a conflicting origin after a crash.

        Recovery/control-plane must authorize a NEW segment number. Session and
        usage bindings are append-only events in canonical state, not a side file.
        """
        with self.registry.transaction() as state:
            history = state.history()
            if any(
                e.kind == "segment_end"
                and e.runner == "codex"
                and e.payload.get("usage_complete") is not True
                for e in history
            ):
                raise SandboxError("Incomplete usage requires trusted ledger reconciliation")
            starts = [e for e in history if e.runner == "codex" and e.kind == "segment_start"]
            ends = {
                e.origin[:2]
                for e in history
                if e.runner == "codex" and e.kind == "segment_end" and e.origin is not None
            }
            if any(e.origin is not None and e.origin[:2] not in ends for e in starts):
                raise SandboxError("Active segment requires trusted recovery before resume")
            if any(e.origin is not None and e.origin[1] >= seg.segment_no for e in starts):
                raise SandboxError(
                    "Segment number must increase; immutable events cannot be replaced"
                )
            if seg.resume_session_id is not None:
                binding = next(
                    (
                        e
                        for e in reversed(history)
                        if e.runner == "codex"
                        and e.kind == "resume"
                        and e.payload.get("session_id") == seg.resume_session_id
                    ),
                    None,
                )
                parent = next(
                    (
                        e
                        for e in starts
                        if binding is not None
                        and e.origin is not None
                        and binding.origin is not None
                        and e.origin[:2] == binding.origin[:2]
                    ),
                    None,
                )
                if (
                    binding is None
                    or binding.origin is None
                    or parent is None
                    or binding.origin[0] != ws.box.box_id
                    or binding.release_id != seg.release_id
                    or parent.payload.get("deal_id") != seg.deal_id
                ):
                    raise SandboxError(
                        "Resume session is not bound to this tenant/task/deal/box/release"
                    )
            tokens = 0
            for event in history:
                value = event.payload.get("host_tokens", 0)
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    raise SandboxError("Invalid canonical usage ledger")
                tokens += value
            now = datetime.now(UTC)
            limits = self.registry.limits
            first = min([self.registry.context.started_at, *[e.ts for e in starts]])
            tool_sessions = {
                e.payload["tools_session"]
                for e in history
                if e.kind == "segment_start" and e.payload.get("tools_session")
            }
            if (
                len(starts) >= limits.max_sessions
                or tokens >= limits.max_tokens
                or seg.max_tokens > limits.max_tokens - tokens
                or len(tool_sessions) > limits.max_sessions
                or (now - first).total_seconds() >= limits.max_wallclock_s
                or (now - self.registry.context.started_at).total_seconds() >= limits.max_session_s
            ):
                raise SandboxError("Canonical policy budget exhausted")
            return _append_locked(state.connection, start, state.scope)

    def stop_reason(self, after_seq: int) -> str | None:
        with self.registry.transaction() as state:
            for event in reversed(state.history()):
                if (
                    event.seq or 0
                ) <= after_seq or event.release_id != self.registry.context.release_id:
                    continue
                if event.runner == "tools":
                    if event.kind == "confirmation_request":
                        return "confirmation"
                    if event.kind == "question":
                        return "question"
                    if event.kind == "deliverable" and event.payload.get("status") == "final":
                        return "deliverable"
                if event.source in {"system", "user"} and event.kind in {
                    "interrupt",
                    "pause",
                    "stuck",
                }:
                    return event.kind
        return None

    def remaining_seconds(self) -> float:
        with self.registry.transaction() as state:
            first = min(
                [
                    self.registry.context.started_at,
                    *[e.ts for e in state.history() if e.kind == "segment_start"],
                ]
            )
        now = datetime.now(UTC)
        limits = self.registry.limits
        return min(
            limits.max_session_s - (now - self.registry.context.started_at).total_seconds(),
            limits.max_wallclock_s - (now - first).total_seconds(),
        )
