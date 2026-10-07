"""Model-directed, bounded investigation. Review results never grant publication."""

import asyncio
import time
from typing import Any, Protocol

from pydantic import BaseModel, Field

from cre_brain.analyst.brain import Brain
from cre_brain.analyst.models import (
    AnalystStep,
    InvestigationResult,
    QuestionDraft,
    Review,
    Role,
    RoleOutput,
    SpecialistRequest,
    SpecialistResult,
    TraceEvent,
)
from cre_brain.knowledge.models import SearchResult
from cre_brain.runner.tools.contracts import Boundary, Reference
from cre_brain.runner.tools.evidence import resolve
from cre_brain.runner.tools.json_io import canonical
from cre_brain.runner.tools.registry import ToolRegistry


class DecisionClient(Protocol):
    async def decide(
        self,
        *,
        role: Role,
        instructions: str,
        context: dict[str, Any],
        schema: dict[str, Any],
        turn_id: str,
    ) -> dict[str, Any]: ...


class SpecialistInputs(Protocol):
    def snapshot(self, request: SpecialistRequest) -> dict[str, Any] | None: ...


class InvestigationLimits(Boundary):
    max_steps: int = Field(default=8, strict=True, ge=2, le=64)
    max_reviews: int = Field(default=2, strict=True, ge=1, le=4)
    turn_seconds: int = Field(default=300, strict=True, ge=1, le=1800)
    total_seconds: int = Field(default=1800, strict=True, ge=1, le=7200)


class AnalystLoop:
    def __init__(
        self,
        *,
        brain: Brain,
        client: DecisionClient,
        registry: ToolRegistry,
        specialist_inputs: SpecialistInputs | None = None,
        limits: InvestigationLimits | None = None,
    ) -> None:
        self.brain = brain
        self.client = client
        self.registry = registry.clone()
        self.specialist_inputs = specialist_inputs
        self.limits = limits or InvestigationLimits()

    async def investigate(
        self,
        *,
        request: str,
        evidence: dict[str, Any],
        run_id: str,
    ) -> InvestigationResult:
        """Host supplies approved scoped evidence, never raw seller documents."""
        from pydantic import TypeAdapter

        from cre_brain.runner.tools.contracts import ID, Text

        TypeAdapter(ID).validate_python(run_id)
        TypeAdapter(Text).validate_python(request)
        observations: list[dict[str, Any]] = []
        trace: list[TraceEvent] = []
        questions: list[QuestionDraft] = []
        reviews: list[dict[str, Any]] = []
        decision = None
        planned = False
        started = time.monotonic()
        binding = canonical(self.registry.context.model_dump(mode="json"))

        def references(model: BaseModel) -> None:
            def walk(value: Any) -> None:
                if isinstance(value, Reference):
                    with self.registry.transaction() as state:
                        resolve(state, value, trusted=False)
                elif isinstance(value, BaseModel):
                    for key in type(value).model_fields:
                        walk(getattr(value, key))
                elif isinstance(value, (tuple, list)):
                    for child in value:
                        walk(child)

            walk(model)

        async def ask[T: RoleOutput](role: Role, context: dict[str, Any], model: type[T]) -> T:
            if canonical(self.registry.context.model_dump(mode="json")) != binding:
                raise ValueError("Authenticated analyst scope changed")
            remaining = self.limits.total_seconds - (time.monotonic() - started)
            if remaining <= 0:
                raise TimeoutError("Investigation wall-clock budget exhausted")
            turn_id = f"{run_id}-{len(trace) + 1}"
            canonical(context)
            output = await asyncio.wait_for(
                self.client.decide(
                    role=role,
                    instructions=self.brain.instructions(role),
                    context=context,
                    schema=model.model_json_schema(),
                    turn_id=turn_id,
                ),
                timeout=min(self.limits.turn_seconds, remaining),
            )
            if canonical(self.registry.context.model_dump(mode="json")) != binding:
                raise ValueError("Authenticated analyst scope changed during decision")
            canonical(output)
            parsed = model.model_validate(output)
            if parsed.turn_id != turn_id:
                raise ValueError("Decision belongs to a different or stale turn")
            references(parsed)
            trace.append(TraceEvent(role=role, turn_id=turn_id, output=output))
            return parsed

        def result(status: str) -> InvestigationResult:
            return InvestigationResult.model_validate(
                {
                    "status": status,
                    "decision": decision,
                    "questions": tuple(questions),
                    "trace": tuple(trace),
                    "brain_sha256": self.brain.sha256,
                }
            )

        for _ in range(self.limits.max_steps):
            step = await ask(
                "lead",
                {
                    "request": request,
                    "evidence": evidence,
                    "observations": observations,
                    "prior_reviews": reviews,
                    "questions": [q.model_dump() for q in questions],
                    "available_tools": {
                        name: model.model_json_schema()
                        for name, model in self.registry.tool_models.items()
                        if name not in {"finalize_deliverable", "draft_external", "send_external"}
                    },
                    "phase": "investigate" if planned else "plan_first",
                },
                AnalystStep,
            )
            assert isinstance(step, AnalystStep)
            if not planned and step.action != "plan":
                raise ValueError("An investigation plan must precede other actions")
            if step.plan is not None:
                planned = True
                observations.append({"plan": step.plan.model_dump(mode="json")})
            elif step.tool is not None:
                response = self.registry.call(
                    step.tool.name,
                    dict(step.tool.arguments),
                    request_id=f"{step.turn_id}-tool",
                )
                observations.append(
                    {
                        "tool": step.tool.name,
                        "purpose": step.tool.purpose,
                        "response": response,
                    }
                )
            elif step.delegate is not None:
                snapshot = (
                    self.specialist_inputs.snapshot(step.delegate)
                    if self.specialist_inputs is not None
                    else None
                )
                if snapshot is None and step.delegate.role == "research":
                    snapshot = {
                        "knowledge": self.registry.call(
                            "knowledge_search",
                            {"query": step.delegate.assignment[:500]},
                            request_id=f"{step.turn_id}-knowledge",
                        )
                    }
                if snapshot is None:
                    observations.append(
                        {
                            "role": step.delegate.role,
                            "status": "unavailable",
                            "message": "Host must provide an authorized specialist snapshot",
                        }
                    )
                    continue
                specialist = await ask(
                    step.delegate.role,
                    {
                        "assignment": step.delegate.model_dump(mode="json"),
                        "evidence": snapshot,
                    },
                    SpecialistResult,
                )
                assert isinstance(specialist, SpecialistResult)
                if specialist.role != step.delegate.role:
                    raise ValueError("Specialist returned a different role")
                if specialist.role == "research":
                    knowledge = snapshot.get("knowledge", {})
                    hits = (
                        SearchResult.model_validate(knowledge["data"]).hits
                        if isinstance(knowledge, dict) and knowledge.get("status") == "ok"
                        else ()
                    )
                    allowed = {hit.citation.resource_id for hit in hits}
                    citations = {canonical(hit.citation.model_dump(mode="json")) for hit in hits}
                    if (
                        set(specialist.source_ids) - allowed
                        or any(statement.references for statement in specialist.observations)
                        or any(
                            canonical(citation.model_dump(mode="json")) not in citations
                            or citation.resource_id not in specialist.source_ids
                            for citation in specialist.citations
                        )
                    ):
                        raise ValueError("Research cannot invent citations or property Fact pins")
                    observations.append({"public_knowledge": knowledge})
                observations.append({"specialist": specialist.model_dump(mode="json")})
            elif step.question is not None:
                questions.append(step.question)
                if step.question.priority == "blocking":
                    return result("needs_user")
            elif step.decision is not None:
                decision = step.decision
                if decision.recommendation == "proceed" and any(
                    q.priority != "optional" for q in questions
                ):
                    raise ValueError("Unanswered material questions cannot support proceed")
                if reviews and not decision.change_log:
                    raise ValueError("A revised recommendation requires a change log")
                review = await ask(
                    "verifier",
                    {
                        "request": request,
                        "evidence": evidence,
                        "observations": observations,
                        "candidate": decision.model_dump(mode="json"),
                        "prior_reviews": reviews,
                    },
                    Review,
                )
                assert isinstance(review, Review)
                reviews.append(review.model_dump(mode="json"))
                if review.accepted:
                    return result("reviewed_draft")
                if len(reviews) >= self.limits.max_reviews:
                    return result("review_blocked")
        return result("step_limit")
