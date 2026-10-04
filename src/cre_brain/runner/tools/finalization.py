"""Authenticated artifact identity and all-gate release transition."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cre_brain.domain import Deliverable, GateResult
from cre_brain.domain.base import TenantScope
from cre_brain.gates.snapshot import ArtifactSnapshot
from cre_brain.runner.policy import ADVISORY, Refusal, required_gates
from cre_brain.runner.tools import files
from cre_brain.runner.tools.contracts import Artifact, Finalize
from cre_brain.runner.tools.json_io import canonical
from cre_brain.runner.tools.registry import ToolRegistry, ok, refused
from cre_brain.runner.tools.state import ToolState


def artifact_snapshot(
    registry: ToolRegistry, state: ToolState, identity: str, *, final_replay: bool = False
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
    return anchor, ArtifactSnapshot(data, anchor.sha256)


def finalize(registry: ToolRegistry, state: ToolState, request: Finalize) -> dict[str, Any]:
    anchor, snapshot = registry.artifact_snapshot(state, request.deliverable_id, final_replay=True)
    registry.require_gates()
    assert registry.gates is not None
    d = anchor.deliverable
    current = state.current(Deliverable, d.d_id)
    if current is not None and current.status == "final":
        released = any(
            e.kind == "deliverable"
            and e.payload.get("d_id") == current.d_id
            and e.payload.get("version") == current.version
            and e.payload.get("sha256") == anchor.sha256
            for e in state.history()
        )
        if not released:
            raise Refusal(
                "untrusted_artifact",
                "Final status requires a trusted gate-bound release transition.",
            )
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
    registry.deadline(state)
    state.append(final)
    state.event(
        "deliverable",
        {"d_id": d.d_id, "version": final.version, "status": "final", "sha256": anchor.sha256},
    )
    return ok({"deliverable_id": d.d_id, "version": final.version, "status": "final"})


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
