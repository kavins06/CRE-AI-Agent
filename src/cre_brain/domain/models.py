"""Persisted, provider-neutral contracts for the CRE analyst."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum, auto
from typing import Annotated, ClassVar, Literal, Self, TypedDict

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer, model_validator

from cre_brain.domain.base import Identifier

PositiveInt = Annotated[int, Field(strict=True, ge=1)]
NonnegativeInt = Annotated[int, Field(strict=True, ge=0)]
FactValueData = str | Decimal | date | bool


class DecimalValueJson(TypedDict):
    type: Literal["decimal"]
    value: str


class DateValueJson(TypedDict):
    type: Literal["date"]
    value: str


FactValueJson = str | bool | DecimalValueJson | DateValueJson


def _encode_value(value: FactValueData) -> FactValueJson:
    if isinstance(value, Decimal):
        return DecimalValueJson(type="decimal", value=str(value))
    if isinstance(value, date):
        return DateValueJson(type="date", value=value.isoformat())
    return value


def _decode_value(value: object) -> object:
    if not isinstance(value, dict):
        return value
    if set(value) != {"type", "value"} or not isinstance(value["value"], str):
        raise ValueError("Tagged fact values need only type and a string value")
    if value["type"] == "decimal":
        try:
            return Decimal(value["value"])
        except ArithmeticError as error:
            raise ValueError("Invalid decimal fact value") from error
    if value["type"] == "date":
        return date.fromisoformat(value["value"])
    raise ValueError("Unknown fact value type")


# JSON strings cannot distinguish a date/Decimal from literal text.
FactValue = Annotated[
    FactValueData,
    BeforeValidator(_decode_value, json_schema_input_type=FactValueData | FactValueJson),
    PlainSerializer(_encode_value, return_type=FactValueJson, when_used="json"),
]


class DomainModel(BaseModel):
    """Strictly shaped value object used at storage and runner boundaries."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class ClaimType(StrEnum):
    SELLER_ASSERTION = auto()
    VERIFIED_FACT = auto()
    INTERPRETATION = auto()
    APPROVED_POLICY = auto()
    CONFLICT = auto()
    ASSUMPTION = auto()


class DeliverableKind(StrEnum):
    SCREEN = "SCREEN"
    UW_MODEL = "UW_MODEL"
    IC_MEMO = "IC_MEMO"
    DD_TRACKER = "DD_TRACKER"
    LOI = "LOI"
    BROKER_QUESTIONS = "BROKER_QUESTIONS"
    LEASE_ABSTRACT = "LEASE_ABSTRACT"
    DEAL_COMPARISON = "DEAL_COMPARISON"
    RENT_COMP_ANALYSIS = "RENT_COMP_ANALYSIS"
    DEBT_QUOTE_SUMMARY = "DEBT_QUOTE_SUMMARY"
    ESCALATION = "ESCALATION"


class DateRange(DomainModel):
    start: date | None = None
    end: date | None = None

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.start is not None and self.end is not None and self.start > self.end:
            raise ValueError("Date range start must not be after end")
        return self


class Provenance(DomainModel):
    doc_id: Identifier
    page: PositiveInt | None = None
    bbox: tuple[float, float, float, float] | None = None
    sheet: str | None = None
    cell: str | None = None
    quote: str | None = None


class Fact(DomainModel):
    fact_id: Identifier
    deal_id: Identifier
    key: Identifier
    value: FactValue
    unit: str | None = None
    claim_type: ClaimType
    provenance: list[Provenance]
    valid_time: DateRange | None = None
    known_at: datetime
    version: PositiveInt


class Assumption(DomainModel):
    key: Identifier
    value: FactValue
    low: FactValue
    high: FactValue
    rationale: str
    sources: list[str]
    is_proxy: bool
    as_of: date
    set_by: Literal["agent", "firm_policy", "user"]


class CalcResult(DomainModel):
    calc_id: Identifier
    fn: Identifier
    inputs: dict[str, str]
    outputs: dict[str, Decimal]
    code_version: str


class Question(DomainModel):
    q_id: Identifier
    task_id: Identifier
    deal_id: Identifier
    text: str
    why_it_matters: str
    default_used: str
    affects: list[str]
    status: Literal["open", "answered", "withdrawn"]
    answer: str | None


class GateResult(DomainModel):
    passed: bool
    failures: list[str]
    metrics: dict[str, Decimal]


class Deliverable(DomainModel):
    d_id: Identifier
    deal_ids: list[Identifier]
    kind: DeliverableKind
    version: PositiveInt
    status: Literal["draft", "final", "blocked", "conditional", "stale", "superseded"]
    path: str
    gate_results: list[GateResult]
    depends_on: list[str]
    edited_by_user: bool = False
    parent_version: PositiveInt | None = None


class Task(DomainModel):
    task_id: Identifier
    user_id: Identifier
    firm_id: Identifier
    deal_ids: list[Identifier]
    request: str
    requested: list[DeliverableKind] | None
    created_at: datetime


AgentSource = Literal["agent", "extractor", "tool", "gate", "user", "system"]
AgentEventKind = Literal[
    "message",
    "tool_call",
    "tool_result",
    "question",
    "answer",
    "user_message",
    "gate_result",
    "deliverable",
    "stale",
    "compaction",
    "budget",
    "usage",
    "confirmation_request",
    "confirmation_response",
    "interrupt",
    "pause",
    "resume",
    "segment_start",
    "segment_end",
    "recovery",
    "stuck",
    "error",
    "escalation",
    "runner_raw",
]


class AgentEvent(DomainModel):
    SOURCES: ClassVar[tuple[str, ...]] = (
        "agent",
        "extractor",
        "tool",
        "gate",
        "user",
        "system",
    )
    KINDS: ClassVar[tuple[str, ...]] = (
        "message",
        "tool_call",
        "tool_result",
        "question",
        "answer",
        "user_message",
        "gate_result",
        "deliverable",
        "stale",
        "compaction",
        "budget",
        "usage",
        "confirmation_request",
        "confirmation_response",
        "interrupt",
        "pause",
        "resume",
        "segment_start",
        "segment_end",
        "recovery",
        "stuck",
        "error",
        "escalation",
        "runner_raw",
    )

    event_id: Identifier
    task_id: Identifier
    seq: PositiveInt | None
    origin: tuple[Identifier, NonnegativeInt, NonnegativeInt] | None
    ts: datetime
    source: AgentSource
    kind: AgentEventKind
    cause_id: Identifier | None
    release_id: Identifier
    runner: Identifier
    schema_version: PositiveInt = 1
    payload: dict[str, object]
