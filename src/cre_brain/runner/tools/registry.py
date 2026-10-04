"""One CRE implementation for CLI and MCP. Authority is host-injected only."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import Engine

from cre_brain.config.settings import Settings, ToggleSettings
from cre_brain.domain import (
    Assumption,
    CalcResult,
    ClaimType,
    Deliverable,
    Fact,
    Question,
)
from cre_brain.excel.base import ExcelEngine
from cre_brain.gates.snapshot import ArtifactSnapshot
from cre_brain.runner.policy import HostContext, Limits, Refusal, charge
from cre_brain.runner.tools import files, finance
from cre_brain.runner.tools.contracts import (
    Artifact,
    AskUser,
    AssumptionSet,
    DraftExternal,
    ExcelBuild,
    ExcelRecalc,
    ExternalConnector,
    FactAnchor,
    FactGet,
    FactPut,
    Finalize,
    FinanceRun,
    GateProvider,
    InputProvider,
    Reference,
    RulesEval,
    SendExternal,
)
from cre_brain.runner.tools.evidence import number, resolve
from cre_brain.runner.tools.json_io import canonical, parse
from cre_brain.runner.tools.state import ToolState, fingerprint
from cre_brain.state.store import lock_append

CORE_TOOLS: dict[str, type[BaseModel]] = {
    "facts_get": FactGet,
    "facts_put": FactPut,
    "assumption_set": AssumptionSet,
    "finance_run": FinanceRun,
    "excel_build": ExcelBuild,
    "excel_recalc_parity": ExcelRecalc,
    "rules_eval": RulesEval,
    "ask_user": AskUser,
    "finalize_deliverable": Finalize,
    "draft_external": DraftExternal,
    "send_external": SendExternal,
}


def refused(category: str, message: str) -> dict[str, Any]:
    return {"status": "refused", "category": category, "message": message}


def ok(data: Any) -> dict[str, Any]:
    return {"status": "ok", "data": data}


class ToolRegistry:
    def __init__(
        self,
        *,
        engine: Engine,
        context: HostContext,
        workspace: Path,
        inputs: InputProvider,
        settings: Settings,
        limits: Limits | None = None,
        gates: GateProvider | None = None,
        excel_engine: ExcelEngine | None = None,
        connectors: dict[str, ExternalConnector] | None = None,
    ) -> None:
        self.engine = engine
        self.context = HostContext.model_validate(context.model_dump(warnings=False))
        self.workspace = workspace.absolute()
        # The host must provision a private workspace; no inference from raw documents.
        if self.workspace.resolve() != self.workspace or not self.workspace.is_dir():
            raise ValueError(
                "Host workspace must be an existing directory without symlink ancestors"
            )
        self.inputs = inputs
        self.settings = Settings.model_validate(settings.model_dump(warnings=False))
        self.limits = Limits.model_validate(
            (
                limits
                or Limits(
                    max_session_s=settings.budget.segment_max_min * 60,
                    max_wallclock_s=settings.budget.nightly_wallclock_h * 3600,
                    max_sessions=settings.budget.nightly_sessions,
                )
            ).model_dump(warnings=False)
        )
        self.gates = gates
        self.excel_engine = excel_engine
        self.connectors = dict(connectors or {})

    def clone(
        self, *, context: HostContext | None = None, limits: Limits | None = None
    ) -> ToolRegistry:
        return ToolRegistry(
            engine=self.engine,
            context=context or self.context,
            workspace=self.workspace,
            inputs=self.inputs,
            settings=self.settings,
            limits=limits or self.limits,
            gates=self.gates,
            excel_engine=self.excel_engine,
            connectors=self.connectors,
        )

    @contextmanager
    def transaction(self) -> Iterator[ToolState]:
        with self.engine.begin() as connection:
            lock_append(connection, self.context.scope, ("tools",))
            if connection.dialect.name == "postgresql":
                # Coordinate with existing state graph and event writers as well.
                lock_append(connection, self.context.scope, ("graph",))
                lock_append(connection, self.context.scope, ("events", self.context.task_id))
            yield ToolState(connection, self.context)

    def call_json(self, name: str, raw: str, *, request_id: str | None = None) -> dict[str, Any]:
        try:
            arguments = parse(raw)
        except (ValueError, RecursionError):
            return refused(
                "invalid_input", "Use a bounded JSON object with unique keys and finite values."
            )
        return self.call(name, arguments, request_id=request_id)

    def call(
        self, name: str, arguments: dict[str, Any], *, request_id: str | None = None
    ) -> dict[str, Any]:
        try:
            self.context = HostContext.model_validate(self.context.model_dump(warnings=False))
            self.limits = Limits.model_validate(self.limits.model_dump(warnings=False))
            # Round-trip even direct calls: reject non-JSON objects and deep payloads.
            arguments = parse(canonical(arguments))
            if name not in CORE_TOOLS:
                return refused("unknown_tool", "Choose a tool from the canonical registry.")
            body_hash = files.digest(canonical({"name": name, "args": arguments}).encode())
            identity = request_id or "auto-" + body_hash
            from pydantic import TypeAdapter

            from cre_brain.runner.tools.contracts import ID

            identity = TypeAdapter(ID).validate_python(identity)
            # Usage is committed even for invalid or failing calls.
            with self.transaction() as state:
                charge(state, self.context, self.limits)
                if self.context.role not in {"lead", "user"}:
                    return refused(
                        "unauthorized_role",
                        "Only the authenticated lead or user may call CRE tools.",
                    )
                try:
                    request = CORE_TOOLS[name].model_validate(arguments)
                except ValidationError:
                    return refused(
                        "invalid_input", "Provide only the fields in this tool's input schema."
                    )
                previous = next(
                    (
                        e.payload
                        for e in reversed(state.history())
                        if e.kind == "tool_result" and e.payload.get("request_id") == identity
                    ),
                    None,
                )
                if previous:
                    if previous["body_hash"] != body_hash:
                        return refused(
                            "idempotency_conflict",
                            "Reuse a request ID only for the identical call.",
                        )
                    response = previous["response"]
                    if not isinstance(response, dict):
                        raise Refusal(
                            "state_error",
                            "Invalid idempotency ledger; ask the host to reconcile state.",
                        )
                    if name == "finalize_deliverable" and response["status"] == "ok":
                        self.require_gates()
                        current = state.current(Deliverable, arguments["deliverable_id"])
                        if (
                            current is None
                            or current.status != "final"
                            or current.version != response["data"]["version"]
                        ):
                            raise Refusal(
                                "idempotency_conflict",
                                "A new artifact version requires a new release request ID.",
                            )
                        self.artifact(state, arguments["deliverable_id"], final_replay=True)
                    if response["status"] != "pending_confirmation":
                        return dict(response)
                try:
                    with state.connection.begin_nested():
                        response = self.dispatch(state, name, request, identity)
                        canonical(
                            response
                        )  # Bound output before persisting state/releasing artifact.
                except Refusal as error:
                    response = refused(error.category, error.message)
                except ValidationError:
                    response = refused(
                        "invalid_input",
                        "Canonical host input is invalid; refresh its validated source.",
                    )
                except (ValueError, ArithmeticError):
                    response = refused(
                        "invalid_input",
                        "Inputs could not be validated; check source identities, units and ranges.",
                    )
                except OSError:
                    response = refused(
                        "unauthorized_path",
                        "Artifact I/O refused; use host-provisioned exclusive workspace paths.",
                    )
                except Exception:
                    response = refused(
                        "provider_error",
                        "Host provider failed; inspect host diagnostics and retry safely.",
                    )
                if response["status"] in {
                    "ok",
                    "pending_confirmation",
                    "pending_delivery",
                } and name not in {"facts_get", "rules_eval", "finance_run"}:
                    state.event(
                        "tool_result",
                        {"request_id": identity, "body_hash": body_hash, "response": response},
                    )
            if response["status"] == "pending_delivery":
                completed = self.deliver(response)
                with self.transaction() as state:
                    state.event(
                        "tool_result",
                        {"request_id": identity, "body_hash": body_hash, "response": completed},
                    )
                return completed
            return response
        except Refusal as error:
            return refused(error.category, error.message)
        except (ValueError, TypeError, RecursionError):
            return refused(
                "invalid_input", "Use validated host context and bounded canonical JSON arguments."
            )
        except Exception:
            return refused(
                "state_error", "Scoped state unavailable; ask the host to restore service."
            )

    def dispatch(
        self, state: ToolState, name: str, request: BaseModel, identity: str
    ) -> dict[str, Any]:
        if isinstance(request, FactGet):
            if request.reference.kind != "fact":
                raise Refusal("invalid_input", "facts_get requires a fact reference.")
            resolve(state, request.reference, trusted=False)
            fact = state.current(Fact, request.reference.record_id)
            assert fact is not None
            data = fact.model_dump(mode="json", warnings=False)
            # Raw seller quote text is never exposed through a tool response.
            for provenance in data["provenance"]:
                provenance["quote"] = None
            return ok(data)
        if isinstance(request, FactPut):
            anchor = self.inputs.fact(self.context, request.anchor_id)
            if anchor is None:
                raise Refusal(
                    "missing_provider",
                    "Host must register verified, user-authorized or quarantined source evidence.",
                )
            anchor = FactAnchor.model_validate(anchor.model_dump(warnings=False))
            fact = Fact.model_validate(anchor.fact.model_dump(warnings=False))
            if (
                fact.deal_id != self.context.deal_id
                or fact.known_at.utcoffset() is None
                or fact.known_at > datetime.now(UTC)
            ):
                raise Refusal(
                    "incompatible_evidence",
                    "Host source must match this deal and known-at boundary.",
                )
            if anchor.authority == "quarantine" and fact.claim_type != ClaimType.SELLER_ASSERTION:
                raise Refusal(
                    "untrusted_evidence", "Quarantined inputs must remain seller assertions."
                )
            if fact.claim_type == ClaimType.VERIFIED_FACT and (
                anchor.authority == "quarantine"
                or (anchor.authority == "verified_source" and not fact.provenance)
            ):
                raise Refusal(
                    "untrusted_evidence",
                    "Verified facts need host source verification or explicit user authorization.",
                )
            if any(state.records(model, fact.fact_id) for model in (Assumption, CalcResult)):
                raise Refusal(
                    "ambiguous_evidence",
                    "Fact identity collides with another canonical collection.",
                )
            current = state.current(Fact, fact.fact_id)
            if current is not None and current.deal_id != fact.deal_id:
                raise Refusal(
                    "unauthorized_scope", "A canonical fact identity cannot move between deals."
                )
            if current != fact:
                state.append(fact)
                if current:
                    state.invalidate(fact.fact_id)
            state.event(
                "tool_result",
                {
                    "binding": "fact",
                    "identity": fact.fact_id,
                    "deal": self.context.deal_id,
                    "digest": fingerprint(fact),
                    "authority": anchor.authority,
                },
            )
            return ok(
                {
                    "fact_id": fact.fact_id,
                    "version": fact.version,
                    "claim_type": fact.claim_type.value,
                }
            )
        if isinstance(request, AssumptionSet):
            assumption, record_id = self.assumption(state, request)
            return ok(
                {
                    "assumption": assumption.model_dump(mode="json", warnings=False),
                    "record_id": record_id,
                    "version": 1,
                    "unit": request.value.unit,
                }
            )
        if isinstance(request, FinanceRun):
            return ok(finance.run(state, request).model_dump(mode="json", warnings=False))
        if isinstance(request, AskUser):
            for affected in request.affects:
                self.artifact(state, affected)
            value = resolve(state, request.default)
            assumption_request = AssumptionSet(
                key=request.default.key,
                value=request.default,
                low=request.default,
                high=request.default,
                rationale=request.why,
            )
            assumption, assumption_id = self.assumption(state, assumption_request)
            question = Question(
                q_id="question-"
                + files.digest(
                    canonical(
                        [
                            self.context.scope.model_dump(warnings=False),
                            self.context.task_id,
                            self.context.deal_id,
                            identity,
                        ]
                    ).encode()
                ),
                task_id=self.context.task_id,
                deal_id=self.context.deal_id,
                text=request.question,
                why_it_matters=request.why,
                default_used=str(value),
                affects=request.affects,
                status="open",
                answer=None,
            )
            state.append(question)
            for affected in request.affects:
                state.edge(assumption_id, affected)
            state.event(
                "question",
                {"q_id": question.q_id, "assumption_id": assumption_id, "affects": request.affects},
            )
            return ok(
                {
                    **question.model_dump(mode="json", warnings=False),
                    "default_reference": Reference(
                        kind="assumption",
                        record_id=assumption_id,
                        version=1,
                        key=assumption.key,
                        unit=request.default.unit,
                    ).model_dump(mode="json", warnings=False),
                }
            )
        if isinstance(request, ExcelBuild):
            return self.build_excel(state, request)
        if isinstance(request, ExcelRecalc):
            return self.recalc_excel(state, request)
        if isinstance(request, RulesEval):
            return self.rules(state, request)
        if isinstance(request, Finalize):
            return self.finalize(state, request)
        if isinstance(request, DraftExternal):
            draft_id = "draft-" + files.digest(
                canonical(
                    [
                        self.context.scope.model_dump(warnings=False),
                        self.context.task_id,
                        self.context.deal_id,
                        identity,
                    ]
                ).encode()
            )
            parts = ("outbox", self.context.deal_id, self.context.task_id, draft_id + ".json")
            body = canonical(request.model_dump(mode="json", warnings=False)).encode()
            path = files.write(self.workspace, parts, body)
            state.event(
                "tool_result",
                {
                    "binding": "draft",
                    "identity": draft_id,
                    "deal": self.context.deal_id,
                    "task": self.context.task_id,
                    "kind": request.kind,
                    "to": request.to,
                    "path": str(path),
                    "digest": files.digest(body),
                    "deliverable_id": request.deliverable_id,
                },
            )
            return ok({"draft_id": draft_id})
        if isinstance(request, SendExternal):
            return self.prepare_send(state, request)
        raise Refusal("unknown_tool", "Choose a canonical CRE tool.")

    def assumption(self, state: ToolState, request: AssumptionSet) -> tuple[Assumption, str]:
        refs = [request.value, request.low, request.high]
        unit = request.value.unit
        if any(ref.unit != unit for ref in refs):
            raise Refusal("incompatible_evidence", "Default and bounds must have compatible units.")
        value, low, high = [resolve(state, ref) for ref in refs]
        if isinstance(value, Decimal):
            value, low, high = [number(state, ref, unit) for ref in refs]
            valid = low <= value <= high
        elif isinstance(value, str | bool):
            valid = (
                type(low) is type(value) is type(high)
                and value == low == high
                and unit == ("bool" if type(value) is bool else "text")
            )
        elif type(value) is date:
            valid = (
                type(low) is date and type(high) is date and unit == "date" and low <= value <= high
            )
        else:
            valid = False
        if not valid:
            raise Refusal(
                "invalid_input", "Default requires compatible canonical values and bounds."
            )
        assumption = Assumption(
            key=request.key,
            value=value,
            low=low,
            high=high,
            rationale=request.rationale,
            sources=list(dict.fromkeys(r.record_id for r in refs)),
            is_proxy=request.is_proxy,
            as_of=datetime.now(UTC).date(),
            set_by="user" if self.context.role == "user" else "agent",
        )
        identity = "assumption-" + files.digest(
            canonical(
                [
                    self.context.deal_id,
                    assumption.model_dump(mode="json", warnings=False),
                    [r.model_dump(mode="json", warnings=False) for r in refs],
                ]
            ).encode()
        )
        if state.current(Assumption, identity) == assumption:
            return assumption, identity
        for event in state.history(task_only=False):
            if (
                event.payload.get("binding") == "assumption"
                and event.payload.get("deal") == self.context.deal_id
                and event.payload.get("key") == request.key
            ):
                old_identity = event.payload["identity"]
                if isinstance(old_identity, str):
                    state.invalidate(old_identity)
        state.append(assumption, identity=identity)
        for ref in refs:
            state.edge(ref.record_id, identity)
        state.event(
            "tool_result",
            {
                "binding": "assumption",
                "identity": identity,
                "deal": self.context.deal_id,
                "key": request.key,
                "unit": unit,
                "digest": fingerprint(assumption),
                "references": [r.model_dump(mode="json", warnings=False) for r in refs],
            },
        )
        return assumption, identity

    def artifact(self, state: ToolState, identity: str, *, final_replay: bool = False) -> Artifact:
        return self.artifact_snapshot(state, identity, final_replay=final_replay)[0]

    def artifact_snapshot(
        self, state: ToolState, identity: str, *, final_replay: bool = False
    ) -> tuple[Artifact, ArtifactSnapshot]:
        from cre_brain.runner.tools.finalization import artifact_snapshot

        return artifact_snapshot(self, state, identity, final_replay=final_replay)

    def finalize(self, state: ToolState, request: Finalize) -> dict[str, Any]:
        from cre_brain.runner.tools.finalization import finalize

        return finalize(self, state, request)

    def require_gates(self) -> None:
        from cre_brain.runner.tools.finalization import require_gates

        return require_gates(self)

    def deadline(self, state: ToolState) -> None:
        if self.context != state.context:
            raise Refusal(
                "policy_conflict",
                "Host context changed during a tool call; resume through the host.",
            )
        now = datetime.now(UTC)
        sessions = [
            e.ts
            for e in state.history()
            if e.kind == "segment_start" and e.payload.get("tools_session")
        ]
        first = min([self.context.started_at, *sessions])
        if (now - self.context.started_at).total_seconds() > self.limits.max_session_s or (
            now - first
        ).total_seconds() > self.limits.max_wallclock_s:
            raise Refusal(
                "budget_exceeded", "Host deadline elapsed; request a host-authorized resume."
            )

    def host_toggle_updates(self, state: ToolState) -> list[dict[str, Any]]:
        # Revisions are assigned under the tenant tools lock, independent of task
        # sequence numbers or wall-clock changes. Legacy events precede revisions.
        updates = [e for e in state.history(task_only=False) if "host_toggles" in e.payload]
        for event in updates:
            revision = event.payload.get("host_toggle_revision", 0)
            if type(revision) is not int or revision < 0:
                raise Refusal("policy_conflict", "Host toggle ledger requires reconciliation.")
        updates.sort(
            key=lambda e: (
                e.payload.get("host_toggle_revision", 0),
                e.ts,
                e.task_id,
                e.seq or 0,
                e.event_id,
            )
        )
        return [e.payload for e in updates]

    def host_toggles(self, state: ToolState) -> ToggleSettings:
        updates = self.host_toggle_updates(state)
        return ToggleSettings.model_validate(
            updates[-1]["host_toggles"] if updates else self.settings.toggles.model_dump()
        )

    def set_host_toggles(self, **updates: str) -> None:
        # Host-only method; not a tool nor a CLI flag. Merge inside the tenant
        # transaction so another task's OFF cannot be lost to startup defaults.
        with self.transaction() as state:
            history = self.host_toggle_updates(state)
            toggles = ToggleSettings.model_validate(
                {**self.host_toggles(state).model_dump(warnings=False), **updates}
            )
            revision = history[-1].get("host_toggle_revision", 0) + 1 if history else 1
            state.event(
                "confirmation_response",
                {
                    "host_toggles": toggles.model_dump(warnings=False),
                    "host_toggle_revision": revision,
                },
            )

    def confirmed(self, state: ToolState, cid: str) -> bool:
        return any(
            e.kind == "confirmation_response"
            and e.payload.get("cid") == cid
            and e.payload.get("confirmed") is True
            for e in state.history()
        )

    def confirm(self, cid: str) -> None:
        """Host authenticated confirmation endpoint adapter, never a runner tool."""
        with self.transaction() as state:
            if not any(
                e.kind == "confirmation_request" and e.payload.get("cid") == cid
                for e in state.history()
            ):
                raise Refusal(
                    "invalid_confirmation", "Confirm only a pending action in this scoped task."
                )
            state.event("confirmation_response", {"cid": cid, "confirmed": True})

    def record_host_tokens(self, tokens: int) -> None:
        if type(tokens) is not int or tokens < 0:
            raise ValueError("Host token usage must be a nonnegative integer")
        with self.transaction() as state:
            state.event("usage", {"host_tokens": tokens, "session": self.context.session_id})

    def prepare_send(self, state: ToolState, request: SendExternal) -> dict[str, Any]:
        from cre_brain.runner.tools.external import prepare_send

        return prepare_send(self, state, request)

    def deliver(self, intent: dict[str, Any]) -> dict[str, Any]:
        from cre_brain.runner.tools.external import deliver

        return deliver(self, intent)

    def released_draft(self, state: ToolState, draft: dict[str, Any], raw: bytes) -> DraftExternal:
        from cre_brain.runner.tools.external import released_draft

        return released_draft(self, state, draft, raw)

    def rules(self, state: ToolState, request: RulesEval) -> dict[str, Any]:
        from cre_brain.rules.engine import INPUT_MODELS, evaluate
        from cre_brain.rules.models import Policy

        if request.table not in INPUT_MODELS:
            raise Refusal("invalid_input", "Choose a bundled allowlisted rule table.")
        policy = self.inputs.rule_policy(self.context, request.table)
        if policy is None:
            raise Refusal(
                "missing_provider", "Host must supply the authenticated firm policy for this table."
            )
        policy = type(policy).model_validate(policy.model_dump(warnings=False))
        if not isinstance(policy, Policy):
            raise Refusal("invalid_input", "Host policy must be a validated rule policy.")
        model = INPUT_MODELS[request.table]
        values: dict[str, Any] = {}
        for key, reference in request.input.items():
            if (
                key in {"policy", "source_ids", "assumption_ids"}
                or key not in model.model_fields
                or reference.key != key
            ):
                raise Refusal(
                    "invalid_input",
                    "Rule inputs must reference canonical fields; policy comes from the host.",
                )
            value = resolve(state, reference)
            if key in {"units", "vintage", "dd_days", "close_days"}:
                expected_unit = {
                    "units": "count",
                    "vintage": "year",
                    "dd_days": "days",
                    "close_days": "days",
                }[key]
                if (
                    reference.unit != expected_unit
                    or not isinstance(value, Decimal)
                    or value != value.to_integral_value()
                ):
                    raise Refusal(
                        "incompatible_evidence",
                        "Rule count/year/day fields require integral canonical inputs.",
                    )
                value = int(value)
            elif isinstance(value, Decimal):
                required = "USD" if key == "price" else "ratio"
                number(state, reference, required)
            elif reference.unit not in {"bool", "text"}:
                raise Refusal(
                    "incompatible_evidence",
                    "Rule strings/booleans require compatible canonical units.",
                )
            values[key] = value
        item = model.model_validate(
            {
                **values,
                "policy": policy,
                "source_ids": tuple(r.record_id for r in request.input.values()),
            }
        )
        return ok(evaluate(request.table, item).model_dump(mode="json", warnings=False))

    def build_excel(self, state: ToolState, request: ExcelBuild) -> dict[str, Any]:
        from cre_brain.runner.tools.excel import build_excel

        return build_excel(self, state, request)

    def recalc_excel(self, state: ToolState, request: ExcelRecalc) -> dict[str, Any]:
        from cre_brain.runner.tools.excel import recalc_excel

        return recalc_excel(self, state, request)
