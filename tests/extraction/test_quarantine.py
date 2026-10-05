"""Public synthetic observations/provider records; plumbing, never quality evidence."""

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine

from cre_brain.config import load
from cre_brain.domain import ClaimType, Fact
from cre_brain.domain.base import TenantScope
from cre_brain.domain.models import Provenance
from cre_brain.extraction.preparse.models import (
    CellAnchor,
    Limits,
    ParsedCell,
    ParsedDocument,
    ParsedTable,
    digest,
)
from cre_brain.extraction.quarantine import Extractor
from cre_brain.extraction.schemas import (
    ExtractionLimits,
    Reconciliation,
    Selection,
    SourceDocument,
)
from cre_brain.runner.policy import HostContext
from cre_brain.runner.streaming import CancellationReceipt
from cre_brain.runner.tools.registry import ToolRegistry
from cre_brain.sandbox.base import Box, SandboxError
from cre_brain.state.schema import metadata
from cre_brain.state.store import SqlVersionedStore


def source(scope, doc_id="roll", doc_type="rent_roll", values=("100.00", "200.00", "300.00")):
    fields = {
        "rent_roll": ("rent", "rent", "rent_total"),
        "t12": ("income", "income", "income_total"),
        "om_summary": ("units", "units", "units_total"),
    }[doc_type]
    cells = tuple(
        ParsedCell(
            cell_id=digest((doc_id, i, value)),
            anchor=CellAnchor(doc_id=doc_id, sheet="Source", cell=f"B{i + 1}"),
            kind="text",
            text=value,
            provenance=Provenance(doc_id=doc_id, sheet="Source", cell=f"B{i + 1}", quote=value),
        )
        for i, value in enumerate(values)
    )
    doc = ParsedDocument(
        doc_id=doc_id,
        scope=scope,
        source_name="public.csv",
        source_sha256=digest(values),
        source_bytes=10,
        parser="native-csv",
        parser_versions=(("synthetic", "1"),),
        config_sha256=digest("public"),
        limits=Limits(),
        status="parsed",
        tables=(ParsedTable(table_id=digest(doc_id), sheet="Source", cells=cells),),
    )
    selections = tuple(
        Selection(field=field, anchor_id=cell.cell_id, anchor_kind="cell")
        for field, cell in zip(fields, cells, strict=True)
    )
    return SourceDocument(
        document=doc,
        parsed_sha256=hashlib.sha256(doc.model_dump_json().encode()).hexdigest(),
        deal_id="deal",
        doc_type=doc_type,
        required=selections,
        reconciliations=(
            Reconciliation(parts=tuple(c.cell_id for c in cells[:-1]), total=cells[-1].cell_id),
        ),
    )


def output(src):
    cells = {c.cell_id: c for t in src.document.tables for c in t.cells} | {
        t.text_id: t for t in src.document.texts
    }
    return {
        "doc_type": src.doc_type,
        "observations": [
            dict(**s.model_dump(), quote=cells[s.anchor_id].text, value=cells[s.anchor_id].text)
            for s in src.required
        ],
    }


def frames(body):
    return [
        json.dumps(event).encode() + b"\n"
        for event in (
            {"type": "thread.started", "thread_id": "synthetic"},
            {"type": "turn.started"},
            {
                "type": "item.completed",
                "item": {"id": "m", "type": "agent_message", "text": json.dumps(body)},
            },
            {"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}},
        )
    ]


class Sources:
    def __init__(self, docs):
        self.docs = {src.document.doc_id: src for src in docs}

    def document(self, context, identity):
        return self.docs.get(identity)

    def fact(self, context, identity):
        return None

    def artifact(self, context, identity):
        return None

    def template(self, context, identity):
        return None

    def rule_policy(self, context, identity):
        return None


class Provider:
    def __init__(self):
        self.created = []
        self.destroyed = []
        self.active = 0
        self.peak = 0

    async def create_extraction(self, user_id, image, parsed):
        data = parsed.read_bytes()
        doc = ParsedDocument.model_validate_json(data)
        box = Box(user_id=user_id, box_id=doc.doc_id, kind="extractor")
        self.created.append((box, data))
        self.active += 1
        self.peak = max(self.peak, self.active)
        return box

    async def exec(self, *args):
        raise AssertionError("No buffered execution/host fallback")

    async def destroy(self, box):
        self.destroyed.append(box)
        self.active -= 1


class Process:
    def __init__(self, lines, delay=0, hang=False):
        self.lines, self.delay, self.hang = lines, delay, hang
        self.cancelled = False

    async def stdout(self):
        await asyncio.sleep(self.delay)
        for line in self.lines:
            yield line
        if self.hang:
            await asyncio.Event().wait()

    async def wait(self):
        return 0

    async def cancel(self):
        self.cancelled = True
        return CancellationReceipt(confirmed=True, total_tokens=2)


class Runtime:
    def __init__(self, provider, docs):
        self.provider = provider
        self.docs = {src.document.doc_id: src for src in docs}
        self.requests, self.bundles, self.processes = {}, {}, {}
        self.override = {}
        self.hang = False
        self.verified = True

    async def capabilities(self, box, bundle):
        from cre_brain.extraction.runtime import ExtractionCapabilities

        return ExtractionCapabilities(
            evidence="synthetic_plumbing_only",
            cli_version="synthetic",
            isolated=self.verified,
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
        self.bundles[box.box_id] = bundle

    async def start(self, box, request):
        self.requests[box.box_id] = request
        src = self.docs[box.box_id]
        process = Process(
            self.override.get(box.box_id, frames(output(src))), delay=0.01, hang=self.hang
        )
        self.processes[box.box_id] = process
        return process


@pytest.fixture
def setup(tmp_path):
    scope = TenantScope(user_id="user", firm_id="firm")
    context = HostContext(
        scope=scope,
        task_id="task",
        deal_id="deal",
        role="lead",
        session_id="host",
        release_id="release",
        started_at=datetime.now(UTC),
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'state.db'}")
    metadata.create_all(engine)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    docs = [source(scope)]
    inputs = Sources(docs)
    registry = ToolRegistry(
        engine=engine,
        context=context,
        workspace=workspace,
        inputs=inputs,
        settings=load(apply_environment=False),
    )
    provider = Provider()
    runtime = Runtime(provider, docs)
    extractor = Extractor(
        registry=registry,
        sources=inputs,
        provider=provider,
        runtime=runtime,
        image="trusted-extract-image",
        scratch=tmp_path / "scratch",
        allow_synthetic=True,
    )
    yield extractor, registry, inputs, provider, runtime
    engine.dispose()


@pytest.mark.asyncio
async def test_t035_ac1_separate_home_one_immutable_document_argv_and_cleanup(setup):
    extractor, registry, inputs, provider, runtime = setup
    result = await extractor.extract(("roll",))
    assert len(result.facts) == 3
    request = runtime.requests["roll"]
    assert isinstance(request.argv, tuple)
    assert request.argv[:6] == ("codex", "exec", "--json", "-p", "extractor", "--output-schema")
    assert request.model == registry.settings.models.roles["extraction"].model
    assert request.codex_home != str(registry.workspace / ".codex")
    bundle = runtime.bundles["roll"]
    assert set(bundle.files) == {"AGENTS.md", "schema.json", "codex/config.toml"}
    assert b"mcp_servers" not in bundle.files["codex/config.toml"]
    assert provider.created[0][1] == inputs.docs["roll"].document.model_dump_json().encode()
    assert provider.destroyed == [provider.created[0][0]]
    assert runtime.processes["roll"].cancelled


@pytest.mark.asyncio
async def test_t035_ac1_missing_or_unverified_adapter_refuses(setup):
    extractor, registry, inputs, provider, runtime = setup
    extractor.runtime = None
    with pytest.raises(SandboxError, match="adapter"):
        await extractor.extract(("roll",))
    assert not provider.created
    extractor.runtime = runtime
    runtime.verified = False
    with pytest.raises(SandboxError, match="capabilities"):
        await extractor.extract(("roll",))
    assert len(provider.destroyed) == 1
    assert not runtime.requests


@pytest.mark.asyncio
@pytest.mark.parametrize("doc_type", ["rent_roll", "t12", "om_summary"])
async def test_t035_ac2_schema_provenance_exact_decimal_and_idempotency(setup, doc_type):
    extractor, registry, inputs, provider, runtime = setup
    values = (
        ("100.0000", "200.0000", "300.0000")
        if doc_type == "om_summary"
        else ("100.0100", "200.0000", "300.0100")
    )
    src = source(registry.context.scope, doc_type=doc_type, values=values)
    inputs.docs["roll"] = runtime.docs["roll"] = src
    first = await extractor.extract(("roll",))
    second = await extractor.extract(("roll",))
    assert first == second
    assert len(provider.created) == 1
    for fact, _selection in zip(first.facts, src.required, strict=True):
        assert fact.claim_type == ClaimType.SELLER_ASSERTION
        assert fact.deal_id == "deal" and fact.version == 1
        assert fact.provenance[0].doc_id == "roll"
        assert fact.value.as_tuple() == Decimal(fact.provenance[0].quote).as_tuple()
        assert (
            SqlVersionedStore(registry.engine, Fact).get(fact.fact_id, scope=registry.context.scope)
            == fact
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "attack",
    ["anchor", "kind", "quote", "value", "field", "duplicate", "authority", "doc_type", "missing"],
)
async def test_t035_ac2_hostile_output_never_creates_facts(setup, attack):
    extractor, registry, inputs, provider, runtime = setup
    body = output(inputs.docs["roll"])
    first = body["observations"][0]
    if attack == "anchor":
        first["anchor_id"] = "f" * 64
    elif attack == "kind":
        first["anchor_kind"] = "text"
    elif attack == "quote":
        first["quote"] = "changed"
    elif attack == "value":
        first["value"] = "100"
    elif attack == "field":
        first["field"] = "units"
    elif attack == "duplicate":
        body["observations"].append(dict(first))
    elif attack == "authority":
        first["claim_type"] = "VERIFIED_FACT"
    elif attack == "doc_type":
        body["doc_type"] = "t12"
    elif attack == "missing":
        body["observations"].pop()
    runtime.override["roll"] = frames(body)
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    with registry.transaction() as state:
        assert not state.all_current(Fact)
    assert len(provider.destroyed) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "attack",
    ["scope", "deal", "digest", "unsupported", "duplicate_source", "status", "source_bounds"],
)
async def test_t035_ac2_authenticated_source_preflight(setup, attack):
    extractor, registry, inputs, provider, runtime = setup
    src = inputs.docs["roll"]
    if attack == "scope":
        src = src.model_copy(
            update={
                "document": src.document.model_copy(
                    update={"scope": TenantScope(user_id="other", firm_id="firm")}
                )
            }
        )
    elif attack == "deal":
        src = src.model_copy(update={"deal_id": "other"})
    elif attack == "digest":
        src = src.model_copy(update={"parsed_sha256": "f" * 64})
    elif attack == "unsupported":
        src = src.model_copy(update={"doc_type": "lease"})
    elif attack == "status":
        src = src.model_copy(
            update={"document": src.document.model_copy(update={"status": "empty"})}
        )
    elif attack == "source_bounds":
        extractor.limits = ExtractionLimits(max_source_bytes=1)
    else:
        table = src.document.tables[0]
        doc = src.document.model_copy(
            update={
                "tables": (table.model_copy(update={"cells": table.cells + (table.cells[0],)}),)
            }
        )
        src = src.model_copy(update={"document": doc})
    inputs.docs["roll"] = src
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    assert not provider.created


@pytest.mark.asyncio
async def test_t035_ac2_concurrency_order_and_failing_batch_are_atomic(setup):
    extractor, registry, inputs, provider, runtime = setup
    docs = [source(registry.context.scope, f"doc{i}") for i in range(6)]
    inputs.docs = runtime.docs = {s.document.doc_id: s for s in docs}
    ids = tuple(inputs.docs)
    result = await extractor.extract(ids)
    assert provider.peak <= registry.settings.budget.max_parallel_extractions
    assert provider.peak > 1
    assert tuple(dict.fromkeys(f.provenance[0].doc_id for f in result.facts)) == ids
    assert len(provider.destroyed) == 6
    # A new batch cannot leave the successful document visible if a peer fails.
    more = [source(registry.context.scope, "extra1"), source(registry.context.scope, "extra2")]
    inputs.docs.update({s.document.doc_id: s for s in more})
    runtime.override["extra2"] = [b"not JSON\n"]
    with pytest.raises(SandboxError):
        await extractor.extract(("extra1", "extra2"))
    with registry.transaction() as state:
        assert all(
            f.provenance[0].doc_id not in {"extra1", "extra2"} for f in state.all_current(Fact)
        )
    assert provider.active == 0


@pytest.mark.asyncio
async def test_t035_ac3_real_gates_snapshot_and_checksum_failure_rolls_back(setup):
    extractor, registry, inputs, provider, runtime = setup
    src = source(registry.context.scope, values=("100", "200", "999"))
    inputs.docs["roll"] = runtime.docs["roll"] = src
    with pytest.raises(SandboxError, match="gate"):
        await extractor.extract(("roll",))
    with registry.transaction() as state:
        assert not state.all_current(Fact)
    src = source(registry.context.scope)
    inputs.docs["roll"] = runtime.docs["roll"] = src
    result = await extractor.extract(("roll",))
    assert tuple(result.gates) == ("coverage", "checksums")
    assert all(g.passed for g in result.gates.values())
    assert hashlib.sha256(result.snapshot.data).hexdigest() == result.snapshot.sha256


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "lines",
    [
        [b'{"type":"turn.started","type":"turn.completed"}\n'],
        [b"{" + b"x" * 131072 + b"}\n"],
        [b"{}\n"],
        [b'{"type":"error"}\n'],
    ],
)
async def test_t035_ac1_malformed_oversized_incomplete_events_cleanup(setup, lines):
    extractor, registry, inputs, provider, runtime = setup
    runtime.override["roll"] = lines
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    assert provider.active == 0 and runtime.processes["roll"].cancelled


@pytest.mark.asyncio
async def test_t035_ac1_cancellation_and_timeout_destroy_boxes(setup):
    extractor, registry, inputs, provider, runtime = setup
    runtime.hang = True
    task = asyncio.create_task(extractor.extract(("roll",)))
    async with asyncio.timeout(1):
        while not runtime.processes and not task.done():
            await asyncio.sleep(0)
    assert runtime.processes
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert provider.active == 0
    assert runtime.processes["roll"].cancelled
    extractor.limits = ExtractionLimits(timeout_s=0.02)
    with pytest.raises(SandboxError, match="time"):
        await extractor.extract(("roll",))
    assert provider.active == 0


@pytest.mark.asyncio
async def test_t035_ac1_scratch_alias_symlink_refuses(setup, tmp_path):
    extractor, registry, inputs, provider, runtime = setup
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    extractor.scratch = link
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    assert not provider.created
    extractor.scratch = real / ".." / "real"
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    assert not provider.created


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "values",
    [
        ("$1,200.0100", "$200.0000", "$1,400.0100"),
        ("(100.00)", "200.00", "100.00"),
        ("100", "200", "300"),
    ],
)
async def test_t035_ac2_deterministic_numeric_formats(setup, values):
    extractor, registry, inputs, provider, runtime = setup
    src = source(registry.context.scope, values=values)
    inputs.docs["roll"] = runtime.docs["roll"] = src
    result = await extractor.extract(("roll",))
    assert tuple(f.provenance[0].quote for f in result.facts) == values
    assert all(isinstance(f.value, Decimal) for f in result.facts)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value",
    ["1e999999", "NaN", "1/2", "100 + 200", "100%", "1,00", "rent 100", "１２３", "2026-01-01"],
)
async def test_t035_ac2_ambiguous_transformed_or_unbounded_numeric_sources_refuse(setup, value):
    extractor, registry, inputs, provider, runtime = setup
    src = source(registry.context.scope, values=(value, "200", "300"))
    inputs.docs["roll"] = src
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    assert not provider.created


@pytest.mark.asyncio
async def test_t035_ac2_date_text_exact_and_native_scientific_decimal(setup):
    from datetime import date

    extractor, registry, inputs, provider, runtime = setup
    src = source(registry.context.scope)
    table = src.document.tables[0]
    dates = ParsedCell(
        cell_id=digest("date"),
        anchor=CellAnchor(doc_id="roll", sheet="Source", cell="C4"),
        kind="date",
        text="2026-10-05",
        provenance=Provenance(doc_id="roll", sheet="Source", cell="C4", quote="2026-10-05"),
    )
    text = ParsedCell(
        cell_id=digest("text"),
        anchor=CellAnchor(doc_id="roll", sheet="Source", cell="C5"),
        kind="text",
        text="  Unit 001\n",
        provenance=Provenance(doc_id="roll", sheet="Source", cell="C5", quote="  Unit 001\n"),
    )
    cells = (table.cells[0].model_copy(update={"kind": "number"}), *table.cells[1:], dates, text)
    doc = src.document.model_copy(update={"tables": (table.model_copy(update={"cells": cells}),)})
    src = src.model_copy(
        update={
            "document": doc,
            "parsed_sha256": hashlib.sha256(doc.model_dump_json().encode()).hexdigest(),
            "required": src.required
            + (
                Selection(field="lease_end", anchor_id=dates.cell_id, anchor_kind="cell"),
                Selection(field="unit_id", anchor_id=text.cell_id, anchor_kind="cell"),
            ),
        }
    )
    inputs.docs["roll"] = runtime.docs["roll"] = src
    result = await extractor.extract(("roll",))
    assert result.facts[-2].value == date(2026, 10, 5)
    assert result.facts[-1].value == "  Unit 001\n"
    assert result.facts[0].value.as_tuple() == Decimal("100.00").as_tuple()


@pytest.mark.asyncio
async def test_t035_ac3_gate_receives_authenticated_same_snapshot_and_missing_coverage_refuses(
    setup, monkeypatch
):
    from cre_brain.gates.models import GatePlan
    from cre_brain.gates.service import GateService

    extractor, registry, inputs, provider, runtime = setup
    original = GateService.check_bytes
    snapshots = []

    def observe(self, name, deliverable, snapshot):
        snapshots.append(snapshot)
        return original(self, name, deliverable, snapshot)

    monkeypatch.setattr(GateService, "check_bytes", observe)
    result = await extractor.extract(("roll",))
    assert snapshots == [result.snapshot, result.snapshot]
    assert snapshots[0] is snapshots[1]
    assert isinstance(result.plan, GatePlan)


@pytest.mark.asyncio
async def test_t035_ac1_cleanup_failure_blocks_retry(setup):
    extractor, registry, inputs, provider, runtime = setup
    original_start = runtime.start

    async def bad_start(*args):
        process = await original_start(*args)

        async def cancel():
            return CancellationReceipt(confirmed=False, total_tokens=None)

        process.cancel = cancel
        return process

    runtime.start = bad_start
    with pytest.raises(SandboxError, match="cleanup"):
        await extractor.extract(("roll",))
    assert provider.active == 0
    runtime.start = original_start
    with pytest.raises(SandboxError, match="recovery"):
        await extractor.extract(("roll",))
    assert len(provider.created) == 1


@pytest.mark.asyncio
async def test_t035_ac4_fake_runner_real_tool_final_state(setup, tmp_path):
    from pathlib import Path

    from cre_brain.domain import Deliverable, DeliverableKind
    from cre_brain.gates.models import TrustedInputs
    from cre_brain.gates.service import GateService
    from cre_brain.runner.codex import CodexRunner
    from cre_brain.runner.fake import FakeRunner
    from cre_brain.runner.record import record_segment
    from cre_brain.runner.segment import SegmentSpec, Workspace
    from cre_brain.runner.streaming import RuntimeCapabilities
    from cre_brain.runner.tools.contracts import Artifact

    extractor, registry, inputs, provider, runtime = setup
    result = await extractor.extract(("roll",))
    fact = result.facts[0]
    directory = registry.workspace / "deals/deal/deliverables"
    directory.mkdir(parents=True)
    path = directory / "extraction.md"
    path.write_text("Source observations remain quarantined seller assertions.\n")
    draft = Deliverable(
        d_id="extraction",
        deal_ids=["deal"],
        kind=DeliverableKind.DD_TRACKER,
        version=1,
        status="draft",
        path=str(path),
        gate_results=[],
        depends_on=[f.fact_id for f in result.facts],
    )
    anchor = Artifact(
        deliverable=draft, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), extraction=True
    )
    original_artifact = inputs.artifact
    inputs.artifact = (
        lambda context, identity: anchor
        if identity == draft.d_id
        else original_artifact(context, identity)
    )
    plans = TrustedInputs()
    plans.put_plan(registry.context.scope, draft, result.plan)
    service = GateService(
        registry.engine,
        scope=registry.context.scope,
        settings=registry.settings.gates,
        inputs=plans,
        scratch=tmp_path / "gate-scratch",
    )

    class FinalGateAdapter:
        scope = registry.context.scope

        def check_bytes(self, name, deliverable, snapshot):
            # RegistryReplayAdapter independently authenticates current final state.
            comparable = deliverable
            if deliverable.status == "final":
                assert deliverable.version == 2 and deliverable.parent_version == 1
                comparable = deliverable.model_copy(
                    update={
                        "version": 1,
                        "status": "draft",
                        "parent_version": None,
                        "gate_results": [],
                    }
                )
            assert comparable == draft
            return service.check_bytes(name, comparable, snapshot)

    registry.gates = FinalGateAdapter()
    with registry.transaction() as state:
        state.append(draft)
    calls = (
        (
            "facts_get",
            {
                "reference": {
                    "kind": "fact",
                    "record_id": fact.fact_id,
                    "version": 1,
                    "key": fact.key,
                    "unit": fact.unit,
                }
            },
        ),
        ("finalize_deliverable", {"deliverable_id": draft.d_id}),
    )
    records = [
        {"type": "thread.started", "thread_id": "synthetic-lead"},
        {"type": "turn.started"},
        *[
            {
                "type": "item.completed",
                "item": {
                    "id": f"call{i}",
                    "type": "mcp_tool_call",
                    "server": "cre",
                    "tool": tool,
                    "arguments": arguments,
                    "result": {"content": [{"type": "text", "text": '{"status":"ok","data":{}}'}]},
                    "status": "completed",
                },
            }
            for i, (tool, arguments) in enumerate(calls)
        ],
        {"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}},
    ]

    class LeadRuntime:
        def __init__(self):
            self.provider, self.registry = provider, registry
            self.process = Process([json.dumps(e).encode() + b"\n" for e in records])

        async def capabilities(self, box):
            return RuntimeCapabilities(
                evidence="synthetic_plumbing_only",
                cli_version="synthetic",
                isolated=True,
                authenticated=True,
                configuration_verified=True,
                hard_caps=True,
                resume_supported=True,
            )

        async def stage(self, box, bundle):
            pass

        async def start(self, box, request):
            return self.process

    lead = CodexRunner(
        provider=provider,
        registry=registry,
        runtime=LeadRuntime(),
        brain_root=Path("brain").absolute(),
        model_provider="openai",
    )
    ws = Workspace(
        box=Box(user_id="user", box_id="synthetic-lead-box"), scope=registry.context.scope
    )
    seg = SegmentSpec(
        task_id="task",
        deal_id="deal",
        release_id="release",
        segment_no=0,
        prompt="Synthetic extraction plumbing",
        max_turns=3,
        max_tokens=100,
    )
    recording = tmp_path / "synthetic-capture"
    manifest = await record_segment(
        lead, seg, ws, registry.context, recording, expected_deliverables=(draft.d_id,)
    )
    assert manifest.evidence == "synthetic_plumbing_only"
    replay = FakeRunner(recording, registry=registry)
    events = [
        e
        async for e in replay.run_segment(
            seg.model_copy(update={"segment_no": 1}), ws, registry.context
        )
    ]
    assert events[-1].payload["plumbing_only"] is True
    final = SqlVersionedStore(registry.engine, Deliverable).get(
        draft.d_id, scope=registry.context.scope
    )
    assert final.status == "final" and final.version == 2
    assert all(g.passed for g in final.gate_results)
    response = registry.call("facts_get", calls[0][1])
    assert (
        response["status"] == "ok"
        and response["data"]["claim_type"] == ClaimType.SELLER_ASSERTION.value
    )
    assert response["data"]["provenance"][0]["quote"] is None


@pytest.mark.asyncio
async def test_t035_ac1_shell_events_stay_inside_box_and_no_mcp(setup):
    extractor, registry, inputs, provider, runtime = setup
    lines = frames(output(inputs.docs["roll"]))
    shell = [
        {
            "type": "item.started",
            "item": {
                "id": "shell",
                "type": "command_execution",
                "command": "read parsed",
                "status": "in_progress",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "shell",
                "type": "command_execution",
                "command": "read parsed",
                "status": "completed",
                "exit_code": 0,
                "aggregated_output": "inert",
            },
        },
    ]
    runtime.override["roll"] = (
        lines[:2] + [json.dumps(e).encode() + b"\n" for e in shell] + lines[2:]
    )
    result = await extractor.extract(("roll",))
    assert len(result.facts) == 3


@pytest.mark.asyncio
async def test_t035_ac1_crashed_attempt_requires_canonical_recovery(setup):
    extractor, registry, inputs, provider, runtime = setup
    with registry.transaction() as state:
        state.event(
            "tool_result",
            {"binding": "extraction_attempt", "identity": "crashed", "phase": "start"},
        )
    with pytest.raises(SandboxError, match="recovery"):
        await extractor.extract(("roll",))
    assert not provider.created


@pytest.mark.asyncio
async def test_t035_ac1_extraction_reserves_canonical_token_budget(setup):
    extractor, registry, inputs, provider, runtime = setup
    registry.limits = registry.limits.model_copy(update={"max_tokens": 1})
    with pytest.raises(SandboxError, match="budget"):
        await extractor.extract(("roll",))
    assert not provider.created


@pytest.mark.asyncio
async def test_t035_ac1_adapter_time_remaining_after_stage(setup):
    extractor, registry, inputs, provider, runtime = setup
    original = runtime.stage

    async def slow_stage(*args):
        await asyncio.sleep(0.03)
        await original(*args)

    runtime.stage = slow_stage
    extractor.limits = ExtractionLimits(timeout_s=0.1)
    await extractor.extract(("roll",))
    assert 0 < runtime.requests["roll"].timeout_s < 0.09


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "flag",
    [
        "authenticated",
        "configuration_verified",
        "hard_caps",
        "model_only_egress",
        "no_mcp",
        "single_document_readonly",
        "bundle_sha256",
        "parsed_sha256",
    ],
)
async def test_t035_ac1_each_verified_capability_binding_is_required(setup, flag):
    extractor, registry, inputs, provider, runtime = setup
    original = runtime.capabilities

    async def caps(*args):
        value = await original(*args)
        return value.model_copy(update={flag: "f" * 64 if flag.endswith("sha256") else False})

    runtime.capabilities = caps
    with pytest.raises(SandboxError, match="capabilities"):
        await extractor.extract(("roll",))
    assert provider.active == 0 and not runtime.requests


@pytest.mark.asyncio
async def test_t035_ac2_cross_document_anchor_and_source_identity_refuse(setup):
    extractor, registry, inputs, provider, runtime = setup
    other = source(registry.context.scope, "other")
    body = output(inputs.docs["roll"])
    body["observations"][0]["anchor_id"] = other.required[0].anchor_id
    runtime.override["roll"] = frames(body)
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    inputs.docs["roll"] = other
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    assert len(provider.created) == len(provider.destroyed) == 1


@pytest.mark.asyncio
async def test_t035_ac2_field_collision_in_same_row_refuses_before_runtime(setup):
    extractor, registry, inputs, provider, runtime = setup
    src = inputs.docs["roll"]
    table = src.document.tables[0]
    changed = table.cells[1].model_copy(
        update={
            "anchor": CellAnchor(doc_id="roll", sheet="Source", cell="C1"),
            "provenance": Provenance(
                doc_id="roll", sheet="Source", cell="C1", quote=table.cells[1].text
            ),
        }
    )
    doc = src.document.model_copy(
        update={
            "tables": (
                table.model_copy(update={"cells": (table.cells[0], changed, table.cells[2])}),
            )
        }
    )
    inputs.docs["roll"] = src.model_copy(
        update={
            "document": doc,
            "parsed_sha256": hashlib.sha256(doc.model_dump_json().encode()).hexdigest(),
        }
    )
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    assert not provider.created


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bound", ["max_schema_bytes", "max_line_bytes", "max_output_bytes", "max_events", "max_tokens"]
)
async def test_t035_ac1_each_output_schema_event_token_bound_refuses(setup, bound):
    extractor, registry, inputs, provider, runtime = setup
    extractor.limits = ExtractionLimits(**{bound: 1})
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    assert provider.active == 0
    with registry.transaction() as state:
        assert not state.all_current(Fact)


@pytest.mark.asyncio
async def test_t035_ac1_duplicate_schema_json_ids_and_mcp_items_refuse(setup):
    extractor, registry, inputs, provider, runtime = setup
    src = inputs.docs["roll"]
    lines = frames(output(src))
    # Duplicate JSON members are rejected even if the last member looks valid.
    event = json.loads(lines[2])
    event["item"]["text"] = '{"doc_type":"rent_roll","doc_type":"rent_roll","observations":[]}'
    runtime.override["roll"] = lines[:2] + [json.dumps(event).encode() + b"\n"] + lines[3:]
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    event["item"] = {
        "id": "cre",
        "type": "mcp_tool_call",
        "server": "cre",
        "tool": "facts_put",
        "arguments": {"anchor_id": "attacker"},
    }
    runtime.override["roll"] = lines[:2] + [json.dumps(event).encode() + b"\n"] + lines[3:]
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    assert provider.active == 0


@pytest.mark.asyncio
async def test_t035_ac3_coverage_backend_failure_cannot_publish(setup, monkeypatch):
    from cre_brain.gates.service import GateService

    extractor, registry, inputs, provider, runtime = setup

    def broken(*args):
        raise RuntimeError("synthetic unavailable gate backend")

    monkeypatch.setattr(GateService, "_coverage", broken)
    with pytest.raises(SandboxError, match="gate"):
        await extractor.extract(("roll",))
    with registry.transaction() as state:
        assert not state.all_current(Fact)
        assert not any(e.payload.get("binding") == "extraction" for e in state.history())


@pytest.mark.asyncio
async def test_t035_ac1_repeated_cancellation_drains_cleanup_for_whole_batch(setup):
    extractor, registry, inputs, provider, runtime = setup
    docs = [source(registry.context.scope, f"doc{i}") for i in range(6)]
    inputs.docs = runtime.docs = {s.document.doc_id: s for s in docs}
    runtime.hang = True
    original_start = runtime.start
    cleanup_started = asyncio.Event()
    cleanup_finish = asyncio.Event()

    async def start(*args):
        process = await original_start(*args)

        async def slow_cancel():
            cleanup_started.set()
            await cleanup_finish.wait()
            process.cancelled = True
            return CancellationReceipt(confirmed=True, total_tokens=2)

        process.cancel = slow_cancel
        return process

    runtime.start = start
    task = asyncio.create_task(extractor.extract(tuple(inputs.docs)))
    async with asyncio.timeout(1):
        while len(runtime.processes) < registry.settings.budget.max_parallel_extractions:
            await asyncio.sleep(0)
    task.cancel()
    await asyncio.wait_for(cleanup_started.wait(), 1)
    task.cancel()
    cleanup_finish.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 1)
    assert provider.active == 0
    assert len(provider.created) == len(provider.destroyed)
    assert all(p.cancelled for p in runtime.processes.values())
    with registry.transaction() as state:
        assert not state.all_current(Fact)


@pytest.mark.asyncio
async def test_t035_ac2_revision_stale_state_and_synthetic_cache_refuse(setup):
    extractor, registry, inputs, provider, runtime = setup
    result = await extractor.extract(("roll",))
    extractor.allow_synthetic = False
    with pytest.raises(SandboxError, match="Synthetic"):
        await extractor.extract(("roll",))
    extractor.allow_synthetic = True
    with registry.transaction() as state:
        state.event("stale", {"item_id": result.facts[0].fact_id})
    with pytest.raises(SandboxError, match="gate"):
        await extractor.extract(("roll",))
    assert len(provider.created) == 1


@pytest.mark.asyncio
async def test_t035_ac1_failure_during_stage_start_and_destroy_never_publishes(setup):
    extractor, registry, inputs, provider, runtime = setup
    stage = runtime.stage

    async def fail(*args):
        raise RuntimeError("synthetic adapter failure")

    runtime.stage = fail
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    runtime.stage = stage
    start = runtime.start
    runtime.start = fail
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    runtime.start = start
    destroy = provider.destroy

    async def destroyed_but_receipt_failed(box):
        await destroy(box)
        raise RuntimeError("synthetic destroy receipt failure")

    provider.destroy = destroyed_but_receipt_failed
    with pytest.raises(SandboxError, match="cleanup"):
        await extractor.extract(("roll",))
    assert provider.active == 0
    with registry.transaction() as state:
        assert not state.all_current(Fact)


@pytest.mark.asyncio
async def test_t035_ac2_om_page_anchors_keep_exact_bbox_quote_and_document(setup):
    from cre_brain.extraction.preparse.models import PageAnchor, ParsedPage, ParsedText

    extractor, registry, inputs, provider, runtime = setup
    src = source(registry.context.scope, doc_type="om_summary", values=("100", "200", "300"))
    texts = tuple(
        ParsedText(
            text_id=s.anchor_id,
            anchor=PageAnchor(
                doc_id="roll", page=1, bbox=(10.0, float(i * 20), 90.0, float(i * 20 + 10))
            ),
            text=str(value),
            provenance=Provenance(
                doc_id="roll",
                page=1,
                bbox=(10.0, float(i * 20), 90.0, float(i * 20 + 10)),
                quote=str(value),
            ),
        )
        for i, (s, value) in enumerate(zip(src.required, (100, 200, 300), strict=True))
    )
    doc = src.document.model_copy(
        update={
            "parser": "docling-native",
            "tables": (),
            "texts": texts,
            "pages": (ParsedPage(page=1, width=100.0, height=100.0),),
        }
    )
    src = src.model_copy(
        update={
            "document": doc,
            "parsed_sha256": hashlib.sha256(doc.model_dump_json().encode()).hexdigest(),
            "required": tuple(s.model_copy(update={"anchor_kind": "text"}) for s in src.required),
        }
    )
    inputs.docs["roll"] = runtime.docs["roll"] = src
    body = {
        "doc_type": "om_summary",
        "observations": [
            s.model_dump() | {"quote": t.text, "value": t.text}
            for s, t in zip(src.required, texts, strict=True)
        ],
    }
    runtime.override["roll"] = frames(body)
    result = await extractor.extract(("roll",))
    for fact, text in zip(result.facts, texts, strict=True):
        assert fact.provenance == [text.provenance]
        assert fact.value == Decimal(text.text)


@pytest.mark.asyncio
async def test_t035_ac2_model_numeric_literals_are_forbidden(setup):
    extractor, registry, inputs, provider, runtime = setup
    body = output(inputs.docs["roll"])
    body["observations"][0]["value"] = 100
    runtime.override["roll"] = frames(body)
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    with registry.transaction() as state:
        assert not state.all_current(Fact)


@pytest.mark.asyncio
async def test_t035_ac1_native_meter_cannot_underreport_completed_usage(setup):
    extractor, registry, inputs, provider, runtime = setup
    start = runtime.start

    async def underreported(*args):
        process = await start(*args)

        async def cancel():
            return CancellationReceipt(confirmed=True, total_tokens=0)

        process.cancel = cancel
        return process

    runtime.start = underreported
    with pytest.raises(SandboxError, match="cleanup"):
        await extractor.extract(("roll",))
    assert provider.active == 0
    with registry.transaction() as state:
        assert not state.all_current(Fact)


@pytest.mark.asyncio
async def test_t035_ac1_cleanup_cancelled_before_entry_blocks_retry(setup, monkeypatch):
    extractor, registry, inputs, provider, runtime = setup
    create_task = asyncio.create_task
    intercepted = False

    def cancel_cleanup(coro, *args, **kwargs):
        nonlocal intercepted
        task = create_task(coro, *args, **kwargs)
        if coro.__qualname__.endswith("_cleanup.<locals>.finish") and not intercepted:
            intercepted = True
            task.cancel()
        return task

    monkeypatch.setattr(asyncio, "create_task", cancel_cleanup)
    with pytest.raises(SandboxError, match="cleanup"):
        await extractor.extract(("roll",))
    assert intercepted
    with registry.transaction() as state:
        assert any(
            e.payload.get("category") == "extraction_cleanup_unverified" for e in state.history()
        )
        assert not state.all_current(Fact)
    with pytest.raises(SandboxError, match="recovery"):
        await extractor.extract(("roll",))
    assert len(provider.created) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["cancel", "destroy"])
async def test_t035_ac1_cleanup_cancellation_suppression_has_real_bound(
    setup, monkeypatch, operation
):
    extractor, registry, inputs, provider, runtime = setup
    release = asyncio.Event()
    entered = asyncio.Event()
    destroy_started = asyncio.Event()
    wait, wait_for = asyncio.wait, asyncio.wait_for

    async def short_wait(tasks, *, timeout=None, **kwargs):
        return await wait(tasks, timeout=min(timeout or 0.01, 0.01), **kwargs)

    async def short_wait_for(awaitable, timeout):
        return await wait_for(awaitable, min(timeout, 0.01))

    monkeypatch.setattr(asyncio, "wait", short_wait)
    monkeypatch.setattr(asyncio, "wait_for", short_wait_for)

    async def suppress_cancellation():
        entered.set()
        while not release.is_set():
            try:
                await release.wait()
            except asyncio.CancelledError:
                pass

    start, destroy = runtime.start, provider.destroy

    async def wrapped_start(*args):
        process = await start(*args)
        if operation == "cancel":

            async def cancel():
                await suppress_cancellation()
                return CancellationReceipt(confirmed=True, total_tokens=2)

            process.cancel = cancel
        return process

    async def wrapped_destroy(box):
        destroy_started.set()
        if operation == "destroy":
            await suppress_cancellation()
        await destroy(box)

    runtime.start, provider.destroy = wrapped_start, wrapped_destroy
    task = asyncio.create_task(extractor.extract(("roll",)))
    try:
        await wait({asyncio.create_task(entered.wait())}, timeout=1)
        done, pending = await wait({task}, timeout=0.15)
        bounded = task in done
        destruction_began = destroy_started.is_set()
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.sleep(0)
    assert bounded, "Cleanup waited beyond its bound for a cancellation-suppressing adapter"
    assert destruction_began, "Destruction must begin even when cancellation stays pending"
    with registry.transaction() as state:
        assert any(
            e.payload.get("category") == "extraction_cleanup_unverified" for e in state.history()
        )
        assert not state.all_current(Fact)
    with pytest.raises(SandboxError, match="recovery"):
        await extractor.extract(("roll",))
    assert len(provider.created) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("receipt_tokens", [0, 100])
async def test_t035_ac1_trailing_malformed_jsonl_preserves_observed_usage(setup, receipt_tokens):
    extractor, registry, inputs, provider, runtime = setup
    lines = frames(output(inputs.docs["roll"]))
    lines[-1] = (
        json.dumps(
            {"type": "turn.completed", "usage": {"input_tokens": 60, "output_tokens": 40}}
        ).encode()
        + b"\n"
    )
    runtime.override["roll"] = lines + [b"malformed\n"]
    start = runtime.start

    async def metered_start(*args):
        process = await start(*args)

        async def cancel():
            return CancellationReceipt(confirmed=True, total_tokens=receipt_tokens)

        process.cancel = cancel
        return process

    runtime.start = metered_start
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    with registry.transaction() as state:
        usage = sum(e.payload.get("host_tokens", 0) for e in state.history())
        assert usage >= 100
        assert not state.all_current(Fact)
        if receipt_tokens == 0:
            assert any(
                e.payload.get("category") == "extraction_cleanup_unverified"
                for e in state.history()
            )
    if receipt_tokens == 0:
        with pytest.raises(SandboxError, match="recovery"):
            await extractor.extract(("roll",))
        assert len(provider.created) == 1


@pytest.mark.asyncio
async def test_t035_ac1_unmetered_output_cannot_accept_zero_receipt(setup):
    extractor, registry, inputs, provider, runtime = setup
    lines = frames(output(inputs.docs["roll"]))
    runtime.override["roll"] = lines[:-1] + [b"malformed\n"]
    start = runtime.start

    async def unmetered_start(*args):
        process = await start(*args)

        async def cancel():
            return CancellationReceipt(confirmed=True, total_tokens=0)

        process.cancel = cancel
        return process

    runtime.start = unmetered_start
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    with pytest.raises(SandboxError, match="recovery"):
        await extractor.extract(("roll",))
    assert len(provider.created) == 1 and provider.active == 0


@pytest.mark.asyncio
async def test_t035_ac1_shared_budget_accounts_active_extraction_reservation(setup):
    from cre_brain.domain import AgentEvent
    from cre_brain.runner.segment import SegmentSpec, Workspace
    from cre_brain.runner.state_adapter import RunnerState

    extractor, registry, inputs, provider, runtime = setup
    registry.limits = registry.limits.model_copy(update={"max_tokens": extractor.limits.max_tokens})
    entered, release = asyncio.Event(), asyncio.Event()
    start = runtime.start

    async def paused_start(*args):
        entered.set()
        await release.wait()
        return await start(*args)

    runtime.start = paused_start
    task = asyncio.create_task(extractor.extract(("roll",)))
    try:
        async with asyncio.timeout(1):
            await entered.wait()
        ws = Workspace(box=Box(user_id="user", box_id="lead"), scope=registry.context.scope)
        seg = SegmentSpec(
            task_id="task",
            deal_id="deal",
            release_id="release",
            segment_no=0,
            prompt="Synthetic budget probe",
            max_turns=1,
            max_tokens=extractor.limits.max_tokens,
        )
        event = AgentEvent(
            event_id="budget-probe",
            task_id="task",
            seq=None,
            origin=("lead", 0, 0),
            ts=datetime.now(UTC),
            source="system",
            kind="segment_start",
            cause_id=None,
            release_id="release",
            runner="codex",
            payload={"max_tokens": seg.max_tokens},
        )
        with pytest.raises(SandboxError, match="budget"):
            RunnerState(registry).reserve(seg, ws, event)
        with registry.transaction() as state:
            attempt = next(
                e
                for e in state.history()
                if e.payload.get("binding") == "extraction_attempt"
                and e.payload.get("phase") == "start"
            )
            assert attempt.payload["reserved_tokens"] == extractor.limits.max_tokens
    finally:
        release.set()
        await task


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["cleanup", "gates", "cache"])
async def test_t035_ac3_publication_deadline_is_checked_at_commit(setup, monkeypatch, path):
    from datetime import timedelta

    import cre_brain.runner.tools.registry as registry_module
    from cre_brain.gates.service import GateService

    extractor, registry, inputs, provider, runtime = setup
    now = datetime.now(UTC)

    class Clock:
        @staticmethod
        def now(tz):
            return now

    monkeypatch.setattr(registry_module, "datetime", Clock)
    registry.limits = registry.limits.model_copy(update={"max_session_s": 1})
    cached = None
    if path == "cache":
        cached = await extractor.extract(("roll",))
        now = registry.context.started_at + timedelta(seconds=2)
    elif path == "cleanup":
        destroy = provider.destroy

        async def expired_destroy(box):
            nonlocal now
            await destroy(box)
            now = registry.context.started_at + timedelta(seconds=2)

        provider.destroy = expired_destroy
    else:
        check = GateService.check_bytes

        def expired_check(*args):
            nonlocal now
            result = check(*args)
            now = registry.context.started_at + timedelta(seconds=2)
            return result

        monkeypatch.setattr(GateService, "check_bytes", expired_check)
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    with registry.transaction() as state:
        assert {f.fact_id: f for f in state.all_current(Fact)} == (
            {f.fact_id: f for f in cached.facts} if cached else {}
        )
        bindings = [e for e in state.history() if e.payload.get("binding") == "extraction"]
        assert len(bindings) == (1 if cached else 0)
    assert provider.active == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["(100", "100)", "($100", "(+100)", "($+100)"])
async def test_t035_ac2_malformed_accounting_lexemes_refuse(setup, value):
    extractor, registry, inputs, provider, runtime = setup
    src = source(registry.context.scope, values=(value, "200", "300"))
    inputs.docs["roll"] = runtime.docs["roll"] = src
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    assert not provider.created
    with registry.transaction() as state:
        assert not state.all_current(Fact)


@pytest.mark.asyncio
async def test_t035_ac2_identical_source_resumes_with_original_known_at(setup):
    from datetime import timedelta

    extractor, registry, inputs, provider, runtime = setup
    first = await extractor.extract(("roll",))
    registry.context = registry.context.model_copy(
        update={
            "session_id": "resumed-host",
            "started_at": registry.context.started_at + timedelta(seconds=1),
        }
    )
    resumed = await extractor.extract(("roll",))
    assert resumed.facts == first.facts and resumed.snapshot == first.snapshot
    assert all(f.known_at < registry.context.started_at for f in resumed.facts)
    assert len(provider.created) == 1


@pytest.mark.asyncio
async def test_t035_ac1_non_openai_provider_refuses_before_runtime(setup):
    extractor, registry, inputs, provider, runtime = setup
    extractor.model_provider = "arbitrary-provider"
    with pytest.raises(SandboxError, match="OpenAI"):
        await extractor.extract(("roll",))
    assert not provider.created and not runtime.requests and not runtime.bundles


def test_t035_ac1_request_boundary_rejects_non_openai_provider(setup):
    from pydantic import ValidationError

    from cre_brain.extraction.runtime import ExtractionRequest

    extractor, registry, inputs, provider, runtime = setup
    bundle = extractor._bundle(inputs.docs["roll"])
    with pytest.raises(ValidationError):
        ExtractionRequest(
            argv=("codex", "exec"),
            model=registry.settings.models.roles["extraction"].model,
            model_provider="arbitrary-provider",
            bundle_sha256=bundle.sha256,
            parsed_sha256=bundle.parsed_sha256,
        )


@pytest.mark.asyncio
async def test_t035_ac1_shared_budget_releases_only_verified_unused_reservation(setup):
    from cre_brain.runner.state_adapter import token_commitment

    extractor, registry, inputs, provider, runtime = setup
    await extractor.extract(("roll",))
    with registry.transaction() as state:
        assert token_commitment(state.history()) == 2
        usage = [e for e in state.history() if "host_tokens" in e.payload]
        assert sum(e.payload["host_tokens"] for e in usage) == 2
        assert all(e.payload.get("extraction_attempt") for e in usage)


@pytest.mark.asyncio
async def test_t035_ac1_extraction_respects_active_lead_reservation(setup):
    from cre_brain.domain import AgentEvent
    from cre_brain.runner.segment import SegmentSpec, Workspace
    from cre_brain.runner.state_adapter import RunnerState

    extractor, registry, inputs, provider, runtime = setup
    registry.limits = registry.limits.model_copy(update={"max_tokens": extractor.limits.max_tokens})
    ws = Workspace(box=Box(user_id="user", box_id="lead"), scope=registry.context.scope)
    seg = SegmentSpec(
        task_id="task",
        deal_id="deal",
        release_id="release",
        segment_no=0,
        prompt="Synthetic reverse budget probe",
        max_turns=1,
        max_tokens=extractor.limits.max_tokens,
    )
    event = AgentEvent(
        event_id="lead-budget-probe",
        task_id="task",
        seq=None,
        origin=("lead", 0, 0),
        ts=datetime.now(UTC),
        source="system",
        kind="segment_start",
        cause_id=None,
        release_id="release",
        runner="codex",
        payload={"max_tokens": seg.max_tokens},
    )
    RunnerState(registry).reserve(seg, ws, event)
    with pytest.raises(SandboxError, match="budget"):
        await extractor.extract(("roll",))
    assert not provider.created


@pytest.mark.asyncio
async def test_t035_ac2_resume_cannot_change_original_known_at_binding(setup, monkeypatch):
    from datetime import timedelta

    from cre_brain.runner.tools.state import ToolState

    extractor, registry, inputs, provider, runtime = setup
    first = await extractor.extract(("roll",))
    fact = first.facts[0]
    changed = fact.model_copy(update={"known_at": fact.known_at - timedelta(days=1)})
    current = ToolState.current

    def altered_read(self, model, identity):
        stored = current(self, model, identity)
        return changed if model is Fact and identity == fact.fact_id else stored

    # Simulate a mismatched backend read without changing append-only stored rows.
    monkeypatch.setattr(ToolState, "current", altered_read)
    registry.context = registry.context.model_copy(
        update={"session_id": "resumed-host", "started_at": datetime.now(UTC)}
    )
    with pytest.raises(SandboxError):
        await extractor.extract(("roll",))
    assert len(provider.created) == 1
