from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from hypothesis import given
from pydantic import ValidationError

from cre_brain.domain import (
    AgentEvent,
    Assumption,
    CalcResult,
    ClaimType,
    DateRange,
    Deliverable,
    DeliverableKind,
    Fact,
    GateResult,
    Provenance,
    Question,
    Task,
)
from tests.domain.strategies import agent_events, calc_results, facts


def test_t010_ac1_exact_domain_contracts_are_available() -> None:
    source = Provenance(doc_id="om", page=7, quote="NOI is $1,000")
    fact = Fact(
        fact_id="fact-1",
        deal_id="deal-1",
        key="noi",
        value=Decimal("1000"),
        unit="USD/year",
        claim_type=ClaimType.VERIFIED_FACT,
        provenance=[source],
        valid_time=DateRange(start=date(2026, 1, 1), end=date(2026, 12, 31)),
        known_at=datetime(2026, 10, 4, tzinfo=UTC),
        version=1,
    )
    assumption = Assumption(
        key="exit_cap",
        value=Decimal("0.055"),
        low=Decimal("0.05"),
        high=Decimal("0.06"),
        rationale="Current market range",
        sources=["reference-1"],
        is_proxy=True,
        as_of=date(2026, 10, 4),
        set_by="agent",
    )
    calc = CalcResult(
        calc_id="calc-1",
        fn="cap_rate",
        inputs={"noi": fact.fact_id},
        outputs={"cap_rate": Decimal("0.05")},
        code_version="finance-v1",
    )
    question = Question(
        q_id="q-1",
        task_id="task-1",
        deal_id="deal-1",
        text="Confirm reassessment ratio?",
        why_it_matters="Changes property taxes",
        default_used="1.0",
        affects=["property_tax"],
        status="open",
        answer=None,
    )
    deliverable = Deliverable(
        d_id="d-1",
        deal_ids=["deal-1"],
        kind=DeliverableKind.UW_MODEL,
        version=2,
        status="conditional",
        path="deliverables/model-v2.xlsx",
        gate_results=[GateResult(passed=True, failures=[], metrics={})],
        depends_on=[calc.calc_id],
        edited_by_user=True,
        parent_version=1,
    )
    task = Task(
        task_id="task-1",
        user_id="user-1",
        firm_id="firm-1",
        deal_ids=["deal-1", "deal-2"],
        request="Compare the two acquisitions",
        requested=[DeliverableKind.DEAL_COMPARISON],
        created_at=datetime(2026, 10, 4, tzinfo=UTC),
    )
    event = AgentEvent(
        event_id="01K6Q0ANWJ53A4KTHD3F48AV99",
        task_id=task.task_id,
        seq=None,
        origin=("box-1", 0, 1),
        ts=task.created_at,
        source="agent",
        kind="question",
        cause_id=None,
        release_id="release-1",
        runner="codex",
        payload=question.model_dump(mode="json"),
    )

    assert deliverable.edited_by_user and deliverable.deal_ids == ["deal-1"]
    assert task.deal_ids == ["deal-1", "deal-2"]
    assert event.seq is None and event.origin == ("box-1", 0, 1)
    assert assumption.set_by == "agent"


def test_t010_ac1_models_reject_unknown_fields_and_invalid_versions() -> None:
    with pytest.raises(ValidationError):
        Provenance(doc_id="om", unexpected="not allowed")
    with pytest.raises(ValidationError):
        Fact(
            fact_id="f",
            deal_id="d",
            key="noi",
            value=Decimal("1"),
            claim_type=ClaimType.VERIFIED_FACT,
            provenance=[],
            known_at=datetime.now(UTC),
            version=0,
        )


def test_t010_ac1_agent_event_has_the_full_kind_and_source_vocabulary() -> None:
    assert AgentEvent.SOURCES == (
        "agent",
        "extractor",
        "tool",
        "gate",
        "user",
        "system",
    )
    assert AgentEvent.KINDS == (
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


def test_t010_ac2_deliverable_kind_includes_required_analyses() -> None:
    assert DeliverableKind.RENT_COMP_ANALYSIS.value == "rent_comp_analysis"
    assert DeliverableKind.DEBT_QUOTE_SUMMARY.value == "debt_quote_summary"


@given(facts)
def test_t010_ac3_fact_json_round_trip(fact: Fact) -> None:
    restored = Fact.model_validate_json(fact.model_dump_json())
    assert restored == fact


@pytest.mark.parametrize("value", [date(2026, 1, 2), "00123", Decimal("1.20"), True])
def test_t010_ac3_fact_value_types_survive_json(value: Decimal | str | date | bool) -> None:
    fact = Fact(
        fact_id="f",
        deal_id="d",
        key="k",
        value=value,
        claim_type=ClaimType.VERIFIED_FACT,
        provenance=[],
        known_at=datetime(2026, 10, 4, tzinfo=UTC),
        version=1,
    )
    restored = Fact.model_validate_json(fact.model_dump_json())
    assert restored.value == value
    assert type(restored.value) is type(value)


@pytest.mark.parametrize(
    "value",
    [
        {"type": "other", "value": "1"},
        {"type": "date", "value": "not-a-date"},
        {"type": "decimal", "value": "not-a-number"},
        {"type": "decimal", "value": "NaN"},
        {"type": "decimal", "value": "Infinity"},
        {"type": "decimal", "value": 1.2},
        {"type": "decimal", "value": "1.2", "unexpected": True},
        {},
    ],
)
def test_t010_ac3_malformed_value_tags_are_rejected(value: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Fact.model_validate(
            {
                "fact_id": "f",
                "deal_id": "d",
                "key": "k",
                "value": value,
                "claim_type": "verified_fact",
                "provenance": [],
                "known_at": "2026-10-04T00:00:00Z",
                "version": 1,
            }
        )


def test_t010_ac3_assumption_values_round_trip() -> None:
    assumption = Assumption(
        key="completion",
        value=date(2026, 10, 4),
        low="00123",
        high=Decimal("1.20"),
        rationale="Explicit mixed-type boundary test",
        sources=[],
        is_proxy=True,
        as_of=date(2026, 10, 4),
        set_by="agent",
    )
    assert Assumption.model_validate_json(assumption.model_dump_json()) == assumption


def test_t010_ac3_json_schemas_describe_tagged_values() -> None:
    for mode in ("validation", "serialization"):
        schema = Fact.model_json_schema(mode=mode)
        assert schema["$defs"]["DateValueJson"]["properties"]["type"]["const"] == "date"
        assert schema["$defs"]["DecimalValueJson"]["properties"]["type"]["const"] == "decimal"


@given(calc_results)
def test_t010_ac3_calc_result_json_round_trip(calc: CalcResult) -> None:
    assert CalcResult.model_validate_json(calc.model_dump_json()) == calc


@given(agent_events)
def test_t010_ac3_agent_event_json_round_trip(event: AgentEvent) -> None:
    assert AgentEvent.model_validate_json(event.model_dump_json()) == event
