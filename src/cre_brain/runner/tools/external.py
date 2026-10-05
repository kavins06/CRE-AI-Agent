"""Durable confirm-before-act and gate-bound outbox delivery handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cre_brain.domain import Deliverable, DeliverableKind
from cre_brain.domain.base import TenantScope
from cre_brain.runner.policy import Refusal
from cre_brain.runner.tools import files
from cre_brain.runner.tools.contracts import DraftExternal, SendExternal
from cre_brain.runner.tools.finalization import trusted_release
from cre_brain.runner.tools.json_io import canonical, parse
from cre_brain.runner.tools.registry import ToolRegistry, ok, refused
from cre_brain.runner.tools.state import ToolState


def prepare_send(registry: ToolRegistry, state: ToolState, request: SendExternal) -> dict[str, Any]:
    draft = state.binding(request.draft_id, "draft")
    if (
        not draft
        or draft["deal"] != registry.context.deal_id
        or draft["task"] != registry.context.task_id
    ):
        raise Refusal(
            "untrusted_artifact", "Use a local draft from this authenticated deal and task."
        )
    raw = files.read(registry.workspace, Path(draft["path"]))
    if files.digest(raw) != draft["digest"]:
        raise Refusal("untrusted_artifact", "Draft changed; create a new immutable outbox draft.")
    toggles = registry.host_toggles(state)
    toggle = getattr(toggles, draft["kind"])
    if toggle == "off":
        raise Refusal("policy_off", "External sending is off; draft remains in the local outbox.")
    cid = "confirmation-" + files.digest(canonical([request.draft_id, draft["digest"]]).encode())
    if toggle == "ask" and not registry.confirmed(state, cid):
        if not any(
            e.kind == "confirmation_request" and e.payload.get("cid") == cid
            for e in state.history()
        ):
            state.event(
                "confirmation_request",
                {"cid": cid, "draft_id": request.draft_id, "digest": draft["digest"]},
            )
        return {"status": "pending_confirmation", "cid": cid}
    connector = registry.connectors.get(draft["kind"])
    if connector is None:
        raise Refusal(
            "missing_connector",
            "Host must configure an allowlisted tenant connector before sending.",
        )
    if (
        TenantScope.model_validate(connector.scope.model_dump(warnings=False))
        != registry.context.scope
        or draft["to"] not in connector.allowed_recipients
    ):
        raise Refusal("unauthorized_scope", "Connector or recipient is outside the host allowlist.")
    key = files.digest(
        canonical(
            [
                registry.context.scope.model_dump(warnings=False),
                registry.context.task_id,
                request.draft_id,
                draft["digest"],
            ]
        ).encode()
    )
    registry.released_draft(state, draft, raw)
    intent = next((e.payload for e in state.history() if e.payload.get("send_key") == key), None)
    if intent:
        if any(
            e.payload.get("send_key") == key and e.payload.get("delivery") == "sent"
            for e in state.history()
        ):
            return ok({"draft_id": request.draft_id, "status": "sent"})
        raise Refusal(
            "delivery_unknown",
            "Delivery already reserved; host must reconcile the connector receipt.",
        )
    # Durable intent commits BEFORE any connector call, so a crash cannot silently resend.
    registry.deadline(state)
    state.event("tool_call", {"send_key": key, "draft_id": request.draft_id})
    return {"status": "pending_delivery", "send_key": key, "draft_id": request.draft_id}


def deliver(registry: ToolRegistry, intent: dict[str, Any]) -> dict[str, Any]:
    try:
        with registry.transaction() as state:
            draft = state.binding(intent["draft_id"], "draft")
            if (
                draft is None
                or draft["deal"] != registry.context.deal_id
                or draft["task"] != registry.context.task_id
                or not any(
                    e.kind == "tool_call"
                    and e.source == "tool"
                    and e.runner == "tools"
                    and e.release_id == registry.context.release_id
                    and e.payload.get("send_key") == intent["send_key"]
                    and e.payload.get("draft_id") == intent["draft_id"]
                    for e in state.history()
                )
            ):
                raise Refusal("untrusted_artifact", "Delivery requires this task's durable intent.")
            if any(
                e.payload.get("send_key") == intent["send_key"]
                and e.payload.get("delivery") == "sent"
                for e in state.history()
            ):
                return ok({"draft_id": intent["draft_id"], "status": "sent"})
            raw = files.read(registry.workspace, Path(draft["path"]))
            if files.digest(raw) != draft["digest"]:
                raise ValueError("Draft bytes changed")
            request = registry.released_draft(state, draft, raw)
            # Re-read durable tenant policy immediately before delivery. Keep the
            # tenant lock through the call so a concurrent OFF cannot commit in
            # the authorization/call gap. The intent is already durable separately.
            toggle = getattr(registry.host_toggles(state), request.kind)
            cid = "confirmation-" + files.digest(
                canonical([intent["draft_id"], draft["digest"]]).encode()
            )
            if toggle == "off" or (toggle == "ask" and not registry.confirmed(state, cid)):
                raise Refusal("policy_off", "Current host policy does not authorize delivery.")
            connector = registry.connectors.get(request.kind)
            if connector is None:
                raise Refusal("missing_connector", "Host connector is no longer configured.")
            if (
                TenantScope.model_validate(connector.scope.model_dump(warnings=False))
                != registry.context.scope
                or request.to not in connector.allowed_recipients
            ):
                raise Refusal("unauthorized_scope", "Current connector authorization revoked.")
            # Connector idempotency is part of the configured host seam.
            connector.send(
                recipient_id=request.to, body=request.body, idempotency_key=intent["send_key"]
            )
            state.event("tool_result", {"send_key": intent["send_key"], "delivery": "sent"})
        return ok({"draft_id": intent["draft_id"], "status": "sent"})
    except Refusal as error:
        return refused(error.category, error.message)
    except Exception:
        return refused(
            "delivery_unknown",
            "Connector outcome unknown; host must reconcile the durable send intent.",
        )


def released_draft(
    registry: ToolRegistry, state: ToolState, draft: dict[str, Any], raw: bytes
) -> DraftExternal:
    request = DraftExternal.model_validate(parse(raw.decode()))
    if request.deliverable_id is None:
        raise Refusal("untrusted_artifact", "Sending requires a gate-finalized canonical artifact.")
    anchor, snapshot = registry.artifact_snapshot(state, request.deliverable_id, final_replay=True)
    current = state.current(Deliverable, request.deliverable_id)
    expected_kind = (
        DeliverableKind.LOI if request.kind == "send_loi" else DeliverableKind.BROKER_QUESTIONS
    )
    if current is None or current.status != "final" or current.kind != expected_kind:
        raise Refusal("untrusted_artifact", "Send only a finalized artifact of the matching kind.")
    registry.require_gates()
    trusted_release(registry, state, anchor, snapshot, current)
    if snapshot.data.decode() != request.body:
        raise Refusal("untrusted_artifact", "Draft must match the finalized artifact exactly.")
    registry.deadline(state)
    return request
