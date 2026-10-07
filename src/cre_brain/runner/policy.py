"""Host-controlled toggles, durable caps, and required gate policy (SPEC 10.3).

Only the host constructs these objects. Every entry revalidates model dumps so
model_construct/model_copy cannot bypass boundary validation. Counters and policy
snapshots live in scoped append-only events, and are inspected under a SQL lock.
"""

from datetime import UTC, datetime

from pydantic import Field, model_validator

from cre_brain.domain import AgentEvent, DeliverableKind
from cre_brain.runner.tools.contracts import AuthenticatedContext, Boundary
from cre_brain.runner.tools.state import ToolState, fingerprint


class Refusal(ValueError):
    def __init__(self, category: str, message: str) -> None:
        self.category = category
        self.message = message
        super().__init__(message)


class HostContext(AuthenticatedContext):
    @model_validator(mode="after")
    def aware(self) -> "HostContext":
        if self.started_at.utcoffset() is None or self.started_at > datetime.now(UTC):
            raise ValueError("Host session start must be an aware timestamp in the past")
        return self


class Limits(Boundary):
    max_tool_calls: int = Field(default=1000, strict=True, ge=1, le=100000)
    max_session_calls: int = Field(default=500, strict=True, ge=1, le=100000)
    max_sessions: int = Field(default=2, strict=True, ge=1, le=1000)
    max_wallclock_s: int = Field(default=3600, strict=True, ge=1, le=86400)
    max_session_s: int = Field(default=1200, strict=True, ge=1, le=86400)
    max_tokens: int = Field(default=1000000, strict=True, ge=1)


def remaining_seconds(
    context: HostContext, limits: Limits, history: list[AgentEvent], now: datetime
) -> float:
    """One task deadline for lead, tools, extraction and publication/resume."""
    first = min(
        [
            context.started_at,
            *[
                e.ts
                for e in history
                if e.kind == "segment_start"
                or (
                    e.payload.get("binding") == "extraction_attempt"
                    and e.payload.get("phase") == "start"
                )
            ],
        ]
    )
    return min(
        limits.max_session_s - (now - context.started_at).total_seconds(),
        limits.max_wallclock_s - (now - first).total_seconds(),
    )


def charge(state: ToolState, context: HostContext, limits: Limits) -> None:
    history = state.history()
    sessions = [e for e in history if e.kind == "segment_start" and e.payload.get("tools_session")]
    session = next((e for e in sessions if e.payload["tools_session"] == context.session_id), None)
    snapshot = {"context": fingerprint(context), "limits": fingerprint(limits)}
    if session is not None and session.payload.get("snapshot") != snapshot:
        raise Refusal("policy_conflict", "Host session policy changed; resume through the host.")
    now = datetime.now(UTC)
    usage = [e for e in history if e.kind == "usage" and e.payload.get("tools_call")]
    tokens = 0
    for event in history:
        value = event.payload.get("host_tokens", 0)
        if type(value) is not int or value < 0:
            raise Refusal(
                "policy_conflict", "Invalid host usage ledger; ask the host to reconcile state."
            )
        tokens += value
    if (
        len(usage) >= limits.max_tool_calls
        or tokens >= limits.max_tokens
        or sum(e.payload.get("session") == context.session_id for e in usage)
        >= limits.max_session_calls
        or remaining_seconds(context, limits, history, now) <= 0
        or (session is None and len(sessions) >= limits.max_sessions)
    ):
        raise Refusal("budget_exceeded", "Host budget exhausted; request a host-authorized resume.")
    if session is None:
        state.event("segment_start", {"tools_session": context.session_id, "snapshot": snapshot})
    state.event("usage", {"tools_call": True, "session": context.session_id})


CATALOG: dict[DeliverableKind, tuple[str, ...]] = {
    kind: ("number_provenance",) for kind in DeliverableKind
}
CATALOG.update(
    {
        DeliverableKind.SCREEN: ("coverage", "buy_box", "number_provenance"),
        DeliverableKind.UW_MODEL: (
            "checksums",
            "parity",
            "excel_errors",
            "assumption_ranges",
            "irr_sanity",
            "fragility",
            "number_provenance",
        ),
        DeliverableKind.IC_MEMO: (
            "number_provenance",
            "numbers_match_model",
            "required_sections",
            "entailment",
        ),
        DeliverableKind.LOI: ("policy_bands", "number_provenance", "entailment"),
        DeliverableKind.DD_TRACKER: ("coverage", "number_provenance"),
    }
)
ADVISORY = frozenset({"entailment", "verifier"})


def required_gates(kind: DeliverableKind, extraction: bool) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys((*(("coverage", "checksums") if extraction else ()), *CATALOG[kind]))
    )
