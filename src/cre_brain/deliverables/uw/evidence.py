"""Additional UW lineage checks over T032's existing authenticated SQL bindings."""

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import cre_brain.finance
from cre_brain.domain import Assumption, CalcResult, Fact
from cre_brain.runner.policy import Refusal
from cre_brain.runner.tools.contracts import Reference
from cre_brain.runner.tools.evidence import MODELS, resolve
from cre_brain.runner.tools.json_io import canonical
from cre_brain.runner.tools.state import ToolState

from .models import EvidenceSnapshot


def finance_version() -> str:
    files = sorted(Path(cre_brain.finance.__file__).parent.glob("*.py"))
    return hashlib.sha256(b"".join(p.name.encode() + p.read_bytes() for p in files)).hexdigest()


def core_version() -> str:
    files = sorted(Path(__file__).parent.glob("*.py"))
    return hashlib.sha256(
        finance_version().encode() + b"".join(p.name.encode() + p.read_bytes() for p in files)
    ).hexdigest()


MAX_REFERENCES = 2048
MAX_DEPENDENCY_EDGES = 4096
MAX_DEPENDENCY_DEPTH = 20  # Matches the shared canonical resolver.
MAX_RESOLUTION_WORK = 16384
MAX_BINDING_BYTES = 1048576


def binding_snapshot(binding: dict[str, object]) -> str:
    # Host model snapshots include output-unit maps for up to 360 months. They
    # are not tool messages; keep the shared tool transport limit unchanged.
    encoded = json.dumps(
        binding, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )
    if len(encoded.encode()) > MAX_BINDING_BYTES:
        raise Refusal("unsupported_inputs", "UW binding snapshots support at most 1 MiB each.")
    return encoded


def inspect_evidence(state: ToolState, references: list[Reference]) -> tuple[EvidenceSnapshot, ...]:
    # Bound the complete graph BEFORE invoking the shared recursive resolver. A
    # small DAG can still expand exponentially when that resolver follows each edge.
    if len(references) > MAX_REFERENCES:
        raise Refusal("unsupported_inputs", "UW evidence supports at most 2048 references.")
    snapshots: dict[str, EvidenceSnapshot] = {}
    dependencies: dict[str, list[Reference]] = {}
    records: dict[str, Fact | Assumption | CalcResult] = {}
    costs: dict[str, int] = {}
    heights: dict[str, int] = {}
    versions = {finance_version(), core_version()}
    history = state.history(task_only=False)  # Already filtered by authenticated tenant scope.
    active_assumptions = {}
    for event in sorted(history, key=lambda e: (e.ts, e.seq or 0, e.event_id)):
        if event.payload.get("binding") == "assumption":
            active_assumptions[(event.payload.get("deal"), event.payload.get("key"))] = (
                event.payload
            )
    edge_count = 0

    def identity(ref: Reference) -> str:
        return canonical(ref.model_dump(mode="json"))

    def visit(ref: Reference, active: frozenset[str] = frozenset()) -> None:
        nonlocal edge_count
        key = identity(ref)
        if ref.record_id in active:
            raise Refusal("stale_evidence", "Regenerate cyclic canonical dependencies.")
        if len(active) >= MAX_DEPENDENCY_DEPTH:
            raise Refusal("unsupported_inputs", "UW dependency depth supports at most 20 records.")
        if key in snapshots:
            if len(active) + heights[key] > MAX_DEPENDENCY_DEPTH:
                raise Refusal(
                    "unsupported_inputs", "UW dependency depth supports at most 20 records."
                )
            return
        if len(snapshots) >= MAX_REFERENCES:
            raise Refusal("unsupported_inputs", "UW evidence supports at most 2048 references.")
        record = state.current(MODELS[ref.kind], ref.record_id)
        binding = state.binding(ref.record_id, ref.kind)
        if record is None:
            raise Refusal("stale_evidence", "Reference must pin the current scoped source version.")
        if binding is None:
            raise Refusal("untrusted_evidence", "Host-authenticated evidence binding is required.")
        assert isinstance(record, Fact | Assumption | CalcResult)
        raw_sources = binding.get("references", [])
        if not isinstance(raw_sources, list):
            raise Refusal("untrusted_evidence", "Canonical dependencies require a reference list.")
        edge_count += len(raw_sources)
        if edge_count > MAX_DEPENDENCY_EDGES:
            raise Refusal(
                "unsupported_inputs", "UW evidence supports at most 4096 dependency edges."
            )
        sources = [Reference.model_validate(r) for r in raw_sources]
        if isinstance(record, Assumption):
            if record.key != ref.key or binding.get("key") != record.key:
                raise Refusal("incompatible_evidence", "Assumption key differs from its binding.")
            current = active_assumptions.get((state.context.deal_id, record.key))
            if binding.get("deal") != state.context.deal_id:
                raise Refusal("untrusted_evidence", "Assumption must belong to this host deal.")
            if current is None or current.get("identity") != ref.record_id:
                raise Refusal(
                    "stale_evidence", "Use the active canonical assumption for this deal/key."
                )
        if isinstance(record, Fact) and not record.provenance:
            raise Refusal("untrusted_evidence", "Facts need stored document/page/cell provenance.")
        if isinstance(record, CalcResult) and (
            not sources
            or set(record.inputs.values()) != {r.record_id for r in sources}
            or record.code_version not in versions
        ):
            raise Refusal("untrusted_evidence", "Refresh fully bound calculations at current code.")
        snapshots[key] = EvidenceSnapshot(
            reference=ref,
            record_json=record.model_dump_json(warnings=False),
            binding_json=binding_snapshot(binding),
        )
        records[key] = record
        dependencies[key] = sources
        for source in sources:
            visit(source, active | {ref.record_id})
        costs[key] = 1 + sum(costs[identity(source)] for source in sources)
        heights[key] = 1 + max((heights[identity(source)] for source in sources), default=0)
        if sum(costs.values()) > MAX_RESOLUTION_WORK:
            raise Refusal(
                "unsupported_inputs", "UW dependency resolution supports at most 16384 visits."
            )

    for reference in references:
        visit(reference)
    # Each unique reference is resolved once here, including source range values.
    resolved = {key: resolve(state, snapshot.reference) for key, snapshot in snapshots.items()}
    for key, record in records.items():
        if isinstance(record, Assumption):
            sources = dependencies[key]
            if (
                len(sources) != 3
                or record.sources != list(dict.fromkeys(r.record_id for r in sources))
                or [resolved[identity(r)] for r in sources]
                != [record.value, record.low, record.high]
                or any(r.unit != snapshots[key].reference.unit for r in sources)
                or not isinstance(record.value, Decimal)
                or not isinstance(record.low, Decimal)
                or not isinstance(record.high, Decimal)
                or not record.low <= record.value <= record.high
            ):
                raise Refusal(
                    "invalid_assumption", "Supply a sourced numeric value inside its range."
                )
    return tuple(snapshots[key] for key in sorted(snapshots))
