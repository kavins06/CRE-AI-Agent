"""Runner adapter to the existing tenant event ledger and T032 policy/state seams."""

from collections.abc import Callable
from datetime import UTC, datetime

from cre_brain.domain import AgentEvent
from cre_brain.runner.policy import HostContext, Limits, remaining_seconds
from cre_brain.runner.segment import SegmentSpec, Workspace
from cre_brain.runner.tools.registry import ToolRegistry
from cre_brain.sandbox.base import SandboxError
from cre_brain.state.events import EventStore, _append_locked


def charged_tokens(history: list[AgentEvent]) -> int:
    """Durable charges only; provider observations are never commit acknowledgements."""
    total = 0
    for event in history:
        amount = event.payload.get("host_tokens", 0)
        if type(amount) is not int or amount < 0:
            raise SandboxError("Invalid canonical usage ledger")
        total += amount
    return total


def require_recovered(history: list[AgentEvent]) -> None:
    """Tenant execution barrier; callers read the tenant ledger under its tools lock.

    A missing error marker is not proof of cleanup. Native lead starts and
    extraction attempts retain ownership even when a marker transaction failed.
    """
    if any(
        e.payload.get("category") in {"extraction_cleanup_unverified", "cleanup_unverified"}
        for e in history
    ):
        raise SandboxError("Unverified execution cleanup requires trusted recovery")
    if any(
        e.kind == "segment_end"
        and e.runner == "codex"
        and e.payload.get("usage_complete") is not True
        for e in history
    ):
        raise SandboxError("Incomplete usage requires trusted ledger reconciliation/recovery")
    lead_ends = {
        (e.task_id, e.release_id, e.origin[:2])
        for e in history
        if e.runner == "codex"
        and e.kind == "segment_end"
        and e.origin is not None
        and e.payload.get("usage_complete") is True
    }
    if any(
        e.runner == "codex"
        and e.kind == "segment_start"
        # Runner starts carry runtime evidence, including offline adapter tests.
        # Bare budget fixtures have never claimed a native process lifetime.
        and e.payload.get("evidence") in {"isolated_runtime", "synthetic_plumbing_only"}
        and (e.origin is None or (e.task_id, e.release_id, e.origin[:2]) not in lead_ends)
        for e in history
    ):
        raise SandboxError("Active lead execution requires trusted lifecycle recovery")
    ended = {
        (e.task_id, e.payload.get("identity"))
        for e in history
        if e.payload.get("binding") == "extraction_attempt" and e.payload.get("phase") == "end"
    }
    if any(
        e.payload.get("binding") == "extraction_attempt"
        and e.payload.get("phase") == "start"
        and (e.task_id, e.payload.get("identity")) not in ended
        for e in history
    ):
        raise SandboxError("Active extraction budget reservation requires trusted recovery")


def token_commitment(history: list[AgentEvent]) -> int:
    """Spent tokens plus unspent active reservations, under the shared tools lock."""
    used = 0
    extraction_usage: dict[tuple[str, str], int] = {}
    lead_usage: dict[tuple[str, str, tuple[str, int]], int] = {}
    for event in history:
        amount = event.payload.get("host_tokens", 0)
        if type(amount) is not int or amount < 0:
            raise SandboxError("Invalid canonical usage ledger")
        used += amount
        attempt = event.payload.get("extraction_attempt")
        if isinstance(attempt, str):
            extraction_key = (event.task_id, attempt)
            extraction_usage[extraction_key] = extraction_usage.get(extraction_key, 0) + amount
        if event.runner == "codex" and event.origin is not None:
            key = (event.task_id, event.release_id, event.origin[:2])
            lead_usage[key] = lead_usage.get(key, 0) + amount
        if event.payload.get("category") == "extraction_cleanup_unverified":
            raise SandboxError("Unverified extraction cleanup requires trusted recovery")
    ended_extractions = {
        (e.task_id, e.payload.get("identity"))
        for e in history
        if e.payload.get("binding") == "extraction_attempt" and e.payload.get("phase") == "end"
    }
    ended_leads = {
        (e.task_id, e.release_id, e.origin[:2])
        for e in history
        if e.runner == "codex"
        and e.kind == "segment_end"
        and e.origin is not None
        and e.payload.get("usage_complete") is True
    }
    for event in history:
        if (
            event.payload.get("binding") == "extraction_attempt"
            and event.payload.get("phase") == "start"
            and (event.task_id, event.payload.get("identity")) not in ended_extractions
        ):
            amount = event.payload.get("reserved_tokens")
            identity = event.payload.get("identity")
            if type(amount) is not int or amount < 1 or not isinstance(identity, str):
                raise SandboxError("Extraction reservation requires trusted budget recovery")
            used += max(0, amount - extraction_usage.get((event.task_id, identity), 0))
        elif (
            event.runner == "codex"
            and event.kind == "segment_start"
            and event.origin is not None
            and (event.task_id, event.release_id, event.origin[:2]) not in ended_leads
        ):
            amount = event.payload.get("max_tokens")
            if type(amount) is not int or amount < 1:
                raise SandboxError("Lead reservation requires trusted budget recovery")
            used += max(
                0, amount - lead_usage.get((event.task_id, event.release_id, event.origin[:2]), 0)
            )
    return used


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

    def reconcile_usage(
        self,
        start: AgentEvent,
        *,
        total: int,
        observed: int,
        make_charge: Callable[[int], AgentEvent],
    ) -> AgentEvent | None:
        """Reconcile one native segment under the authenticated ledger transaction."""
        if start.origin is None or start.task_id != self.registry.context.task_id:
            raise SandboxError("Invalid native accounting identity")
        origin = start.origin[:2]
        with self.registry.transaction() as state:

            def charges() -> list[AgentEvent]:
                return [
                    e
                    for e in state.history()
                    if e.runner == "codex"
                    and e.release_id == start.release_id
                    and e.origin is not None
                    and e.origin[:2] == origin
                    and e.kind == "usage"
                ]

            charged = charged_tokens(charges())
            if total < max(observed, charged):
                raise SandboxError(
                    "Native receipt conflicts with canonical usage; recovery required"
                )
            if charged == total:
                return None
            # Allocate an origin only for a real charge; recordings require
            # contiguous event origins even when the meter adds no tokens.
            charge = make_charge(total - charged)
            stored = _append_locked(state.connection, charge, state.scope)
            if charged_tokens(charges()) != total:
                raise SandboxError("Native accounting reconciliation requires recovery")
            return stored

    def reserve(self, seg: SegmentSpec, ws: Workspace, start: AgentEvent) -> AgentEvent:
        """Lock and reserve once; never regenerate a conflicting origin after a crash.

        Recovery/control-plane must authorize a NEW segment number. Session and
        usage bindings are append-only events in canonical state, not a side file.
        """
        with self.registry.transaction() as state:
            tenant_history = state.history(task_only=False)
            require_recovered(tenant_history)
            history = state.history()
            starts = [e for e in history if e.runner == "codex" and e.kind == "segment_start"]
            tenant_starts = [
                e for e in tenant_history if e.runner == "codex" and e.kind == "segment_start"
            ]
            ends = {
                (e.task_id, e.origin[:2])
                for e in tenant_history
                if e.runner == "codex" and e.kind == "segment_end" and e.origin is not None
            }
            if any(
                e.origin is not None and (e.task_id, e.origin[:2]) not in ends
                for e in tenant_starts
            ):
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
            tokens = token_commitment(history)
            now = datetime.now(UTC)
            limits = self.registry.limits
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
                or remaining_seconds(self.registry.context, limits, history, now) <= 0
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
            return remaining_seconds(
                self.registry.context, self.registry.limits, state.history(), datetime.now(UTC)
            )
