"""Role outputs carry decisions and references, never authoritative financial values."""

from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from cre_brain.knowledge.models import Citation
from cre_brain.runner.tools.contracts import ID, Boundary, Reference

Text = Annotated[str, StringConstraints(min_length=1, max_length=4096)]
Role = Literal["lead", "extraction", "research", "verifier", "classifier", "reflection"]


class Statement(Boundary):
    text: Text
    references: tuple[Reference, ...] = Field(default=(), max_length=32)


class PlanItem(Boundary):
    investigation: Text
    why_it_matters: Text
    disconfirming_evidence: Text
    skill: Literal["screen", "multifamily", "underwriting", "diligence", "research", "review"]


class Plan(Boundary):
    thesis_to_test: Text
    investigations: tuple[PlanItem, ...] = Field(min_length=1, max_length=12)
    decision_dependencies: tuple[Text, ...] = Field(default=(), max_length=12)


class ToolCall(Boundary):
    name: Literal[
        "facts_get",
        "facts_put",
        "assumption_set",
        "finance_run",
        "excel_build",
        "excel_recalc_parity",
        "rules_eval",
        "ask_user",
        "knowledge_search",
    ]
    arguments: dict[str, object] = Field(max_length=32)
    purpose: Text


class SpecialistRequest(Boundary):
    role: Literal["extraction", "research"]
    assignment: Text
    required_evidence: tuple[Text, ...] = Field(min_length=1, max_length=12)


class QuestionDraft(Boundary):
    question: Text
    why_it_matters: Text
    decision_if_unanswered: Text
    priority: Literal["blocking", "material", "optional"]
    evidence_needed: tuple[Text, ...] = Field(min_length=1, max_length=12)


class Decision(Boundary):
    recommendation: Literal["proceed", "hold", "pass"]
    thesis: Text
    reasons: tuple[Statement, ...] = Field(min_length=1, max_length=16)
    conditions: tuple[Text, ...] = Field(max_length=16)
    unresolved: tuple[Text, ...] = Field(max_length=16)
    change_log: tuple[Text, ...] = Field(max_length=16)

    @model_validator(mode="after")
    def unresolved_proceed(self) -> Self:
        if self.recommendation == "proceed" and self.unresolved:
            raise ValueError("Unresolved decision dependencies require hold, not proceed")
        return self


class RoleOutput(Boundary):
    turn_id: ID


class AnalystStep(RoleOutput):
    action: Literal["plan", "tool", "delegate", "question", "decide"]
    plan: Plan | None = None
    tool: ToolCall | None = None
    delegate: SpecialistRequest | None = None
    question: QuestionDraft | None = None
    decision: Decision | None = None

    @model_validator(mode="after")
    def one_action(self) -> Self:
        expected = {"decide": "decision"}.get(self.action, self.action)
        present = {
            key
            for key in ("plan", "tool", "delegate", "question", "decision")
            if getattr(self, key) is not None
        }
        if present != {expected}:
            raise ValueError("Return exactly the payload matching action")
        return self


class Finding(Boundary):
    finding_id: ID
    severity: Literal["minor", "major", "stopping"]
    issue: Text
    required_action: Text
    references: tuple[Reference, ...] = Field(default=(), max_length=32)


class Review(RoleOutput):
    accepted: bool = Field(strict=True)
    findings: tuple[Finding, ...] = Field(max_length=16)
    strongest_contrary_case: Text

    @model_validator(mode="after")
    def independent_objections(self) -> Self:
        if self.accepted and any(f.severity != "minor" for f in self.findings):
            raise ValueError("Major/stopping objections require revision, not acceptance")
        return self


class SpecialistResult(RoleOutput):
    role: Literal["extraction", "research"]
    observations: tuple[Statement, ...] = Field(max_length=16)
    conflicts: tuple[Text, ...] = Field(max_length=16)
    missing_evidence: tuple[Text, ...] = Field(max_length=16)
    source_ids: tuple[ID, ...] = Field(max_length=16)
    citations: tuple[Citation, ...] = Field(default=(), max_length=16)
    limitations: tuple[Text, ...] = Field(min_length=1, max_length=16)


class TraceEvent(Boundary):
    role: Role
    turn_id: ID
    output: dict[str, object]


class InvestigationResult(Boundary):
    status: Literal["reviewed_draft", "needs_user", "review_blocked", "step_limit"]
    decision: Decision | None
    questions: tuple[QuestionDraft, ...]
    trace: tuple[TraceEvent, ...]
    brain_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    publication: Literal["not_authorized"] = "not_authorized"
