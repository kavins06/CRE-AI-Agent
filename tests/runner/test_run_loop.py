"""Public synthetic plumbing only: real preparse, extraction, tools, gates and publication.

Only model transport and host receipt verification use isolated synthetic adapters.
No transcript, runtime acceptance or analyst quality evidence is produced.
"""

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from cre_brain.config import load
from cre_brain.control.jobs import HostReceipt, JobStore
from cre_brain.deliverables.screen import Document, ScreenInputs, ScreenService
from cre_brain.domain import ClaimType, Deliverable, Fact, Provenance
from cre_brain.domain.base import TenantScope
from cre_brain.extraction.preparse import Preparser
from cre_brain.extraction.quarantine import Extractor
from cre_brain.extraction.schemas import Reconciliation, Selection, SourceDocument
from cre_brain.finance.risk import RiskPolicy
from cre_brain.gates import GateService, TrustedInputs
from cre_brain.rules.models import BuyBoxPolicy
from cre_brain.runner.codex import CodexRunner
from cre_brain.runner.orchestration.run import (
    NativeClaim,
    RunGateService,
    RunHost,
    RunInput,
    RunPlan,
    RunSession,
    SourcePin,
    configuration_digest,
    execute_run,
)
from cre_brain.runner.orchestration.stuck import StuckLimits
from cre_brain.runner.policy import HostContext
from cre_brain.runner.segment import SegmentSpec, Workspace
from cre_brain.runner.streaming import CancellationReceipt, RuntimeCapabilities
from cre_brain.runner.tools.contracts import FactAnchor, Reference
from cre_brain.runner.tools.json_io import canonical
from cre_brain.runner.tools.registry import ToolRegistry
from cre_brain.sandbox.base import Box
from cre_brain.state.schema import metadata


def frames(*events):
    return [canonical(event).encode() + b"\n" for event in events]


class Process:
    def __init__(self, lines, silent=False):
        self.lines, self.silent = lines, silent
        self.cancelled = False
        self.confirmed = True
        self.total = 2

    async def stdout(self):
        if self.silent:
            await asyncio.Event().wait()
        for line in self.lines:
            yield line

    async def wait(self):
        return 0

    async def cancel(self):
        self.cancelled = True
        return CancellationReceipt(confirmed=self.confirmed, total_tokens=self.total)


class Sources:
    def __init__(self):
        self.docs, self.facts = {}, {}

    def document(self, context, identity):
        return self.docs.get(identity)

    def fact(self, context, identity):
        return self.facts.get(identity)

    def artifact(self, context, identity):
        return None

    def template(self, context, identity):
        return None

    def rule_policy(self, context, identity):
        return None


class Provider:
    def __init__(self):
        self.created, self.destroyed = [], []

    async def create_extraction(self, user_id, image, parsed):
        box = Box(user_id=user_id, box_id="extract", kind="extractor")
        self.created.append(box)
        return box

    async def destroy(self, box):
        self.destroyed.append(box)

    async def exec(self, *args):
        raise AssertionError("Host execution forbidden")


class ExtractionTransport:
    def __init__(self, provider, source):
        self.provider, self.source = provider, source

    async def capabilities(self, box, bundle):
        from cre_brain.extraction.runtime import ExtractionCapabilities

        return ExtractionCapabilities(
            evidence="synthetic_plumbing_only",
            cli_version="synthetic",
            isolated=True,
            authenticated=True,
            configuration_verified=True,
            hard_caps=True,
            resume_supported=False,
            model_only_egress=True,
            no_mcp=True,
            single_document_readonly=True,
            bundle_sha256=bundle.sha256,
            parsed_sha256=bundle.parsed_sha256,
        )

    async def stage(self, box, bundle):
        pass

    async def start(self, box, request):
        cells = {c.cell_id: c for t in self.source.document.tables for c in t.cells}
        text = canonical(
            {
                "doc_type": self.source.doc_type,
                "observations": [
                    s.model_dump()
                    | {"quote": cells[s.anchor_id].text, "value": cells[s.anchor_id].text}
                    for s in self.source.required
                ],
            }
        )
        return Process(
            frames(
                {"type": "thread.started", "thread_id": "extract-session"},
                {"type": "turn.started"},
                {
                    "type": "item.completed",
                    "item": {"id": "m", "type": "agent_message", "text": text},
                },
                {"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}},
            )
        )


class LeadTransport:
    def __init__(self, provider, registry):
        self.provider, self.registry = provider, registry
        self.starts = 0
        self.process = Process(
            frames(
                {"type": "thread.started", "thread_id": "native-session"},
                {"type": "turn.started"},
                {
                    "type": "item.completed",
                    "item": {"id": "m", "type": "agent_message", "text": "Ready"},
                },
                {"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}},
            )
        )
        self.caps = RuntimeCapabilities(
            evidence="synthetic_plumbing_only",
            cli_version="synthetic",
            isolated=True,
            authenticated=True,
            configuration_verified=True,
            hard_caps=True,
            resume_supported=True,
        )

    async def capabilities(self, box):
        return self.caps

    async def stage(self, box, bundle):
        pass

    async def start(self, box, request):
        self.starts += 1
        return self.process


class HostEvidence:
    """Synthetic host evidence; it cannot claim genuine native/runtime verification."""

    def __init__(self, registry):
        self.registry = registry
        self.unknown = False
        self.nudges = []

    async def verify(self, job):
        if self.unknown:
            raise ValueError("Unknown synthetic outcome")
        with self.registry.transaction() as state:
            end = next(
                e
                for e in reversed(state.history())
                if e.runner == "codex" and e.kind == "segment_end"
            )
        return HostReceipt(
            identity=job.identity,
            receipt_id="synthetic-receipt",
            claim_revision=job.claim_revision,
            owner_id=job.owner_id,
            observed_at=datetime.now(UTC),
            outcome="completed" if end.payload["reason"] == "completed" else "stopped",
            session_id=end.payload["session_id"],
        )

    async def nudge(self, job):
        self.nudges.append(datetime.now(UTC))


@pytest.fixture
def environment(tmp_path):
    scope = TenantScope(user_id="synthetic-user", firm_id="synthetic-firm")
    context = HostContext(
        scope=scope,
        task_id="task",
        deal_id="deal",
        role="lead",
        session_id="host-session",
        release_id="release",
        started_at=datetime.now(UTC),
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'state.db'}")
    metadata.create_all(engine)
    for name in ("raw", "parsed", "workspace"):
        (tmp_path / name).mkdir()
    (tmp_path / "raw" / "rent_roll.csv").write_text(
        "rent\n100\n200\n300\n10000000\n100\n1.3\n0.95\nB\n"
    )
    preparser = Preparser(tmp_path / "raw", tmp_path / "parsed", scope)
    doc = preparser.parse("rent_roll.csv", doc_id="roll")
    cells = doc.tables[0].cells[1:4]
    source = SourceDocument(
        document=doc,
        parsed_sha256=hashlib.sha256(doc.model_dump_json().encode()).hexdigest(),
        deal_id="deal",
        doc_type="rent_roll",
        required=tuple(
            Selection(field=field, anchor_id=c.cell_id, anchor_kind="cell")
            for field, c in zip(("rent", "rent", "rent_total"), cells, strict=True)
        ),
        reconciliations=(
            Reconciliation(parts=tuple(c.cell_id for c in cells[:2]), total=cells[2].cell_id),
        ),
    )
    inputs = Sources()
    inputs.docs["roll"] = source
    authority = TrustedInputs()
    settings = load(apply_environment=False)
    gates = GateService(
        engine, scope=scope, settings=settings.gates, inputs=authority, scratch=tmp_path / "gates"
    )
    registry = ToolRegistry(
        engine=engine,
        context=context,
        workspace=tmp_path / "workspace",
        inputs=ScreenInputs(inputs),
        settings=settings,
        gates=gates,
        risk_policy=RiskPolicy(
            policy_id="synthetic-policy",
            version="v1",
            source_ids=("policy",),
            min_occupancy=Decimal("0.9"),
            min_dscr=Decimal("1.25"),
            occupancy_weight=Decimal("0.4"),
            dscr_weight=Decimal("0.6"),
        ),
    )
    # Host-provided canonical SCREEN pins. No extraction-key renaming is claimed.
    headlines = []
    for row, (key, value, unit) in enumerate(
        (
            ("price", Decimal("10000000"), "USD"),
            ("units", Decimal("100"), "count"),
            ("dscr", Decimal("1.3"), "ratio"),
            ("occupancy", Decimal("0.95"), "ratio"),
            ("market_tier", "B", "text"),
        ),
        start=5,
    ):
        fact = Fact(
            fact_id=key,
            deal_id="deal",
            key=key,
            value=value,
            unit=unit,
            claim_type=ClaimType.SELLER_ASSERTION,
            provenance=[
                Provenance(doc_id="roll", sheet="Source", cell=f"A{row}", quote=str(value))
            ],
            known_at=context.started_at,
            version=1,
        )
        inputs.facts[key] = FactAnchor(fact=fact, authority="quarantine")
        assert registry.call("facts_put", {"anchor_id": key})["status"] == "ok"
        headlines.append(
            (key, Reference(kind="fact", record_id=key, version=1, key=key, unit=unit))
        )
    provider = Provider()
    extractor = Extractor(
        registry=registry,
        sources=inputs,
        provider=provider,
        runtime=ExtractionTransport(provider, source),
        image="synthetic-image",
        scratch=tmp_path / "extract",
        allow_synthetic=True,
    )
    transport = LeadTransport(provider, registry)
    runner = CodexRunner(
        provider=provider,
        registry=registry,
        runtime=transport,
        brain_root=Path("brain").absolute(),
        model_provider="openai",
    )
    evidence = HostEvidence(registry)
    session = RunSession(
        preparser=preparser,
        extractor=extractor,
        screen=ScreenService(registry, authority, BuyBoxPolicy()),
        runner=runner,
        receipts=evidence,
        controls=evidence,
    )
    request = RunInput(deal=str(tmp_path / "raw"), request="Screen synthetic deal")
    plan = RunPlan(
        request=request,
        context=context,
        workspace=Workspace(box=Box(user_id=scope.user_id, box_id="lead"), scope=scope),
        segment=SegmentSpec(
            task_id="task",
            deal_id="deal",
            release_id="release",
            segment_no=0,
            prompt=request.request,
            max_turns=3,
            max_tokens=100,
        ),
        request_id="request",
        owner_id="worker",
        sources=(
            SourcePin(
                relative_path="rent_roll.csv",
                source=source,
                descriptor=Document(doc_id="roll", filename="rent_roll.csv"),
            ),
        ),
        headlines=tuple(headlines),
        capabilities=transport.caps,
        configuration_sha256="0" * 64,
        stuck=StuckLimits(window_s=1),
        poll_s=0.02,
    )
    plan = plan.model_copy(update={"configuration_sha256": configuration_digest(session, plan)})
    jobs = JobStore(engine)
    calls = []

    def compose(pin, job):
        assert jobs.get(pin.identity) == job  # Claim exists BEFORE factory invocation.
        assert transport.starts == 0 or job.status == "completed"
        calls.append(job)
        transport.claim_binding = NativeClaim(
            identity=job.identity, owner_id=job.owner_id, claim_revision=job.claim_revision
        )
        registry.gates = RunGateService(gates, jobs=jobs, job=job, context=context)
        return session

    host = RunHost(jobs=jobs, authorize=lambda supplied: plan, compose=compose)
    yield host, plan, session, transport, evidence, calls
    engine.dispose()


@pytest.mark.asyncio
async def test_run_partial_synthetic_plumbing_only_real_preparse_extract_screen_publication(
    environment,
):
    host, plan, session, transport, evidence, calls = environment
    result = await execute_run(host, plan.request)
    assert result.status == "ok", result
    assert result.evidence == "synthetic_plumbing_only"
    assert len(result.deliverable_ids) == 2
    assert transport.starts == 1 and transport.process.cancelled
    assert len(session.extractor.provider.created) == len(session.extractor.provider.destroyed) == 1
    with session.runner.registry.transaction() as state:
        assert len([f for f in state.all_current(Fact) if f.fact_id.startswith("ex-")]) == 3
        assert all(d.status == "final" for d in state.all_current(Deliverable))
        assert any(e.kind == "gate_result" for e in state.history())
    assert host.jobs.get(plan.identity).status == "completed"


@pytest.mark.asyncio
async def test_run_partial_synthetic_plumbing_only_replay_no_duplicate_launch(environment):
    host, plan, session, transport, evidence, calls = environment
    first = await execute_run(host, plan.request)
    second = await execute_run(host, plan.request)
    assert second == first
    assert transport.starts == 1
    assert len(session.extractor.provider.created) == 1


@pytest.mark.asyncio
async def test_run_unknown_claim_never_calls_factory(environment):
    host, plan, session, transport, evidence, calls = environment
    host.jobs.claim(plan.identity, owner_id=plan.owner_id, now=datetime.now(UTC))
    result = await execute_run(host, plan.request)
    assert result.category == "recovery_unavailable"
    assert not calls and transport.starts == 0


@pytest.mark.asyncio
async def test_run_request_binding_mismatch_no_authority(environment):
    host, plan, session, transport, evidence, calls = environment
    result = await execute_run(host, plan.request.model_copy(update={"request": "Other request"}))
    assert result.category == "binding_mismatch"
    assert not calls and host.jobs.get(plan.identity) is None


@pytest.mark.asyncio
async def test_run_configuration_mismatch_before_external_work(environment):
    host, plan, session, transport, evidence, calls = environment
    session.runner.registry.limits = session.runner.registry.limits.model_copy(
        update={"max_tokens": 5}
    )
    result = await execute_run(host, plan.request)
    assert result.category == "binding_mismatch"
    assert transport.starts == 0 and not session.extractor.provider.created


@pytest.mark.asyncio
async def test_run_unknown_receipt_refuses_relaunch_and_publication(environment):
    host, plan, session, transport, evidence, calls = environment
    evidence.unknown = True
    first = await execute_run(host, plan.request)
    second = await execute_run(host, plan.request)
    assert first.category == "receipt_unavailable"
    assert second.category == "recovery_unavailable"
    assert transport.starts == 1
    with session.runner.registry.transaction() as state:
        assert not state.all_current(Deliverable)


@pytest.mark.asyncio
async def test_run_partial_synthetic_plumbing_only_silent_watchdog_full_interval(environment):
    host, plan, session, transport, evidence, calls = environment
    transport.process.silent = True
    result = await execute_run(host, plan.request)
    assert result.category == "escalation_unavailable"
    assert result.reason == "no_progress"
    assert len(evidence.nudges) == 1
    assert (datetime.now(UTC) - evidence.nudges[0]).total_seconds() >= 1
    assert transport.process.cancelled
    assert host.jobs.get(plan.identity).status == "stopped"
    with session.runner.registry.transaction() as state:
        assert any(e.payload.get("binding") == "run_watchdog" for e in state.history())
        assert not state.all_current(Deliverable)


@pytest.mark.asyncio
async def test_run_parent_cancellation_propagates_after_cleanup(environment):
    host, plan, session, transport, evidence, calls = environment
    transport.process.silent = True
    task = asyncio.create_task(execute_run(host, plan.request))
    async with asyncio.timeout(2):
        while transport.starts == 0:
            await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert transport.process.cancelled
    assert (await execute_run(host, plan.request)).category == "recovery_unavailable"


@pytest.mark.asyncio
async def test_run_changed_source_refuses_before_extraction(environment):
    host, plan, session, transport, evidence, calls = environment
    (session.preparser.raw_root / "rent_roll.csv").write_text("rent\n101\n200\n301\n")
    result = await execute_run(host, plan.request)
    assert result.category == "binding_mismatch"
    assert not session.extractor.provider.created and transport.starts == 0


@pytest.mark.asyncio
async def test_run_unverified_cleanup_keeps_unknown_job(environment):
    host, plan, session, transport, evidence, calls = environment
    transport.process.confirmed = False
    result = await execute_run(host, plan.request)
    assert result.status == "refused"
    assert host.jobs.get(plan.identity).status not in {"completed", "stopped", "failed"}
    assert (await execute_run(host, plan.request)).category == "recovery_unavailable"


@pytest.mark.asyncio
async def test_run_publication_replay_rechecks_current_freshness(environment):
    host, plan, session, transport, evidence, calls = environment
    assert (await execute_run(host, plan.request)).status == "ok"
    with session.runner.registry.transaction() as state:
        state.invalidate("price")
    result = await execute_run(host, plan.request)
    assert result.category == "stale_evidence"
    assert transport.starts == 1


@pytest.mark.asyncio
async def test_run_partial_synthetic_plumbing_only_budget_cap_refuses_before_launch(environment):
    from dataclasses import replace

    host, plan, session, transport, evidence, calls = environment
    session.runner.registry.limits = session.runner.registry.limits.model_copy(
        update={"max_tokens": 100}
    )
    plan = plan.model_copy(update={"configuration_sha256": configuration_digest(session, plan)})
    host = replace(host, authorize=lambda supplied: plan)
    result = await execute_run(host, plan.request)
    assert result.category == "escalation_unavailable" and result.reason == "budget_cap"
    assert transport.starts == 0 and not session.extractor.provider.created


@pytest.mark.asyncio
async def test_run_deadline_stop_reconciles_before_terminal_job(environment):
    from dataclasses import replace

    host, plan, session, transport, evidence, calls = environment
    transport.process.silent = True
    plan = plan.model_copy(update={"segment": plan.segment.model_copy(update={"timeout_s": 0.04})})
    plan = plan.model_copy(update={"configuration_sha256": configuration_digest(session, plan)})
    host = replace(host, authorize=lambda supplied: plan)
    result = await execute_run(host, plan.request)
    assert result.category == "escalation_unavailable" and result.reason == "budget_cap"
    assert transport.process.cancelled and host.jobs.get(plan.identity).status == "stopped"


@pytest.mark.asyncio
async def test_run_cancellation_with_unknown_cleanup_still_propagates(environment):
    host, plan, session, transport, evidence, calls = environment
    transport.process.silent = True
    transport.process.confirmed = False
    task = asyncio.create_task(execute_run(host, plan.request))
    async with asyncio.timeout(2):
        while transport.starts == 0:
            await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert host.jobs.get(plan.identity).status == "start_unknown"


@pytest.mark.asyncio
async def test_run_wrong_receipt_generation_and_session_refuse(environment):
    host, plan, session, transport, evidence, calls = environment
    verify = evidence.verify

    async def wrong(job):
        receipt = await verify(job)
        return receipt.model_copy(update={"claim_revision": job.claim_revision + 1})

    evidence.verify = wrong
    result = await execute_run(host, plan.request)
    assert result.category == "receipt_unavailable"
    assert host.jobs.get(plan.identity).status == "start_unknown"


@pytest.mark.asyncio
async def test_run_uw_model_explicitly_unsupported_no_published_uw(environment):
    from dataclasses import replace

    host, plan, session, transport, evidence, calls = environment
    plan = plan.model_copy(update={"kind": "UW_MODEL"})
    host = replace(host, authorize=lambda supplied: plan)
    result = await execute_run(host, plan.request)
    assert result.category == "unsupported_underwriting"
    assert not calls and transport.starts == 0


@pytest.mark.asyncio
async def test_run_gate_barrier_blocks_native_lead_publication(environment):
    host, plan, session, transport, evidence, calls = environment
    original = transport.start
    attempts = []

    async def start(box, request):
        run = session.screen.run(
            documents=tuple(p.descriptor for p in plan.sources),
            headlines=dict(plan.headlines),
            run_id="premature",
        )
        attempts.extend(
            session.runner.registry.call("finalize_deliverable", {"deliverable_id": identity})
            for identity in run.deliverable_ids
        )
        return await original(box, request)

    transport.start = start
    result = await execute_run(host, plan.request)
    assert result.status == "ok"
    assert len(attempts) == 2 and all(r["category"] == "gate_failure" for r in attempts)
    with session.runner.registry.transaction() as state:
        assert len([d for d in state.all_current(Deliverable) if d.status == "final"]) == 2


@pytest.mark.asyncio
async def test_run_unknown_native_start_does_not_retry(environment):
    host, plan, session, transport, evidence, calls = environment

    async def unknown(box, request):
        transport.starts += 1
        raise RuntimeError("Native launch happened, acknowledgement lost")

    transport.start = unknown
    result = await execute_run(host, plan.request)
    assert result.status == "refused"
    assert (await execute_run(host, plan.request)).category == "recovery_unavailable"
    assert transport.starts == 1


@pytest.mark.asyncio
async def test_run_native_claim_generation_binding_required_before_launch(environment):
    from dataclasses import replace

    host, plan, session, transport, evidence, calls = environment
    compose = host.compose

    def wrong(pin, job):
        composed = compose(pin, job)
        transport.claim_binding = transport.claim_binding.model_copy(
            update={"claim_revision": job.claim_revision + 1}
        )
        return composed

    host = replace(host, compose=wrong)
    result = await execute_run(host, plan.request)
    assert result.category == "binding_mismatch"
    assert not session.extractor.provider.created and transport.starts == 0


@pytest.mark.asyncio
async def test_run_source_change_during_lead_refuses_publication(environment):
    host, plan, session, transport, evidence, calls = environment
    original = transport.start

    async def changed(box, request):
        process = await original(box, request)
        (session.preparser.raw_root / "rent_roll.csv").write_text("rent\n101\n200\n301\n")
        return process

    transport.start = changed
    result = await execute_run(host, plan.request)
    assert result.category == "binding_mismatch"
    with session.runner.registry.transaction() as state:
        assert not state.all_current(Deliverable)


@pytest.mark.asyncio
async def test_run_capability_change_before_start_refuses(environment):
    host, plan, session, transport, evidence, calls = environment
    transport.caps = transport.caps.model_copy(update={"resume_supported": False})
    result = await execute_run(host, plan.request)
    assert result.category == "binding_mismatch"
    assert transport.starts == 0 and not session.extractor.provider.created


@pytest.mark.asyncio
async def test_run_watchdog_checkpoint_failure_does_not_orphan_lead(environment, monkeypatch):
    from cre_brain.runner.tools.state import ToolState

    host, plan, session, transport, evidence, calls = environment
    original = ToolState.event

    def fail_checkpoint(self, kind, payload):
        if payload.get("binding") == "run_watchdog":
            raise RuntimeError("Synthetic storage failure")
        return original(self, kind, payload)

    monkeypatch.setattr(ToolState, "event", fail_checkpoint)
    result = await execute_run(host, plan.request)
    await asyncio.sleep(0.05)
    assert result.status == "refused"
    assert transport.starts == 0


@pytest.mark.asyncio
async def test_run_resume_target_requires_separate_verified_recovery(environment):
    from dataclasses import replace

    host, plan, session, transport, evidence, calls = environment
    plan = plan.model_copy(
        update={"segment": plan.segment.model_copy(update={"resume_session_id": "seller-session"})}
    )
    host = replace(host, authorize=lambda supplied: plan)
    result = await execute_run(host, plan.request)
    assert result.category == "invalid_input"
    assert not calls and transport.starts == 0


@pytest.mark.asyncio
async def test_run_completed_without_manifest_refuses_new_launch(environment):
    host, plan, session, transport, evidence, calls = environment
    # A real synthetic run reaches native completion; SCREEN finalization then refuses.
    from dataclasses import replace

    plan = plan.model_copy(update={"configuration_sha256": configuration_digest(session, plan)})
    host = replace(host, authorize=lambda supplied: plan)
    original = session.screen.run

    def unavailable(**kwargs):
        from cre_brain.runner.policy import Refusal

        raise Refusal("synthetic_publication_failure", "Failure after native reconciliation")

    session.screen.run = unavailable
    assert (await execute_run(host, plan.request)).category == "synthetic_publication_failure"
    session.screen.run = original
    assert host.jobs.get(plan.identity).status == "completed"
    assert (await execute_run(host, plan.request)).category == "recovery_unavailable"
    assert transport.starts == 1


def test_run_cli_trusted_embedding_uses_checked_flow(environment):
    from typer.testing import CliRunner

    from cre_brain.cli import create_app
    from cre_brain.runner.run_commands import install_run_host

    host, plan, session, transport, evidence, calls = environment
    install_run_host(host)
    try:
        result = CliRunner().invoke(
            create_app(), ["run", "--deal", plan.request.deal, "--request", plan.request.request]
        )
    finally:
        install_run_host(None)
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["status"] == "ok"
    assert json.loads(result.stdout)["evidence"] == "synthetic_plumbing_only"
    assert transport.starts == 1


@pytest.mark.asyncio
async def test_run_authenticated_context_mismatch_refuses_before_model_work(environment):
    host, plan, session, transport, evidence, calls = environment
    session.runner.registry.context = session.runner.registry.context.model_copy(
        update={"deal_id": "other-deal"}
    )
    result = await execute_run(host, plan.request)
    assert result.category == "binding_mismatch"
    assert transport.starts == 0 and not session.extractor.provider.created


@pytest.mark.asyncio
async def test_run_wrong_native_session_receipt_refuses(environment):
    host, plan, session, transport, evidence, calls = environment
    verify = evidence.verify

    async def wrong(job):
        receipt = await verify(job)
        return receipt.model_copy(update={"session_id": "other-session"})

    evidence.verify = wrong
    result = await execute_run(host, plan.request)
    assert result.category == "receipt_unavailable"
    assert host.jobs.get(plan.identity).status == "start_unknown"
    with session.runner.registry.transaction() as state:
        assert not state.all_current(Deliverable)


@pytest.mark.asyncio
async def test_run_slow_nudge_acknowledgement_gets_full_watchdog_interval(environment):
    host, plan, session, transport, evidence, calls = environment
    transport.process.silent = True

    async def delayed_nudge(job):
        await asyncio.sleep(0.2)
        evidence.nudges.append(datetime.now(UTC))

    evidence.nudge = delayed_nudge
    result = await execute_run(host, plan.request)
    assert result.reason == "no_progress"
    assert (datetime.now(UTC) - evidence.nudges[0]).total_seconds() >= 1
