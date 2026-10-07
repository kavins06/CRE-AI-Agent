"""Build literal inputs and live formulas from tenant-scoped authoritative state."""

import json
import math
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.comments import Comment
from pydantic import BaseModel
from sqlalchemy import Engine, select

from cre_brain.config.settings import GateSettings
from cre_brain.domain import CalcResult, ClaimType, Fact
from cre_brain.domain.base import TenantScope
from cre_brain.excel.models import TemplateMap, WorkbookBuild
from cre_brain.excel.validation import validate_workbook
from cre_brain.finance.proforma import ProFormaInput, build_proforma
from cre_brain.state.graph import DependencyGraph
from cre_brain.state.store import SqlVersionedStore, tenant_filter


def _current_records[Record: BaseModel](
    engine: Engine, model: type[Record], scope: TenantScope
) -> list[Record]:
    store = SqlVersionedStore(engine, model)
    with engine.connect() as connection:
        ids = (
            connection.execute(
                select(store.table.c.record_id).where(tenant_filter(store.table, scope)).distinct()
            )
            .scalars()
            .all()
        )
    records = [store.current(record_id, scope=scope) for record_id in ids]
    return [record for record in records if record is not None]


def _excel_number(value: Decimal) -> float:
    if not value.is_finite():
        raise ValueError("Excel inputs must be finite Decimal values")
    result = float(value)
    if not math.isfinite(result) or (value != 0 and result == 0):
        raise ValueError("Value is outside Excel binary64 representability")
    # Excel stores at most 15 significant decimal digits. Reject hidden loss,
    # rather than silently changing authoritative money on input.
    if Decimal(format(result, ".15g")) != value:
        raise ValueError(
            "Input exceeds Excel 15-significant-digit precision; use a labelled solution"
        )
    return result


def build_workbook(
    template: Path,
    mapping: TemplateMap,
    target: Path,
    *,
    engine: Engine,
    scope: TenantScope,
    deal_id: str,
    task_id: str,
    calculations: dict[str, str],
    gates: GateSettings,
    as_of: date | None = None,
) -> WorkbookBuild:
    mapping = TemplateMap.model_validate(mapping.model_dump())
    validate_workbook(template, gates=gates)
    if target.resolve() == template.resolve() or target.suffix.lower() != ".xlsx":
        raise ValueError("Choose a separate .xlsx output path")
    stale = set(DependencyGraph(engine, release_id="excel").tenant_stale_items(scope=scope))
    facts = _current_records(engine, Fact, scope)
    by_id = {f.fact_id: f for f in facts}
    calcs = _current_records(engine, CalcResult, scope)
    by_calc = {c.calc_id: c for c in calcs}
    # CalcResult IDs are content identities. Storage's append-only seam permits
    # versions; divergent versions of one calc identity are ambiguous here.
    store = SqlVersionedStore(engine, CalcResult)
    ambiguous_calcs: set[str] = set()
    with engine.connect() as connection:
        for stored_calc in calcs:
            payloads = connection.execute(
                select(store.table.c.payload).where(
                    tenant_filter(store.table, scope),
                    store.table.c.record_id == stored_calc.calc_id,
                )
            ).scalars()
            if any(CalcResult.model_validate(p) != stored_calc for p in payloads):
                ambiguous_calcs.add(stored_calc.calc_id)
    required = {e.calculation for e in mapping.entries if e.source == "calc"}
    if set(calculations) != required:
        raise ValueError(
            "Provide exactly one stored calc ID for each template calculation namespace"
        )
    effective_date = as_of or datetime.now(UTC).date()

    def validate_fact(fact: Fact) -> None:
        if fact.deal_id != deal_id:
            raise ValueError("Incompatible deal in calculation provenance")
        if fact.fact_id in stale or fact.claim_type == ClaimType.CONFLICT:
            raise ValueError(f"Stale or conflicting fact {fact.fact_id}; resolve and regenerate")
        # A date admits knowledge through its UTC end-of-day, inclusive.
        # Naive timestamps cannot establish an evidence boundary.
        if fact.known_at.utcoffset() is None:
            raise ValueError(f"Fact {fact.fact_id} known_at requires a timezone")
        if fact.known_at.astimezone(UTC).date() > effective_date:
            raise ValueError(f"Fact {fact.fact_id} was not known at the as_of date")
        if fact.valid_time is not None and (
            (fact.valid_time.start is not None and fact.valid_time.start > effective_date)
            or (fact.valid_time.end is not None and fact.valid_time.end < effective_date)
        ):
            raise ValueError(f"Fact {fact.fact_id} is outside its valid time; refresh evidence")

    selected_facts: dict[str, Fact] = {}
    for entry in mapping.entries:
        if entry.source != "fact":
            continue
        matches = [f for f in facts if f.deal_id == deal_id and f.key == entry.key]
        if len(matches) != 1:
            raise ValueError(f"Missing or ambiguous fact key {entry.key} for this deal")
        fact = matches[0]
        validate_fact(fact)
        if fact.unit != entry.unit or not isinstance(fact.value, Decimal):
            raise ValueError(f"Fact {fact.fact_id} requires Decimal {entry.unit}")
        selected_facts[entry.key] = fact
    visited: set[str] = set()
    active: set[str] = set()

    def lineage(record_id: str) -> None:
        if record_id in ambiguous_calcs:
            raise ValueError(f"Ambiguous stored calculation identity {record_id}")
        if record_id in stale:
            raise ValueError(f"Stale dependency {record_id}; regenerate before Excel build")
        if record_id in active:
            raise ValueError("Circular stored calculation provenance")
        if record_id in visited:
            return
        if record_id in by_id and record_id in by_calc:
            raise ValueError(f"Ambiguous fact/calculation identity {record_id}")
        if record_id in by_id:
            validate_fact(by_id[record_id])
        elif record_id in by_calc:
            active.add(record_id)
            calc = by_calc[record_id]
            if not calc.inputs:
                raise ValueError("Calculation needs stored fact/calculation dependencies")
            for source in calc.inputs.values():
                lineage(source)
            active.remove(record_id)
        else:
            raise ValueError(f"Missing stored dependency {record_id}")
        visited.add(record_id)

    # Independently validate that the stored reference-model outputs correspond
    # to today's mapped input facts. Changing a fact without graph invalidation
    # cannot smuggle old calculation values into a fresh workbook.
    input_values: dict[str, Decimal] = {}
    for key, fact in selected_facts.items():
        assert isinstance(fact.value, Decimal)
        input_values[key] = fact.value
    verified = build_proforma(
        ProFormaInput(
            input_id="excel-validation",
            projection_months=60,
            **input_values,
        ),
        calc_id="excel-validation",
        code_version="reference-validation",
    )
    expected: dict[str, Decimal] = {}
    provenance: dict[str, dict[str, object]] = {}
    literals: dict[str, float] = {}
    for entry in mapping.entries:
        if entry.source == "fact":
            fact = selected_facts[entry.key]
            assert isinstance(fact.value, Decimal)
            value = fact.value
            provenance[entry.address] = {
                "source": "fact",
                "fact_id": fact.fact_id,
                "version": fact.version,
                "key": fact.key,
                "unit": fact.unit,
                "claim_type": fact.claim_type.value,
                "provenance": [p.model_dump(mode="json") for p in fact.provenance],
            }
        else:
            assert entry.calculation is not None
            calc_id = calculations[entry.calculation]
            lineage(calc_id)
            calc = by_calc.get(calc_id)
            if calc is None or calc.fn != entry.function or entry.key not in calc.outputs:
                raise ValueError(f"Incompatible calculation for {entry.address}")
            # The reference subset cannot mirror optional tax/value-add schedules.
            if mapping.template == "mf_standard" and any(
                v != 0
                for k, v in calc.outputs.items()
                if k.endswith((":property_tax", ":renovation_cost", ":value_add_gross_rent_impact"))
            ):
                raise ValueError(
                    "Reference template does not support optional tax/value-add schedules"
                )
            if not {f.fact_id for f in selected_facts.values()}.issubset(visited):
                raise ValueError("Calculation lineage must resolve every mapped fact input")
            value = calc.outputs[entry.key]
            if entry.role == "output" and verified.outputs.get(entry.key) != value:
                raise ValueError(
                    f"Stored calculation does not match current facts at {entry.address}"
                )
            provenance[entry.address] = {
                "source": "calc",
                "calc_id": calc.calc_id,
                "key": entry.key,
                "code_version": calc.code_version,
                "inputs": dict(calc.inputs),
            }
        if not value.is_finite():
            raise ValueError(f"Nonfinite stored value at {entry.address}")
        expected[entry.address] = value
        if entry.role == "input":
            literals[entry.address] = _excel_number(value)
    workbook = load_workbook(template)
    try:
        if set(workbook.defined_names) != {e.name for e in mapping.entries}:
            raise ValueError("Template names and map disagree")
        for entry in mapping.entries:
            if list(workbook.defined_names[entry.name].destinations) != [(entry.sheet, entry.cell)]:
                raise ValueError(f"Map/name mismatch for {entry.name}")
            cell = workbook[entry.sheet][entry.cell]
            if entry.formula is not None and cell.value != entry.formula:
                raise ValueError(f"Map/formula mismatch at {entry.address}")
            if entry.role == "input":
                if cell.data_type == "f":
                    raise ValueError("Input cell unexpectedly contains a formula")
                cell.value = literals[entry.address]
            cell.comment = Comment(
                json.dumps(provenance[entry.address], sort_keys=True), "CRE state"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(target)
    finally:
        workbook.close()
    return WorkbookBuild(path=target, mapping=mapping, expected=expected, provenance=provenance)
