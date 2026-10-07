"""Host composition boundaries; numbers enter only through canonical references."""

from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import Field

from cre_brain.runner.tools.contracts import ID, Boundary, FinanceRun, Reference


class UWRequest(Boundary):
    proforma: dict[ID, Reference] = Field(max_length=8)
    taxes: dict[ID, Reference | None] | None = Field(default=None, max_length=9)
    value_add: dict[ID, Reference] | None = Field(default=None, max_length=8)
    debt: dict[ID, Reference] | None = Field(default=None, max_length=12)
    returns: FinanceRun | None = None


class EvidenceSnapshot(Boundary):
    reference: Reference
    record_json: str
    binding_json: str


class ModelNumber(Boundary):
    value: Decimal
    reference: Reference


class CalculationSnapshot(Boundary):
    component: Literal["proforma", "taxes", "value_add", "debt", "returns"]
    calc_id: ID
    code_version: str
    record_json: str
    numbers: tuple[ModelNumber, ...] = Field(min_length=1)

    def output(self, key: str) -> ModelNumber:
        return next(number for number in self.numbers if number.reference.key == key)


class UWModel(Boundary):
    """Immutable Python snapshot of SQL records, never a publication authority."""

    status: Literal["computed"] = "computed"
    deal_id: ID
    task_id: ID
    calculations: tuple[CalculationSnapshot, ...] = Field(min_length=1)
    evidence: tuple[EvidenceSnapshot, ...]
    irr_status: Literal["not_requested", "unique", "undefined", "ambiguous"]
    recommendation: None = None

    def calculation(self, component: str) -> CalculationSnapshot:
        return next(calc for calc in self.calculations if calc.component == component)


class UWQuestion(Boundary):
    field: str
    text: str


class UWRefusal(Boundary):
    status: Literal["refused"] = "refused"
    code: str
    questions: tuple[UWQuestion, ...]


class UWWorkbook(Boundary):
    """Recalculated draft artifact; paired publication remains a T038 dependency."""

    status: Literal["recalculated"] = "recalculated"
    artifact_id: ID
    path: Path
    sha256: str
