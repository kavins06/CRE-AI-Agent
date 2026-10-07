"""Product Excel path: validated build, intact formulas and complete parity."""

from pathlib import Path

from cre_brain.config.settings import GateSettings
from cre_brain.domain import GateResult
from cre_brain.excel.base import ExcelEngine
from cre_brain.excel.models import WorkbookBuild
from cre_brain.excel.parity import check_parity
from cre_brain.excel.validation import validate_mapped_workbook


def recalc_deliverable(
    build: WorkbookBuild, engine: ExcelEngine, *, gates: GateSettings
) -> tuple[Path, GateResult]:
    """Return the saved recalculated file and its complete deliverable gate.

    Only a build from build_workbook is authoritative. Reconstruction rechecks
    descriptor shape and coverage; it does not attest arbitrary input provenance.
    A failed numeric gate is reviewable; it must never be finalized.
    """
    build = WorkbookBuild.model_validate(build.model_dump())
    validate_mapped_workbook(build.path, build.mapping, gates=gates)
    output = engine.recalc(build.path)
    gate = check_parity(output, build.expected, gates=gates, mapping=build.mapping)
    return output, gate
