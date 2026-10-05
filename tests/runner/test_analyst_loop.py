"""Synthetic controller tests, not recordings or evidence of analyst quality."""

from copy import deepcopy
from pathlib import Path

import pytest
from tests.runner.test_tools_t032 import put

from cre_brain.analyst.brain import load_brain
from cre_brain.analyst.loop import AnalystLoop, InvestigationLimits
from cre_brain.knowledge import CacheStore, KnowledgeLibrary, SearchRequest

pytest_plugins = ("tests.runner.test_tools_t032",)

ROOT = Path(__file__).resolve().parents[2] / "brain"
PLAN = {
    "action": "plan",
    "plan": {
        "thesis_to_test": "Collections and recurring expenses support the in-place thesis",
        "investigations": [
            {
                "investigation": "Reconcile the operating evidence",
                "why_it_matters": "Reported income might not be collected cash",
                "disconfirming_evidence": "Unfunded capital work or weak collections",
                "skill": "multifamily",
            }
        ],
        "decision_dependencies": ["collections"],
    },
}


def candidate(recommendation="hold", *, changed=False, references=()):
    return {
        "action": "decide",
        "decision": {
            "recommendation": recommendation,
            "thesis": "The business plan requires corroboration",
            "reasons": [{"text": "Collections remain unverified", "references": references}],
            "conditions": ["Obtain independent collection evidence"],
            "unresolved": [] if recommendation == "proceed" else ["collections"],
            "change_log": ["Downgraded the recommendation pending evidence"] if changed else [],
        },
    }


REJECT = {
    "accepted": False,
    "findings": [
        {
            "finding_id": "collections-gap",
            "severity": "major",
            "issue": "Proposed performance lacks corroborated collections",
            "required_action": "Hold pending evidence or corroborate collections",
            "references": [],
        }
    ],
    "strongest_contrary_case": "Reported income may overstate recurring collected cash",
}
ACCEPT = {
    "accepted": True,
    "findings": [],
    "strongest_contrary_case": "A hold may delay a good acquisition, but the gap is material",
}


class StubClient:
    def __init__(self, responses, *, interrupt=None):
        self.responses = list(responses)
        self.calls = []
        self.interrupt = interrupt

    async def decide(self, **kwargs):
        self.calls.append(kwargs)
        role, response = self.responses.pop(0)
        assert role == kwargs["role"]
        if self.interrupt is not None:
            self.interrupt()
        return {"turn_id": kwargs["turn_id"], **deepcopy(response)}


def loop(tools, client, **kwargs):
    registry, _ = tools
    return AnalystLoop(brain=load_brain(ROOT), client=client, registry=registry, **kwargs)


@pytest.mark.asyncio
async def test_analyst_plans_reads_tool_evidence_and_revises_after_independent_review(tools):
    ref = put(tools, "noi", "1000")
    client = StubClient(
        [
            ("lead", PLAN),
            (
                "lead",
                {
                    "action": "tool",
                    "tool": {
                        "name": "facts_get",
                        "arguments": {"reference": ref},
                        "purpose": "Inspect the source and claim status",
                    },
                },
            ),
            ("lead", candidate("proceed", references=[ref])),
            ("verifier", REJECT),
            ("lead", candidate(changed=True, references=[ref])),
            ("verifier", ACCEPT),
        ]
    )
    outcome = await loop(tools, client).investigate(
        request="Test the acquisition thesis",
        evidence={"references": [ref]},
        run_id="case-a",
    )
    assert outcome.status == "reviewed_draft"
    assert outcome.decision.recommendation == "hold"
    assert outcome.publication == "not_authorized"
    assert [e.role for e in outcome.trace] == [
        "lead",
        "lead",
        "lead",
        "verifier",
        "lead",
        "verifier",
    ]
    assert client.calls[2]["context"]["observations"][-1]["response"]["status"] == "ok"
    assert client.calls[-2]["context"]["prior_reviews"][0]["accepted"] is False
    assert "finalize_deliverable" not in client.calls[0]["context"]["available_tools"]


@pytest.mark.asyncio
async def test_missing_evidence_question_does_not_invent_default_or_assumption(tools):
    question = {
        "action": "question",
        "question": {
            "question": "Provide independent collections evidence",
            "why_it_matters": "Recurring income is not yet corroborated",
            "decision_if_unanswered": "Hold the underwriting recommendation",
            "priority": "blocking",
            "evidence_needed": ["collection ledger"],
        },
    }
    client = StubClient([("lead", PLAN), ("lead", question)])
    outcome = await loop(tools, client).investigate(
        request="Investigate",
        evidence={},
        run_id="case-b",
    )
    assert outcome.status == "needs_user"
    assert outcome.decision is None
    assert len(outcome.questions) == 1
    with tools[0].transaction() as state:
        assert not any(e.payload.get("binding") == "assumption" for e in state.history())


@pytest.mark.asyncio
async def test_review_budget_cannot_self_approve_unresolved_objections(tools):
    client = StubClient(
        [
            ("lead", PLAN),
            ("lead", candidate()),
            ("verifier", REJECT),
            ("lead", candidate(changed=True)),
            ("verifier", REJECT),
        ]
    )
    outcome = await loop(tools, client).investigate(
        request="Investigate",
        evidence={},
        run_id="case-c",
    )
    assert outcome.status == "review_blocked"
    assert len(outcome.trace) == 5
    assert outcome.publication == "not_authorized"


@pytest.mark.asyncio
async def test_investigation_requires_plan_and_rejects_stale_turn(tools):
    for response in (candidate(), {**PLAN, "turn_id": "stale-turn"}):
        client = StubClient([("lead", response)])
        with pytest.raises(ValueError):
            await loop(tools, client).investigate(
                request="Investigate",
                evidence={},
                run_id="case-d",
            )


@pytest.mark.asyncio
async def test_model_cannot_publish_send_or_use_forged_numeric_references(tools):
    invalid_ref = {
        "kind": "fact",
        "record_id": "invented",
        "version": 1,
        "key": "noi",
        "unit": "USD",
    }
    responses = [
        {
            "action": "tool",
            "tool": {
                "name": "finalize_deliverable",
                "arguments": {},
                "purpose": "Publish",
            },
        },
        candidate(references=[invalid_ref]),
    ]
    for response in responses:
        client = StubClient([("lead", PLAN), ("lead", response)])
        with pytest.raises(ValueError):
            await loop(tools, client).investigate(
                request="Investigate",
                evidence={},
                run_id="case-e",
            )


@pytest.mark.asyncio
async def test_step_limit_returns_incomplete_not_reviewed_result(tools):
    client = StubClient([("lead", PLAN), ("lead", PLAN)])
    outcome = await loop(
        tools,
        client,
        limits=InvestigationLimits(max_steps=2),
    ).investigate(request="Investigate", evidence={}, run_id="case-f")
    assert outcome.status == "step_limit"
    assert outcome.decision is None


@pytest.mark.asyncio
async def test_extraction_requires_host_snapshot_and_scope_cannot_drift(tools):
    delegate = {
        "action": "delegate",
        "delegate": {
            "role": "extraction",
            "assignment": "Extract the rent roll",
            "required_evidence": ["host quarantined source"],
        },
    }
    client = StubClient(
        [("lead", PLAN), ("lead", delegate), ("lead", candidate()), ("verifier", ACCEPT)]
    )
    outcome = await loop(tools, client).investigate(
        request="Investigate",
        evidence={},
        run_id="case-g",
    )
    assert outcome.status == "reviewed_draft"
    assert all(c["role"] != "extraction" for c in client.calls)
    assert client.calls[2]["context"]["observations"][-1]["status"] == "unavailable"

    controller = loop(tools, StubClient([("lead", PLAN)]))
    controller.client.interrupt = lambda: setattr(
        controller.registry,
        "context",
        controller.registry.context.model_copy(update={"deal_id": "other"}),
    )
    with pytest.raises(ValueError, match="scope changed"):
        await controller.investigate(request="Investigate", evidence={}, run_id="case-h")


@pytest.mark.asyncio
async def test_research_carries_canonical_metadata_to_lead_without_promoting_facts(
    tools, public_probe_path
):
    tools[0].knowledge_provider = KnowledgeLibrary(
        cache=CacheStore(public_probe_path / "public-knowledge")
    )
    assignment = {
        "action": "delegate",
        "delegate": {
            "role": "research",
            "assignment": "Commercial Real Estate Lending",
            "required_evidence": ["Canonical public guidance"],
        },
    }
    research = {
        "role": "research",
        "observations": [{"text": "Metadata identifies lender guidance"}],
        "conflicts": [],
        "missing_evidence": ["Cached passage"],
        "source_ids": [
            "mfuv-occ-cre-lending-2022",
        ],
        "limitations": ["Metadata only; no pages inspected"],
    }
    citation = next(
        hit.citation.model_dump(mode="json")
        for hit in tools[0]
        .knowledge_provider.search(SearchRequest(query=assignment["delegate"]["assignment"]))
        .hits
        if hit.citation.resource_id == research["source_ids"][0]
    )
    research["citations"] = [citation]
    client = StubClient(
        [
            ("lead", PLAN),
            ("lead", assignment),
            ("research", research),
            ("lead", candidate()),
            ("verifier", ACCEPT),
        ]
    )
    outcome = await loop(tools, client).investigate(
        request="Research the decision",
        evidence={},
        run_id="case-research",
    )
    assert outcome.status == "reviewed_draft"
    knowledge = client.calls[3]["context"]["observations"][-2]["public_knowledge"]
    assert knowledge["status"] == "ok"
    assert knowledge["data"]["scope"] == "global_public"
    assert all(hit["text"] is None for hit in knowledge["data"]["hits"])
    assert all(
        hit["evidence_role"] == "public_reference_not_deal_fact"
        for hit in knowledge["data"]["hits"]
    )
    with tools[0].transaction() as state:
        assert not any(e.payload.get("binding") == "fact" for e in state.history())

    forged = {**research, "source_ids": ["invented-book"]}
    with pytest.raises(ValueError, match="invent citations"):
        await loop(
            tools,
            StubClient(
                [
                    ("lead", PLAN),
                    ("lead", assignment),
                    ("research", forged),
                ]
            ),
        ).investigate(request="Research", evidence={}, run_id="case-forged-research")
    changed_page = {**research, "citations": [{**citation, "page": 999}]}
    with pytest.raises(ValueError, match="invent citations"):
        await loop(
            tools,
            StubClient([("lead", PLAN), ("lead", assignment), ("research", changed_page)]),
        ).investigate(request="Research", evidence={}, run_id="case-forged-page")
