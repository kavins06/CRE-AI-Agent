"""Schema-only seller observations. No model-issued identities, authority or numbers."""

from typing import Annotated, Literal, Protocol

from pydantic import Field, StringConstraints

from cre_brain.domain.base import Identifier
from cre_brain.extraction.preparse.models import Boundary, Digest, ParsedDocument
from cre_brain.runner.tools.contracts import AuthenticatedContext

DocType = Literal["rent_roll", "t12", "om_summary"]
SemanticField = Literal[
    "unit_id",
    "rent",
    "rent_total",
    "lease_end",
    "income",
    "income_total",
    "expense",
    "expense_total",
    "period",
    "property_name",
    "units",
    "units_total",
    "asking_price",
    "as_of",
]
ObservedText = Annotated[str, StringConstraints(min_length=1, max_length=4096)]


class Selection(Boundary):
    field: SemanticField
    anchor_id: Digest
    anchor_kind: Literal["cell", "text"]


class Observation(Selection):
    quote: ObservedText
    value: ObservedText  # Exact source lexeme; numeric JSON is forbidden.


class RentObservation(Observation):
    field: Literal["unit_id", "rent", "rent_total", "lease_end"]


class T12Observation(Observation):
    field: Literal["income", "income_total", "expense", "expense_total", "period"]


class OMObservation(Observation):
    field: Literal["property_name", "units", "units_total", "asking_price", "as_of"]


class RentRollOutput(Boundary):
    doc_type: Literal["rent_roll"]
    observations: Annotated[tuple[RentObservation, ...], Field(min_length=1, max_length=256)]


class T12Output(Boundary):
    doc_type: Literal["t12"]
    observations: Annotated[tuple[T12Observation, ...], Field(min_length=1, max_length=256)]


class OMSummaryOutput(Boundary):
    doc_type: Literal["om_summary"]
    observations: Annotated[tuple[OMObservation, ...], Field(min_length=1, max_length=256)]


OUTPUTS: dict[str, type[RentRollOutput] | type[T12Output] | type[OMSummaryOutput]] = {
    "rent_roll": RentRollOutput,
    "t12": T12Output,
    "om_summary": OMSummaryOutput,
}


class Reconciliation(Boundary):
    """Host inventory of source totals and source components; never model arithmetic."""

    parts: Annotated[tuple[Digest, ...], Field(min_length=1, max_length=255)]
    total: Digest


class SourceDocument(Boundary):
    """Issued by authenticated host preparse/intake, never deserialized from a tool call.

    parsed_sha256 authenticates the exact ParsedDocument.model_dump_json bytes.
    required and reconciliations are host-approved semantic/row inventories.
    Unsupported/incomplete inventories refuse, including documents without totals.
    """

    document: ParsedDocument
    parsed_sha256: Digest
    deal_id: Identifier
    doc_type: DocType
    required: Annotated[tuple[Selection, ...], Field(min_length=1, max_length=256)]
    reconciliations: Annotated[tuple[Reconciliation, ...], Field(min_length=1, max_length=32)]


class SourceProvider(Protocol):
    def document(self, context: AuthenticatedContext, identity: str) -> SourceDocument | None: ...


class ExtractionLimits(Boundary):
    max_source_bytes: Annotated[int, Field(ge=1, le=8 * 1024 * 1024)] = 2 * 1024 * 1024
    max_batch_observations: Annotated[int, Field(ge=1, le=1024)] = 256
    max_schema_bytes: Annotated[int, Field(ge=1, le=131072)] = 32768
    max_output_bytes: Annotated[int, Field(ge=1, le=2 * 1024 * 1024)] = 524288
    max_line_bytes: Annotated[int, Field(ge=1, le=131072)] = 131072
    max_events: Annotated[int, Field(ge=1, le=4096)] = 256
    max_tokens: Annotated[int, Field(ge=1, le=1000000)] = 20000
    max_turns: Annotated[int, Field(ge=1, le=16)] = 4
    timeout_s: Annotated[float, Field(gt=0, le=1200)] = 120
