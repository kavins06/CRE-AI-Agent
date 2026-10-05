"""Bounded host descriptors and deterministic SCREEN results."""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from cre_brain.domain import CalcResult
from cre_brain.runner.tools.contracts import ID, Boundary, Reference


class Document(Boundary):
    doc_id: ID
    filename: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_. -]{1,160}$")]


class Classification(Boundary):
    doc_id: ID
    kind: Literal["om", "rent_roll", "t12", "lease", "unknown", "ambiguous", "unsupported"]
    method: Literal["rules"] = "rules"


class ScreenRequest(Boundary):
    run_id: ID
    documents: tuple[Document, ...] = Field(min_length=1, max_length=32)
    headlines: dict[ID, Reference] = Field(max_length=16)


class ScreenRun(Boundary):
    run_id: ID
    recommendation: Literal["GO", "NO_GO", "UNKNOWN"]
    classifications: tuple[Classification, ...]
    risk: CalcResult | None
    markdown: str
    json_memo: dict[str, str]
    deliverable_ids: tuple[str, ...]
    questions: tuple[str, ...]
    elapsed_ns: int = Field(strict=True, ge=0)
