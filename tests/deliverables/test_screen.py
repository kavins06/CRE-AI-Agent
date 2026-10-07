"""Public synthetic plumbing only; no eval answers or operational quality claims."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine

from cre_brain.config import load
from cre_brain.domain import ClaimType, Deliverable, Fact, Provenance
from cre_brain.domain.base import TenantScope
from cre_brain.gates import GateService, TrustedInputs
from cre_brain.runner.policy import HostContext
from cre_brain.runner.tools.contracts import FactAnchor, Reference
from cre_brain.runner.tools.registry import ToolRegistry
from cre_brain.state.events import EventStore
from cre_brain.state.schema import metadata
from cre_brain.state.store import SqlVersionedStore


class Inputs:
    def __init__(self):
        self.facts = {}
        self.artifacts = {}

    def fact(self, context, identity):
        return self.facts.get(identity)

    def artifact(self, context, identity):
        return self.artifacts.get((context.task_id, context.deal_id, context.release_id, identity))

    def template(self, context, identity):
        return None

    def rule_policy(self, context, table):
        return None


@pytest.fixture
def screen_env(tmp_path):
    from cre_brain.deliverables.screen import Document, ScreenInputs, ScreenService
    from cre_brain.finance.risk import RiskPolicy
    from cre_brain.rules.models import BuyBoxPolicy

    engine = create_engine(f"sqlite:///{tmp_path / 'state.db'}")
    metadata.create_all(engine)
    context = HostContext(
        scope=TenantScope(user_id="synthetic-user", firm_id="synthetic-firm"),
        task_id="synthetic-task",
        deal_id="deal-0001",
        role="lead",
        session_id="host-session",
        release_id="synthetic-release",
        started_at=datetime.now(UTC),
    )
    inputs = Inputs()
    authority = TrustedInputs()
    settings = load(apply_environment=False)
    gate = GateService(
        engine,
        scope=context.scope,
        settings=settings.gates,
        inputs=authority,
        scratch=tmp_path / "private",
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    risk = RiskPolicy(
        policy_id="synthetic-policy",
        version="test-v1",
        source_ids=("firm-policy",),
        min_occupancy=Decimal("0.90"),
        min_dscr=Decimal("1.25"),
        occupancy_weight=Decimal("0.4"),
        dscr_weight=Decimal("0.6"),
    )
    registry = ToolRegistry(
        engine=engine,
        context=context,
        workspace=workspace,
        inputs=ScreenInputs(inputs),
        settings=settings,
        gates=gate,
        risk_policy=risk,
    )
    service = ScreenService(registry, authority, BuyBoxPolicy())
    docs = (
        Document(doc_id="om", filename="offering_memorandum.pdf"),
        Document(doc_id="rr", filename="rent_roll.csv"),
    )
    # Synthetic host intake pins descriptors independently of each run request.
    for document in (
        *docs,
        Document(doc_id="unclassified", filename="notes.pdf"),
        Document(doc_id="fixture-om", filename="offering_memo.csv"),
    ):
        registry.inputs.register_document(registry.context, document)
    refs = {}
    for key, value, unit, doc in (
        ("price", Decimal("10000000"), "USD", "om"),
        ("units", Decimal("100"), "count", "rr"),
        ("dscr", Decimal("1.30"), "ratio", "om"),
        ("occupancy", Decimal("0.88"), "ratio", "rr"),
        ("market_tier", "B", "text", "om"),
        ("noi", Decimal("-125.50"), "USD", "om"),
    ):
        fact = Fact(
            fact_id=key,
            deal_id=context.deal_id,
            key=key,
            value=value,
            unit=unit,
            claim_type=ClaimType.SELLER_ASSERTION,
            provenance=[Provenance(doc_id=doc, page=1)],
            known_at=datetime.now(UTC),
            version=1,
        )
        inputs.facts[key] = FactAnchor(fact=fact, authority="quarantine")
        assert registry.call("facts_put", {"anchor_id": key})["status"] == "ok"
        refs[key] = Reference(kind="fact", record_id=key, version=1, key=key, unit=unit)
    yield service, registry, inputs, authority, docs, refs
    engine.dispose()


def test_t038_ac1_screen_canonical_headlines_policy_risk_and_memo(screen_env):
    service, registry, inputs, _, docs, refs = screen_env
    run = service.run(documents=docs, headlines=refs, run_id="run-one")
    assert run.recommendation == "GO"
    assert run.risk.outputs == {"risk_score": Decimal("0.4")}
    assert run.risk.inputs["occupancy:0"] == "occupancy"
    assert run.risk.code_version
    assert "Seller assertion" in run.markdown
    assert "noi USD -125.50" in run.markdown
    assert run.json_memo == {"markdown": run.markdown}
    for identity in run.deliverable_ids:
        response = registry.call("finalize_deliverable", {"deliverable_id": identity})
        assert response["status"] == "ok", response
    assert all(registry.inputs.artifact(registry.context, d).sha256 for d in run.deliverable_ids)


def test_t038_ac2_screen_skill_and_real_gate_finalize(screen_env):
    from pathlib import Path

    service, registry, _, _, docs, refs = screen_env
    assert "SELLER_ASSERTION" in Path("brain/skills/screen/SKILL.md").read_text()
    run = service.run(documents=docs, headlines=refs, run_id="run-two")
    assert all(
        registry.call("finalize_deliverable", {"deliverable_id": d})["status"] == "ok"
        for d in run.deliverable_ids
    )


def test_t038_ac3_screen_measured_latency_in_event_store(screen_env):
    from cre_brain.state.events import EventStore

    service, registry, _, _, docs, refs = screen_env
    run = service.run(documents=docs, headlines=refs, run_id="run-time")
    assert run.elapsed_ns > 0
    events = EventStore(registry.engine).list(
        registry.context.task_id, scope=registry.context.scope
    )
    measurements = [e for e in events if e.payload.get("screen_run_id") == "run-time"]
    assert len(measurements) == 1
    assert measurements[0].payload["elapsed_ns"] == run.elapsed_ns
    assert measurements[0].release_id == registry.context.release_id


@pytest.mark.parametrize(
    "filename,kind",
    [
        ("offering-memorandum.pdf", "om"),
        ("rent_roll.csv", "rent_roll"),
        ("t-12.xlsx", "t12"),
        ("lease.pdf", "lease"),
        ("notes.pdf", "unknown"),
        ("om_rent_roll.pdf", "ambiguous"),
        ("om.exe", "unsupported"),
        ("rentroller.csv", "unknown"),
    ],
)
def test_t038_ac1_screen_rules_first_classification(filename, kind):
    from cre_brain.deliverables.screen import Document, RuleDecisionModel

    result = RuleDecisionModel().classify(Document(doc_id="source", filename=filename))
    assert result.kind == kind
    assert result.method == "rules"


@pytest.mark.parametrize("missing", ["price", "units", "occupancy", "dscr", "market_tier"])
def test_t038_ac1_screen_missing_evidence_unknown_and_scoped_questions(screen_env, missing):
    from cre_brain.domain import Question
    from cre_brain.state.store import SqlVersionedStore

    service, registry, _, _, docs, refs = screen_env
    del refs[missing]
    run = service.run(documents=docs, headlines=refs, run_id="missing")
    assert run.recommendation == "UNKNOWN"
    assert run.risk is None
    assert missing.replace("_", " ") + ": unknown" in run.markdown
    assert run.questions
    with registry.transaction() as state:
        questions = state.all_current(Question)
    assert questions
    assert all(
        q.task_id == registry.context.task_id
        and q.deal_id == registry.context.deal_id
        and q.default_used == "unknown; no default"
        for q in questions
    )
    for identity in run.deliverable_ids:
        assert (
            registry.call("finalize_deliverable", {"deliverable_id": identity})["status"]
            == "refused"
        )
        assert (
            SqlVersionedStore(registry.engine, Deliverable)
            .get(identity, scope=registry.context.scope)
            .status
            == "draft"
        )


def test_t038_ac1_screen_unknown_document_and_missing_policy_refuse_release(screen_env):
    from cre_brain.deliverables.screen import Document

    service, registry, _, _, docs, refs = screen_env
    registry.risk_policy = None
    run = service.run(
        documents=(*docs, Document(doc_id="unclassified", filename="notes.pdf")),
        headlines=refs,
        run_id="unknown-doc",
    )
    assert run.recommendation == "UNKNOWN"
    assert run.risk is None
    assert any("classification" in q for q in run.questions)
    assert any("risk policy" in q for q in run.questions)
    assert (
        registry.call("finalize_deliverable", {"deliverable_id": run.deliverable_ids[0]})["status"]
        == "refused"
    )


@pytest.mark.parametrize(
    "corruption",
    [
        "missing",
        "version",
        "unit",
        "string",
        "anchor",
        "deal",
        "claim",
        "reference-only",
        "future",
        "duplicate",
    ],
)
def test_t038_ac1_screen_bad_or_forged_headline_refused(screen_env, corruption):
    from datetime import timedelta

    from cre_brain.runner.policy import Refusal

    service, registry, inputs, _, docs, refs = screen_env
    if corruption in {"missing", "version", "unit"}:
        change = {
            "missing": {"record_id": "absent"},
            "version": {"version": 2},
            "unit": {"unit": "ratio"},
        }
        refs["price"] = refs["price"].model_copy(update=change[corruption])
    else:
        old = inputs.facts["price"].fact
        updates = {"version": 2}
        if corruption == "string":
            updates["value"] = "10000000"
        if corruption == "anchor":
            updates["provenance"] = [Provenance(doc_id="om")]
        if corruption == "deal":
            updates["deal_id"] = "other-deal"
        if corruption == "claim":
            updates["claim_type"] = ClaimType.VERIFIED_FACT
        if corruption == "reference-only":
            updates["claim_type"] = ClaimType.INTERPRETATION
        if corruption == "future":
            updates["known_at"] = datetime.now(UTC) + timedelta(days=2)
        if corruption == "duplicate":
            with registry.transaction() as state:
                state.append(old.model_copy(update={"fact_id": "duplicate"}))
        else:
            # Direct canonical mutations have no new authentic T032 binding.
            with registry.transaction() as state:
                state.append(old.model_copy(update=updates))
            refs["price"] = refs["price"].model_copy(update={"version": 2})
    with pytest.raises((Refusal, ValueError)):
        service.run(documents=docs, headlines=refs, run_id="bad-evidence")


def test_t038_ac1_screen_cross_tenant_cannot_consume_facts(screen_env):
    from cre_brain.runner.policy import Refusal
    from cre_brain.runner.tools.evidence import screen_fact

    _, registry, _, _, _, refs = screen_env
    context = registry.context.model_copy(
        update={"scope": TenantScope(user_id="other-user", firm_id="other-firm")}
    )
    other = registry.clone(context=context)
    with other.transaction() as state, pytest.raises(Refusal):
        screen_fact(state, refs["price"])


def test_t038_ac1_screen_no_go_real_buy_box_and_claims_unchanged(screen_env):
    from cre_brain.deliverables.screen import ScreenService
    from cre_brain.rules.models import BuyBoxPolicy
    from cre_brain.state.store import SqlVersionedStore

    _, registry, _, authority, docs, refs = screen_env
    service = ScreenService(registry, authority, BuyBoxPolicy(max_price=Decimal("5000000")))
    run = service.run(documents=docs, headlines=refs, run_id="no-go")
    assert run.recommendation == "NO_GO"
    for identity in run.deliverable_ids:
        result = registry.call("finalize_deliverable", {"deliverable_id": identity})
        assert result["status"] == "ok", result
    assert (
        SqlVersionedStore(registry.engine, Fact)
        .get("price", scope=registry.context.scope)
        .claim_type
        == ClaimType.SELLER_ASSERTION
    )


@pytest.mark.parametrize("mutation", ["markdown", "json", "claim", "number", "gate"])
def test_t038_ac2_screen_artifact_mutation_and_forged_gate_refused(screen_env, mutation):
    from pathlib import Path

    from cre_brain.domain import Deliverable, GateResult
    from cre_brain.state.store import SqlVersionedStore

    service, registry, _, _, docs, refs = screen_env
    run = service.run(documents=docs, headlines=refs, run_id="mutation")
    identity = run.deliverable_ids[0]
    artifact = registry.inputs.artifact(registry.context, identity)
    if mutation == "gate":
        with registry.transaction() as state:
            draft = state.current(Deliverable, identity)
            state.append(
                draft.model_copy(
                    update={
                        "version": 2,
                        "status": "final",
                        "parent_version": 1,
                        "gate_results": [GateResult(passed=True, failures=[], metrics={})] * 3,
                    }
                )
            )
    else:
        path = (
            Path(artifact.deliverable.path) if mutation != "json" else artifact.companions[0].path
        )
        text = path.read_text()
        if mutation == "claim":
            text = text.replace("Seller assertion", "Verified fact")
        elif mutation == "number":
            text = text.replace("-125.50", "125.50")
        else:
            text += "forged"
        path.write_text(text)
    assert (
        registry.call("finalize_deliverable", {"deliverable_id": identity})["status"] == "refused"
    )
    assert not any(
        e.kind == "deliverable"
        for e in EventStore(registry.engine).list(
            registry.context.task_id, scope=registry.context.scope
        )
    )
    if mutation != "gate":
        assert (
            SqlVersionedStore(registry.engine, Deliverable)
            .get(identity, scope=registry.context.scope)
            .status
            == "draft"
        )


def test_t038_ac2_screen_gate_detects_rehashed_json_markdown_mismatch(screen_env):
    import hashlib
    import json

    service, registry, _, authority, docs, refs = screen_env
    run = service.run(documents=docs, headlines=refs, run_id="mismatch")
    artifact = registry.inputs.artifact(registry.context, run.deliverable_ids[0])
    d = artifact.deliverable
    plan = authority.plan(registry.context.scope, d)
    other = plan.memo_pair.json_path
    changed = json.dumps({"markdown": run.markdown.replace("GO", "NO_GO")}).encode()
    other.write_bytes(changed)
    plan = plan.model_copy(
        update={
            "memo_pair": plan.memo_pair.model_copy(
                update={"json_sha256": hashlib.sha256(changed).hexdigest()}
            )
        }
    )
    authority.put_plan(registry.context.scope, d, plan)
    # Even rehashing a mismatched companion at the host boundary cannot bypass equivalence.
    assert not registry.gates.check("number_provenance", d).passed


def test_t038_ac1_screen_risk_determinism_reproduction_and_forged_calc(screen_env):
    from decimal import localcontext

    from cre_brain.gates.authority import reproduce

    service, registry, _, authority, docs, refs = screen_env
    first = service.run(documents=docs, headlines=refs, run_id="risk-one")
    with localcontext() as ctx:
        ctx.prec = 2
        second = service.run(documents=docs, headlines=refs, run_id="risk-two")
    assert first.risk == second.risk
    recipe = authority.recipe(registry.context.scope, registry.context.deal_id, first.risk.calc_id)
    assert reproduce(recipe) == first.risk
    with registry.transaction() as state:
        state.append(first.risk.model_copy(update={"outputs": {"risk_score": Decimal("0")}}))
    assert (
        registry.call("finalize_deliverable", {"deliverable_id": first.deliverable_ids[0]})[
            "status"
        ]
        == "refused"
    )


@pytest.mark.parametrize("policy_change", ["weight", "no-source", "threshold"])
def test_t038_ac1_screen_risk_policy_requires_bounded_versioned_provenance(
    screen_env, policy_change
):
    from cre_brain.finance.risk import RiskPolicy

    _, registry, _, _, _, _ = screen_env
    values = registry.risk_policy.model_dump()
    values.update(
        {
            "weight": {"dscr_weight": Decimal("0.5")},
            "no-source": {"source_ids": ()},
            "threshold": {"min_occupancy": Decimal("1.1")},
        }[policy_change]
    )
    with pytest.raises(ValueError):
        RiskPolicy.model_validate(values)


def test_t038_ac1_screen_no_arbitrary_calculators_or_caller_policy(screen_env):
    _, registry, _, _, _, refs = screen_env
    args = {key: refs[key].model_dump(mode="json") for key in ("occupancy", "dscr")}
    assert registry.call("finance_run", {"fn": "__import__", "args": args})["status"] == "refused"
    assert (
        registry.call("finance_run", {"fn": "risk_score", "args": args, "policy": {}})["status"]
        == "refused"
    )
    assert (
        registry.call(
            "finance_run", {"fn": "risk_score", "args": {**args, "policy": args["dscr"]}}
        )["status"]
        == "refused"
    )
    registry.risk_policy = None
    assert registry.call("finance_run", {"fn": "risk_score", "args": args})["status"] == "refused"


def test_t038_ac3_screen_latency_on_failure_and_run_identity(screen_env):
    from cre_brain.runner.policy import Refusal
    from cre_brain.state.events import EventStore

    service, registry, _, _, docs, refs = screen_env
    refs["price"] = refs["price"].model_copy(update={"record_id": "absent"})
    with pytest.raises(Refusal):
        service.run(documents=docs, headlines=refs, run_id="failed")
    measurements = [
        e
        for e in EventStore(registry.engine).list(
            registry.context.task_id, scope=registry.context.scope
        )
        if e.payload.get("screen_run_id") == "failed"
    ]
    assert len(measurements) == 1
    assert measurements[0].payload["outcome"] == "refused"
    assert measurements[0].payload["elapsed_ns"] > 0
    with pytest.raises(Refusal, match="new SCREEN run"):
        service.run(documents=docs, headlines=refs, run_id="failed")


@pytest.mark.asyncio
async def test_t038_ac2_screen_generator_canonical_facts_record_and_fake_replay(
    screen_env, tmp_path
):
    import csv
    import io
    import json
    import re
    from pathlib import Path

    from evals.generator.models import DefaultPriors
    from evals.generator.render import render_om, render_rent_roll
    from evals.generator.sampler import sample_deal
    from pypdf import PdfReader
    from tests.runner.test_codex_t033 import BufferedProvider, Streaming, collect, raw

    from cre_brain.deliverables.screen import Document
    from cre_brain.runner.codex import CodexRunner
    from cre_brain.runner.fake import FakeRunner, RegistryReplayAdapter, ReplayError
    from cre_brain.runner.record import record_segment
    from cre_brain.runner.segment import SegmentSpec, Workspace
    from cre_brain.sandbox.base import Box

    service, registry, inputs, _, _, refs = screen_env
    # Public developer generator only. No batch/gold/truth/score artifact is read or produced.
    public_deal = sample_deal(
        "t038-public-document-plumbing", priors=DefaultPriors(min_units=80, max_units=80)
    )
    assert public_deal.deal_id == registry.context.deal_id
    om_path, rr_path = tmp_path / "offering_memorandum.pdf", tmp_path / "rent_roll.csv"
    render_om(public_deal, om_path)
    render_rent_roll(public_deal, rr_path, layout="yardi")
    om_text = PdfReader(om_path).pages[0].extract_text()
    price = Decimal(re.search(r"Asking price \(USD\): ([0-9.]+)", om_text)[1])
    units = Decimal(re.search(r"Units: ([0-9]+)", om_text)[1])
    rows = list(csv.reader(io.StringIO(rr_path.read_text())))
    body = rows[3:]
    assert units == Decimal(len(body)) == Decimal(80)
    occupancy = Decimal(sum(row[2] == "Occupied" for row in body)) / Decimal(len(body))
    fixture_path = tmp_path / "offering_memo.csv"
    fixture_path.write_text(
        "key,value,unit\ndscr,1.30,ratio\nmarket_tier,B,text\nnoi,-125.50,USD\n"
    )
    for key, old_ref in tuple(refs.items()):
        old = inputs.facts[key].fact
        if key in {"price", "units", "occupancy"}:
            value = {"price": price, "units": units, "occupancy": occupancy}[key]
            provenance = (
                [Provenance(doc_id="om", page=1)]
                if key != "occupancy"
                else [Provenance(doc_id="rr", sheet="CSV", cell="C4:C83")]
            )
        else:
            value = old.value
            cell = {"dscr": "B2", "market_tier": "B3", "noi": "B4"}[key]
            provenance = [Provenance(doc_id="fixture-om", sheet="CSV", cell=cell)]
        fact = old.model_copy(update={"value": value, "provenance": provenance, "version": 2})
        inputs.facts[key] = FactAnchor(fact=fact, authority="quarantine")
        assert (
            registry.call("facts_put", {"anchor_id": key}, request_id="new-" + key)["status"]
            == "ok"
        )
        refs[key] = old_ref.model_copy(update={"version": 2})
    docs = (
        Document(doc_id="om", filename=om_path.name),
        Document(doc_id="rr", filename=rr_path.name),
        Document(doc_id="fixture-om", filename=fixture_path.name),
    )
    run = service.run(documents=docs, headlines=refs, run_id="generator-record")
    assert run.recommendation == "GO"
    lines = raw(
        {"type": "thread.started", "thread_id": "synthetic-provider-session"},
        {"type": "turn.started"},
        *(
            {
                "type": "item.completed",
                "item": {
                    "id": "synthetic-call-" + str(index),
                    "type": "mcp_tool_call",
                    "server": "cre",
                    "tool": "finalize_deliverable",
                    "arguments": {"deliverable_id": identity},
                    "result": {"content": [{"type": "text", "text": json.dumps({"status": "ok"})}]},
                    "status": "completed",
                },
            }
            for index, identity in enumerate(run.deliverable_ids)
        ),
        {"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}},
    )
    provider = BufferedProvider()  # Cannot exec, create a container or reach a model.
    runtime = Streaming(provider, registry, lines)
    runner = CodexRunner(
        provider=provider,
        runtime=runtime,
        registry=registry,
        brain_root=Path("brain").absolute(),
        model_provider="configured-provider",
    )
    ws = Workspace(
        box=Box(user_id=registry.context.scope.user_id, box_id="synthetic-screen-box"),
        scope=registry.context.scope,
    )
    seg = SegmentSpec(
        task_id=registry.context.task_id,
        deal_id=registry.context.deal_id,
        release_id=registry.context.release_id,
        segment_no=0,
        prompt="Synthetic SCREEN tool plumbing",
        max_turns=3,
        max_tokens=100,
    )
    recording = tmp_path / "synthetic-screen-recording"
    manifest = await record_segment(
        runner, seg, ws, registry.context, recording, expected_deliverables=run.deliverable_ids
    )
    assert manifest.evidence == "synthetic_plumbing_only"
    # Recording does not bless the provider's synthetic results. Replay executes the real tools.
    assert all(
        SqlVersionedStore(registry.engine, Deliverable).get(d, scope=ws.scope).status == "draft"
        for d in run.deliverable_ids
    )
    fake = FakeRunner(recording, registry=registry)
    result = await collect(fake, seg.model_copy(update={"segment_no": 1}), ws, registry.context)
    assert result[-1].payload["plumbing_only"] is True
    RegistryReplayAdapter(registry).assert_final(run.deliverable_ids)
    releases = [
        e
        for e in EventStore(registry.engine).list(
            registry.context.task_id, scope=ws.scope, limit=1000
        )
        if e.kind == "deliverable"
    ]
    assert len(releases) == 2
    for identity in run.deliverable_ids:
        current = SqlVersionedStore(registry.engine, Deliverable).get(identity, scope=ws.scope)
        artifact = registry.inputs.artifact(registry.context, identity)
        assert current.status == "final" and current.parent_version == 1
        assert all(g.passed for g in current.gate_results)
        release = next(e for e in releases if e.payload["d_id"] == identity)
        assert release.runner == "tools" and release.release_id == registry.context.release_id
        assert release.payload["sha256"] == artifact.sha256
        assert release.payload["companions"] == {str(c.path): c.sha256 for c in artifact.companions}
    assert ".agents/skills/screen/SKILL.md" in runtime.assets.files
    Path(
        registry.inputs.artifact(registry.context, run.deliverable_ids[1]).deliverable.path
    ).write_text("{}")
    with pytest.raises(ReplayError):
        RegistryReplayAdapter(registry).assert_final(run.deliverable_ids)


@pytest.mark.parametrize(
    "change", ["negative", "too-large", "fractional-units", "bad-anchor", "foreign-doc"]
)
def test_t038_ac1_screen_malformed_bound_sources_refused(screen_env, change):
    from cre_brain.runner.policy import Refusal

    service, registry, inputs, _, docs, refs = screen_env
    key = "units" if change == "fractional-units" else "occupancy"
    updates = {"version": 2}
    updates.update(
        {
            "negative": {"value": Decimal("-0.01")},
            "too-large": {"value": Decimal("1.01")},
            "fractional-units": {"value": Decimal("2.5")},
            "bad-anchor": {"provenance": [Provenance(doc_id="rr")]},
            "foreign-doc": {"provenance": [Provenance(doc_id="foreign", page=1)]},
        }[change]
    )
    inputs.facts[key] = FactAnchor(
        fact=inputs.facts[key].fact.model_copy(update=updates), authority="quarantine"
    )
    assert registry.call("facts_put", {"anchor_id": key}, request_id="bad-" + key)["status"] == "ok"
    refs[key] = refs[key].model_copy(update={"version": 2})
    with pytest.raises((Refusal, ValueError)):
        service.run(documents=docs, headlines=refs, run_id="malformed")


@pytest.mark.parametrize(
    "field,value",
    [("task_id", "other-task"), ("deal_id", "other-deal"), ("release_id", "other-release")],
)
def test_t038_ac2_screen_artifact_identity_separation(screen_env, field, value):
    service, registry, _, _, docs, refs = screen_env
    run = service.run(documents=docs, headlines=refs, run_id="identity")
    other = registry.clone(context=registry.context.model_copy(update={field: value}))
    assert (
        other.call("finalize_deliverable", {"deliverable_id": run.deliverable_ids[0]})["status"]
        == "refused"
    )


def test_t038_ac1_screen_bounds_and_duplicate_documents(screen_env):
    from cre_brain.deliverables.screen import Document
    from cre_brain.runner.policy import Refusal

    service, _, _, _, docs, refs = screen_env
    with pytest.raises(ValueError):
        Document(doc_id="om", filename="../raw.pdf")
    with pytest.raises(ValueError):
        service.run(documents=docs * 20, headlines=refs, run_id="too-many")
    with pytest.raises(Refusal):
        service.run(documents=docs * 2, headlines=refs, run_id="duplicates")


@pytest.mark.parametrize(
    "occupancy,dscr,expected",
    [
        ("0.90", "1.25", "0"),
        ("0.89", "1.25", "0.4"),
        ("0.90", "1.24", "0.6"),
        ("0.89", "1.24", "1"),
    ],
)
def test_t038_ac1_screen_exact_configured_risk_boundaries(screen_env, occupancy, dscr, expected):
    from cre_brain.finance.risk import RiskInput, risk_score

    _, registry, _, _, _, _ = screen_env
    source = RiskInput(
        input_id="host-risk-input",
        occupancy=Decimal(occupancy),
        dscr=Decimal(dscr),
        policy=registry.risk_policy,
    )
    result = risk_score(source, calc_id="boundary-calc", code_version="test-code")
    assert result.outputs["risk_score"] == Decimal(expected)


def test_t038_ac1_screen_period_metadata_does_not_invent_date_fact(screen_env):
    from datetime import date

    from cre_brain.domain.models import DateRange
    from cre_brain.runner.policy import Refusal

    service, registry, inputs, _, docs, refs = screen_env
    inputs.facts["price"] = FactAnchor(
        fact=inputs.facts["price"].fact.model_copy(
            update={"version": 2, "valid_time": DateRange(start=date(2020, 1, 1), end=None)}
        ),
        authority="quarantine",
    )
    assert registry.call("facts_put", {"anchor_id": "price"}, request_id="period")["status"] == "ok"
    refs["price"] = refs["price"].model_copy(update={"version": 2})
    with pytest.raises(Refusal, match="period"):
        service.run(documents=docs, headlines=refs, run_id="period")


def test_t038_ac2_screen_new_evidence_invalidates_memo_and_risk(screen_env):
    service, registry, inputs, _, docs, refs = screen_env
    first = service.run(documents=docs, headlines=refs, run_id="first-evidence")
    inputs.facts["occupancy"] = FactAnchor(
        fact=inputs.facts["occupancy"].fact.model_copy(
            update={"version": 2, "value": Decimal("0.95")}
        ),
        authority="quarantine",
    )
    assert (
        registry.call("facts_put", {"anchor_id": "occupancy"}, request_id="change")["status"]
        == "ok"
    )
    assert (
        registry.call("finalize_deliverable", {"deliverable_id": first.deliverable_ids[0]})[
            "status"
        ]
        == "refused"
    )
    refs["occupancy"] = refs["occupancy"].model_copy(update={"version": 2})
    second = service.run(documents=docs, headlines=refs, run_id="second-evidence")
    assert second.risk.outputs["risk_score"] == Decimal(0)
    assert second.risk.calc_id != first.risk.calc_id
    assert second.deliverable_ids != first.deliverable_ids
    assert (
        registry.call("finalize_deliverable", {"deliverable_id": second.deliverable_ids[0]})[
            "status"
        ]
        == "ok"
    )


def test_t038_ac1_screen_annual_rent_total_unit_and_provenance(screen_env):
    service, registry, inputs, _, docs, refs = screen_env
    fact = Fact(
        fact_id="gpr",
        deal_id=registry.context.deal_id,
        key="gpr",
        value=Decimal("1500000.00"),
        unit="USD/year",
        claim_type=ClaimType.SELLER_ASSERTION,
        provenance=[Provenance(doc_id="rr", sheet="CSV", cell="D104")],
        known_at=datetime.now(UTC),
        version=1,
    )
    inputs.facts["gpr"] = FactAnchor(fact=fact, authority="quarantine")
    assert registry.call("facts_put", {"anchor_id": "gpr"})["status"] == "ok"
    refs["gpr"] = Reference(kind="fact", record_id="gpr", version=1, key="gpr", unit="USD/year")
    run = service.run(documents=docs, headlines=refs, run_id="annual-rent")
    assert "1500000.00 USD/year" in run.markdown
    for identity in run.deliverable_ids:
        result = registry.call("finalize_deliverable", {"deliverable_id": identity})
        assert result["status"] == "ok", result


@pytest.mark.parametrize("sheet,cell", [("", ""), (" ", "\t"), ("CSV", " "), (" ", "C4")])
def test_t038_ac1_screen_blank_source_anchors_refused(screen_env, sheet, cell):
    from cre_brain.runner.policy import Refusal

    service, registry, inputs, _, docs, refs = screen_env
    inputs.facts["occupancy"] = FactAnchor(
        fact=inputs.facts["occupancy"].fact.model_copy(
            update={"version": 2, "provenance": [Provenance(doc_id="rr", sheet=sheet, cell=cell)]}
        ),
        authority="quarantine",
    )
    assert (
        registry.call("facts_put", {"anchor_id": "occupancy"}, request_id="blank")["status"] == "ok"
    )
    refs["occupancy"] = refs["occupancy"].model_copy(update={"version": 2})
    with pytest.raises(Refusal, match="anchors"):
        service.run(documents=docs, headlines=refs, run_id="blank-anchors")


@pytest.mark.parametrize("sheet,cell", [("", ""), (" ", "\t"), ("CSV", " "), (" ", "C4")])
def test_t038_ac2_screen_coverage_blank_source_anchors_refused(screen_env, sheet, cell):
    service, registry, _, authority, docs, refs = screen_env
    run = service.run(documents=docs, headlines=refs, run_id="coverage-blank")
    anchor = registry.inputs.artifact(registry.context, run.deliverable_ids[0])
    with registry.transaction() as state:
        fact = state.current(Fact, "occupancy")
        state.append(
            fact.model_copy(
                update={
                    "version": 2,
                    "provenance": [Provenance(doc_id="rr", sheet=sheet, cell=cell)],
                }
            )
        )
    plan = authority.plan(registry.context.scope, anchor.deliverable)
    fields = tuple(
        field.model_copy(
            update={
                "references": tuple(
                    ref.model_copy(update={"version": 2}) for ref in field.references
                )
            }
        )
        if field.name == "occupancy"
        else field
        for field in plan.coverage
    )
    authority.put_plan(
        registry.context.scope, anchor.deliverable, plan.model_copy(update={"coverage": fields})
    )
    result = registry.gates.check("coverage", anchor.deliverable)
    assert result.passed is False, result


@pytest.mark.parametrize("extension", ["md", "json"])
def test_t038_ac2_screen_companion_aba_uses_captured_pair(screen_env, monkeypatch, extension):
    service, registry, _, _, docs, refs = screen_env
    run = service.run(documents=docs, headlines=refs, run_id="aba-pair")
    identity = next(d for d in run.deliverable_ids if d.endswith(":" + extension))
    anchor = registry.inputs.artifact(registry.context, identity)
    companion = anchor.companions[0].path
    original = companion.read_bytes()
    checker = registry.gates.check_bytes

    def probe(name, deliverable, snapshot):
        if name != "number_provenance":
            return checker(name, deliverable, snapshot)
        companion.write_bytes(b"{}")
        try:
            return checker(name, deliverable, snapshot)
        finally:
            companion.write_bytes(original)

    monkeypatch.setattr(registry.gates, "check_bytes", probe)
    result = registry.call("finalize_deliverable", {"deliverable_id": identity})
    assert result["status"] == "ok", result


@pytest.mark.parametrize("window", ["deadline", "append", "event", "after-release"])
def test_t038_ac2_screen_publication_is_immutable_pair(screen_env, monkeypatch, window):
    import base64
    import json
    from pathlib import Path

    from cre_brain.runner.tools import files
    from cre_brain.runner.tools.state import ToolState

    service, registry, _, _, docs, refs = screen_env
    run = service.run(documents=docs, headlines=refs, run_id="publication")
    identity = run.deliverable_ids[0]
    anchor = registry.inputs.artifact(registry.context, identity)
    companion = anchor.companions[0].path
    expected = companion.read_bytes()
    expected_bodies = {
        anchor.deliverable.path: Path(anchor.deliverable.path).read_bytes(),
        str(companion): expected,
    }
    original_deadline = registry.deadline
    original_append = ToolState.append
    original_event = ToolState.event
    calls = 0

    def deadline(state):
        nonlocal calls
        original_deadline(state)
        calls += 1
        # The second deadline is the final one after the artifact recheck.
        if calls == 2 and window == "deadline":
            companion.write_bytes(b"{}")

    def append(state, record, **kwargs):
        if isinstance(record, Deliverable) and record.status == "final" and window == "append":
            companion.write_bytes(b"{}")
        return original_append(state, record, **kwargs)

    def event(state, kind, payload):
        if kind == "deliverable" and window == "event":
            companion.write_bytes(b"{}")
        return original_event(state, kind, payload)

    monkeypatch.setattr(registry, "deadline", deadline)
    monkeypatch.setattr(ToolState, "append", append)
    monkeypatch.setattr(ToolState, "event", event)
    result = registry.call("finalize_deliverable", {"deliverable_id": identity})
    if window == "after-release":
        assert result["status"] == "ok", result
        companion.write_bytes(b"{}")
    with registry.transaction() as state:
        releases = [e for e in state.history() if e.kind == "deliverable"]
        current = state.current(Deliverable, identity)
        ordinary = json.dumps([event.model_dump(mode="json") for event in state.history()])
    if result["status"] == "refused":
        assert not releases
        assert current.status == "draft"
    else:
        assert result["status"] == "ok", result
        for body in expected_bodies.values():
            assert body.decode() not in ordinary
            assert json.dumps(body.decode())[1:-1] not in ordinary
            for encoded in (
                base64.b64encode(body).decode(),
                base64.urlsafe_b64encode(body).decode(),
                base64.b85encode(body).decode(),
                body.hex(),
            ):
                assert encoded not in ordinary
        references = releases[0].payload["publication"]
        assert all(set(item) == {"publication_id", "path", "sha256"} for item in references)
        published = {
            item["path"]: registry.published_artifact(identity, item["publication_id"])
            for item in references
        }
        assert published == expected_bodies
        assert published[str(companion)] == expected
        assert {path: files.digest(data) for path, data in published.items()} == {
            anchor.deliverable.path: anchor.sha256,
            **{str(c.path): c.sha256 for c in anchor.companions},
        }
        assert companion.read_bytes() == b"{}"


def test_t038_ac1_screen_swapped_authenticated_filenames_refused(screen_env):
    from cre_brain.deliverables.screen import Document
    from cre_brain.runner.policy import Refusal

    service, _, _, _, docs, refs = screen_env
    swapped = tuple(
        Document(doc_id=d.doc_id, filename=docs[1 - i].filename) for i, d in enumerate(docs)
    )
    with pytest.raises(Refusal, match="document"):
        service.run(documents=swapped, headlines=refs, run_id="swapped")


def test_t038_ac1_screen_unregistered_document_refused(screen_env):
    from cre_brain.deliverables.screen import Document
    from cre_brain.runner.policy import Refusal

    service, _, _, _, docs, refs = screen_env
    with pytest.raises(Refusal, match="document"):
        service.run(
            documents=(*docs, Document(doc_id="unbound", filename="om.pdf")),
            headlines=refs,
            run_id="unbound",
        )


@pytest.mark.parametrize(
    "forgery", ["review-repro", "source", "runner", "release", "companions", "gates", "publication"]
)
def test_t038_ac2_screen_external_send_requires_trusted_release(screen_env, forgery):
    from pathlib import Path

    from tests.runner.test_tools_t032 import Gates

    from cre_brain.domain import DeliverableKind, GateResult
    from cre_brain.runner.policy import required_gates
    from cre_brain.runner.tools import files
    from cre_brain.runner.tools.contracts import Artifact, ArtifactCompanion
    from cre_brain.state.events import _append_locked

    _, registry, inputs, _, _, _ = screen_env
    registry.gates = Gates(registry.context.scope)
    root = registry.workspace / "deals" / registry.context.deal_id / "deliverables"
    root.mkdir(parents=True)
    path = root / "questions.md"
    path.write_text("Broker questions")
    companion = root / "questions.json"
    companion.write_text('{"markdown":"Broker questions"}')
    draft = Deliverable(
        d_id="questions",
        deal_ids=[registry.context.deal_id],
        kind=DeliverableKind.BROKER_QUESTIONS,
        version=1,
        status="draft",
        path=str(path),
        gate_results=[],
        depends_on=[],
    )
    anchor = Artifact(
        deliverable=draft,
        sha256=files.digest(path.read_bytes()),
        companions=(
            ArtifactCompanion(path=companion, sha256=files.digest(companion.read_bytes())),
        ),
    )
    inputs.artifacts[
        (
            registry.context.task_id,
            registry.context.deal_id,
            registry.context.release_id,
            draft.d_id,
        )
    ] = anchor
    with registry.transaction() as state:
        state.append(draft)
    assert registry.call("finalize_deliverable", {"deliverable_id": draft.d_id})["status"] == "ok"
    with registry.transaction() as state:
        release = next(e for e in state.history() if e.kind == "deliverable")
    # Reconstruct an independent forged final record, with no real release transition.
    new_id = "forged-questions"
    forged_draft = draft.model_copy(update={"d_id": new_id})
    inputs.artifacts[
        (registry.context.task_id, registry.context.deal_id, registry.context.release_id, new_id)
    ] = anchor.model_copy(update={"deliverable": forged_draft})
    payload = {**release.payload, "d_id": new_id}
    update = {}
    if forgery in {"source", "review-repro"}:
        update["source"] = "agent"
    if forgery in {"runner", "review-repro"}:
        update["runner"] = "codex"
    if forgery in {"release", "review-repro"}:
        update["release_id"] = "old-release"
    if forgery == "companions":
        payload["companions"] = {}
    if forgery == "publication":
        payload.pop("publication", None)
    results = [
        GateResult(passed=True, failures=[], metrics={}) for _ in required_gates(draft.kind, False)
    ]
    with registry.transaction() as state:
        state.append(forged_draft)
        state.append(
            forged_draft.model_copy(
                update={
                    "version": 2,
                    "parent_version": 1,
                    "status": "final",
                    "gate_results": [] if forgery in {"gates", "review-repro"} else results,
                }
            )
        )
        _append_locked(
            state.connection,
            release.model_copy(
                update={**update, "event_id": "forged-event", "seq": None, "payload": payload}
            ),
            registry.context.scope,
        )

    class Connector:
        scope = registry.context.scope
        allowed_recipients = frozenset({"host-recipient"})
        calls = []

        def send(self, **kwargs):
            self.calls.append(kwargs)
            return "receipt"

    connector = Connector()
    registry.connectors["email_brokers"] = connector
    registry.set_host_toggles(email_brokers="on")
    outbox = registry.call(
        "draft_external",
        {
            "kind": "email_brokers",
            "to": "host-recipient",
            "body": Path(draft.path).read_text(),
            "deliverable_id": new_id,
        },
    )
    assert outbox["status"] == "ok", outbox
    result = registry.call("send_external", {"draft_id": outbox["data"]["draft_id"]})
    assert result["status"] == "refused", result
    assert connector.calls == []


def test_t038_ac2_screen_finalize_cached_response_authenticates_release(screen_env):
    from cre_brain.domain import GateResult
    from cre_brain.runner.policy import required_gates
    from cre_brain.runner.tools import files
    from cre_brain.runner.tools.json_io import canonical

    service, registry, _, _, docs, refs = screen_env
    run = service.run(documents=docs, headlines=refs, run_id="cached-forgery")
    identity = run.deliverable_ids[0]
    arguments = {"deliverable_id": identity}
    with registry.transaction() as state:
        draft = state.current(Deliverable, identity)
        state.append(
            draft.model_copy(
                update={
                    "version": 2,
                    "parent_version": 1,
                    "status": "final",
                    "gate_results": [
                        GateResult(passed=True, failures=[], metrics={})
                        for _ in required_gates(draft.kind, False)
                    ],
                }
            )
        )
        state.event(
            "tool_result",
            {
                "request_id": "forged-cache",
                "body_hash": files.digest(
                    canonical({"name": "finalize_deliverable", "args": arguments}).encode()
                ),
                "response": {
                    "status": "ok",
                    "data": {"deliverable_id": identity, "version": 2, "status": "final"},
                },
            },
        )
    result = registry.call("finalize_deliverable", arguments, request_id="forged-cache")
    assert result["status"] == "refused", result


def test_t038_ac2_final_replay_snapshot_bytes_come_from_protected_store(screen_env, monkeypatch):
    from cre_brain.state import publications

    service, registry, _, _, docs, refs = screen_env
    run = service.run(documents=docs, headlines=refs, run_id="protected-snapshot")
    identity = run.deliverable_ids[0]
    assert registry.call("finalize_deliverable", {"deliverable_id": identity})["status"] == "ok"
    loaded = []
    original_load = publications.load_release

    def load(*args):
        result = original_load(*args)
        loaded.append(result)
        return result

    monkeypatch.setattr(publications, "load_release", load)
    with registry.transaction() as state:
        _, snapshot = registry.artifact_snapshot(state, identity, final_replay=True)
    assert loaded
    assert snapshot.data is loaded[0][1][0].body
    assert all(
        c.data is stored.body
        for c, stored in zip(snapshot.companions, loaded[0][1][1:], strict=True)
    )
