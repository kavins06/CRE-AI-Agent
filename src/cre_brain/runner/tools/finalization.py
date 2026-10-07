"""Authenticated artifact identity and all-gate release transition."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from cre_brain.domain import Deliverable, GateResult
from cre_brain.domain.base import TenantScope
from cre_brain.gates.snapshot import ArtifactSnapshot, CompanionSnapshot
from cre_brain.runner.policy import ADVISORY, Refusal, required_gates
from cre_brain.runner.tools import files
from cre_brain.runner.tools.contracts import Artifact, Finalize
from cre_brain.runner.tools.json_io import canonical
from cre_brain.runner.tools.registry import ToolRegistry, ok, refused
from cre_brain.runner.tools.state import ToolState
from cre_brain.state import publications


class PublicationAuthority(Protocol):
    """Independent, host-bound lifecycle authorization; never a gate verdict.

    Existing hosts may omit this additional restriction. Once an embedding binds
    it to a registry, every finalization and trusted release replay must authorize
    under the same canonical transaction, regardless of the chosen gate provider.
    """

    def authorize(self, registry: ToolRegistry, state: ToolState) -> None: ...


def authorize_publication(registry: ToolRegistry, state: ToolState) -> None:
    authority = registry.publication_authority
    if authority is not None:
        authority.authorize(registry, state)


def artifact_snapshot(
    registry: ToolRegistry,
    state: ToolState,
    identity: str,
    *,
    final_replay: bool = False,
) -> tuple[Artifact, ArtifactSnapshot]:
    anchor = registry.inputs.artifact(registry.context, identity)
    if anchor is None:
        raise Refusal(
            "missing_provider", "Host must authenticate the canonical artifact and gate plan."
        )
    anchor = Artifact.model_validate(anchor.model_dump(warnings=False))
    expected = Deliverable.model_validate(anchor.deliverable.model_dump(warnings=False))
    current = state.current(Deliverable, identity)
    if current is None:
        raise Refusal("untrusted_artifact", "Host artifact must exist in scoped canonical state.")
    comparable = current
    if final_replay and current.status == "final" and current.version == expected.version + 1:
        comparable = Deliverable.model_validate(
            {
                **current.model_dump(warnings=False),
                "version": expected.version,
                "status": expected.status,
                "gate_results": expected.gate_results,
                "parent_version": expected.parent_version,
            }
        )
    if (
        comparable != expected
        or expected.d_id != identity
        or expected.deal_ids != [registry.context.deal_id]
    ):
        raise Refusal(
            "untrusted_artifact",
            "Reload the current canonical kind, deal, version and artifact identity.",
        )
    root = registry.workspace / "deals" / registry.context.deal_id / "deliverables"
    files.relative(root, Path(expected.path))
    if not state.fresh(identity) or any(not state.fresh(dep) for dep in current.depends_on):
        raise Refusal(
            "stale_evidence", "Regenerate the artifact after source or assumption changes."
        )
    data = files.read(registry.workspace, Path(expected.path))
    if files.digest(data) != anchor.sha256:
        raise Refusal(
            "untrusted_artifact",
            "Artifact bytes changed; host must register a new canonical version.",
        )
    companions = []
    for companion in anchor.companions:
        files.relative(root, companion.path)
        body = files.read(registry.workspace, companion.path)
        if files.digest(body) != companion.sha256 or companion.path == Path(expected.path):
            raise Refusal("untrusted_artifact", "Companion memo changed; register a new version.")
        companions.append(CompanionSnapshot(companion.path, body, companion.sha256))
    if final_replay and current.status == "final":
        stored_anchor, stored = publications.load_release(
            state.connection, registry.context, identity, current.version
        )
        if stored_anchor != anchor or not stored:
            raise Refusal("untrusted_artifact", "Protected publication requires its bound anchor.")
        snapshot = ArtifactSnapshot(
            stored[0].body,
            anchor.sha256,
            tuple(
                CompanionSnapshot(companion.path, published.body, companion.sha256)
                for companion, published in zip(anchor.companions, stored[1:], strict=True)
            ),
        )
        if publications.prepare(registry.context, anchor, snapshot) != stored:
            raise Refusal("untrusted_artifact", "Protected publication references must match.")
        return anchor, snapshot
    return anchor, ArtifactSnapshot(data, anchor.sha256, tuple(companions))


def finalize(registry: ToolRegistry, state: ToolState, request: Finalize) -> dict[str, Any]:
    authorize_publication(registry, state)
    anchor, snapshot = registry.artifact_snapshot(state, request.deliverable_id, final_replay=True)
    registry.require_gates()
    assert registry.gates is not None
    d = anchor.deliverable
    current = state.current(Deliverable, d.d_id)
    if current is not None and current.status == "final":
        trusted_release(registry, state, anchor, snapshot, current)
        return ok({"deliverable_id": current.d_id, "version": current.version, "status": "final"})
    if d.status not in {"draft", "conditional"}:
        raise Refusal(
            "untrusted_artifact",
            "Only a current draft or conditional artifact can be finalized.",
        )
    results = []
    failures = []
    for gate in required_gates(d.kind, anchor.extraction):
        try:
            result = registry.gates.check_bytes(gate, d, snapshot)
            if type(result.passed) is not bool:
                raise ValueError("Gate verdict must be a genuine boolean")
            result = GateResult.model_validate(result.model_dump(warnings=False))
            canonical(result.model_dump(mode="json", warnings=False))
            passed = result.passed and not result.failures
            # Provider details may include paths or credentials; store safe gate names only.
            result = GateResult(
                passed=passed,
                failures=[] if passed else [f"{gate}: required check failed or unavailable"],
                metrics=result.metrics,
            )
        except Exception:
            result = GateResult(
                passed=False, failures=[f"{gate}: trusted checker unavailable"], metrics={}
            )
        results.append(result)
        state.event(
            "gate_result",
            {
                "deliverable_id": d.d_id,
                "gate": gate,
                "sha256": snapshot.sha256,
                "result": result.model_dump(mode="json", warnings=False),
            },
        )
        if gate not in ADVISORY and not result.passed:
            failures.append(gate)
    if failures:
        # Persist every trusted gate result without blessing a release transition.
        return {
            **refused("gate_failure", "Resolve all required blocking gates before release."),
            "failures": failures,
        }
    # Revalidate canonical identity/freshness and the current published bytes.
    # The gates consumed only the immutable authenticated snapshot above.
    registry.deadline(state)
    registry.artifact(state, d.d_id)
    final = Deliverable.model_validate(
        {
            **d.model_dump(warnings=False),
            "version": d.version + 1,
            "status": "final",
            "parent_version": d.version,
            "gate_results": results,
        }
    )
    prepared = publications.prepare(registry.context, anchor, snapshot)
    publication = publications.encode(registry.context, anchor, prepared)
    payload = {
        "d_id": d.d_id,
        "version": final.version,
        "status": "final",
        "sha256": anchor.sha256,
        "publication": publications.references(prepared),
        **(
            {"companions": {str(c.path): c.sha256 for c in anchor.companions}}
            if anchor.companions
            else {}
        ),
    }
    # Bound metadata before the last deadline check. Lossless bodies are never
    # encoded into the ordinary stored/streamed/exported event envelope.
    canonical(payload)
    registry.deadline(state)
    authorize_publication(registry, state)
    state.append(final, publication=publication)
    state.event("deliverable", payload)
    # A workspace race during the transition must roll back the entire release.
    # Consumers can retrieve committed bytes independently of subsequent mirrors.
    registry.artifact(state, d.d_id, final_replay=True)
    registry.deadline(state)
    return ok({"deliverable_id": d.d_id, "version": final.version, "status": "final"})


def published_artifact(
    registry: ToolRegistry, identity: str, publication_id: str, *, version: int | None = None
) -> bytes:
    """Host-only retrieval, including historical releases, without reading mirrors.

    The registry context comes from trusted host authentication, never URL claims.
    Version/reference may come from a caller; the scoped row and trusted release
    event authenticate them. Omitted versions require canonical freshness; only
    explicit versions permit archival reads of invalidated immutable releases.
    """
    if registry.context.role not in {"lead", "user"}:
        raise Refusal("unauthorized_role", "Publication retrieval requires host authorization.")
    with registry.transaction() as state:
        current_read = version is None
        records = state.records(Deliverable, identity)
        if version is None:
            version = records[-1].version if records else None
        if type(version) is not int or version < 2:
            raise Refusal("untrusted_artifact", "Retrieve a published canonical version.")
        current = next((d for d in records if d.version == version), None)
        if current is None:
            raise Refusal("untrusted_artifact", "Release does not belong to this tenant.")
        anchor, stored = publications.load_release(
            state.connection, registry.context, identity, version
        )
        root = registry.workspace / "deals" / registry.context.deal_id / "deliverables"
        for item in stored:
            files.relative(root, Path(item.path))
        if (
            stored[0].path != anchor.deliverable.path
            or stored[0].sha256 != anchor.sha256
            or [(p.path, p.sha256) for p in stored[1:]]
            != [(str(c.path), c.sha256) for c in anchor.companions]
        ):
            raise Refusal("untrusted_artifact", "Protected bytes must match release descriptors.")
        snapshot = ArtifactSnapshot(
            stored[0].body,
            stored[0].sha256,
            tuple(CompanionSnapshot(Path(p.path), p.body, p.sha256) for p in stored[1:]),
        )
        registry.require_gates()
        trusted_release(registry, state, anchor, snapshot, current)
        if current_read and (
            not state.fresh(identity) or any(not state.fresh(dep) for dep in current.depends_on)
        ):
            raise Refusal(
                "stale_evidence", "Regenerate the artifact after source or assumption changes."
            )
        for item in stored:
            if item.publication_id == publication_id:
                return item.body
        raise Refusal("untrusted_artifact", "Reference does not belong to this protected release.")


def trusted_release(
    registry: ToolRegistry,
    state: ToolState,
    anchor: Artifact,
    snapshot: ArtifactSnapshot,
    current: Deliverable,
) -> None:
    """One authentication rule for finalization replay, FakeRunner and external sends."""
    authorize_publication(registry, state)
    names = required_gates(current.kind, anchor.extraction)
    baseline = Deliverable.model_validate(
        {
            **current.model_dump(warnings=False),
            "version": anchor.deliverable.version,
            "status": anchor.deliverable.status,
            "gate_results": anchor.deliverable.gate_results,
            "parent_version": anchor.deliverable.parent_version,
        }
    )
    if (
        baseline != anchor.deliverable
        or current.deal_ids != [registry.context.deal_id]
        or current.status != "final"
        or current.version != anchor.deliverable.version + 1
        or current.parent_version != anchor.deliverable.version
        or len(current.gate_results) != len(names)
        or any(
            name not in ADVISORY and (result.passed is not True or result.failures)
            for name, result in zip(names, current.gate_results, strict=True)
        )
    ):
        raise Refusal("untrusted_artifact", "Final status requires complete blocking gate results.")
    prepared = publications.prepare(registry.context, anchor, snapshot)
    stored_anchor, stored = publications.load_release(
        state.connection, registry.context, current.d_id, current.version
    )
    if stored_anchor != anchor or stored != prepared:
        raise Refusal("untrusted_artifact", "References must authenticate scoped stored bytes.")
    if not any(
        e.kind == "deliverable"
        and e.runner == "tools"
        and e.source == "tool"
        and e.release_id == registry.context.release_id
        and e.payload.get("d_id") == current.d_id
        and e.payload.get("version") == current.version
        and e.payload.get("status") == "final"
        and e.payload.get("sha256") == anchor.sha256
        and e.payload.get("companions", {}) == {str(c.path): c.sha256 for c in anchor.companions}
        and e.payload.get("publication") == publications.references(prepared)
        for e in state.history()
    ):
        raise Refusal(
            "untrusted_artifact", "Final status requires a trusted immutable gate-bound release."
        )


def require_gates(registry: ToolRegistry) -> None:
    if registry.gates is None:
        raise Refusal(
            "missing_provider",
            "Finalization requires a host-authenticated GateService provider.",
        )
    if (
        TenantScope.model_validate(registry.gates.scope.model_dump(warnings=False))
        != registry.context.scope
    ):
        raise Refusal("unauthorized_scope", "Gate provider must be authenticated to this tenant.")
