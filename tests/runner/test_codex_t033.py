"""Synthetic, in-memory provider JSONL: plumbing only, never live/quality evidence."""

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from typer.testing import CliRunner

from cre_brain.cli import create_app
from cre_brain.config import load
from cre_brain.domain import Deliverable, DeliverableKind, GateResult
from cre_brain.domain.base import TenantScope
from cre_brain.runner.codex import CodexRunner
from cre_brain.runner.fake import FakeRunner, ReplayError
from cre_brain.runner.normalizer import EventInputError, Normalizer, Sanitizer
from cre_brain.runner.policy import HostContext
from cre_brain.runner.record import RecordError, load_recording, record_segment
from cre_brain.runner.segment import SegmentSpec, Workspace
from cre_brain.runner.streaming import CancellationReceipt, RuntimeCapabilities
from cre_brain.runner.tools.contracts import Artifact
from cre_brain.runner.tools.registry import ToolRegistry
from cre_brain.sandbox.base import Box, SandboxError
from cre_brain.state.events import EventStore
from cre_brain.state.schema import metadata
from cre_brain.state.store import SqlVersionedStore


class Inputs:
    def __init__(self):
        self.artifacts = {}

    def fact(self, context, identity):
        return None

    def artifact(self, context, identity):
        return self.artifacts.get(identity)

    def template(self, context, identity):
        return None

    def rule_policy(self, context, table):
        return None


class Gates:
    def __init__(self, scope):
        self.scope = scope

    def check(self, name, deliverable):
        return GateResult(passed=True, failures=[], metrics={})

    def check_bytes(self, name, deliverable, snapshot):
        return self.check(name, deliverable)


class BufferedProvider:
    """All provider exec attempts are forbidden, including a host fallback."""

    async def exec(self, *args):
        raise AssertionError("Buffered provider must never execute analyst commands")


class Process:
    def __init__(self, lines, *, hang=False):
        self.lines = lines
        self.cancelled = False
        self.cancel_confirmed = True
        self.hang = hang
        self.metered_tokens = 0

    async def stdout(self):
        for line in self.lines:
            try:
                body = json.loads(line)
                if body.get("type") == "turn.completed":
                    usage = body.get("usage", {})
                    self.metered_tokens += usage.get("input_tokens", 0) + usage.get(
                        "output_tokens", 0
                    )
            except (ValueError, AttributeError):
                pass
            yield line
        if self.hang:
            await asyncio.Event().wait()

    async def wait(self):
        return 0

    async def cancel(self):
        self.cancelled = True
        return CancellationReceipt(
            confirmed=self.cancel_confirmed, total_tokens=self.metered_tokens
        )


class Streaming:
    """Synthetic trusted adapter, deliberately incapable of claiming live evidence."""

    def __init__(self, provider, registry, lines=(), *, hang=False):
        self.provider = provider
        self.registry = registry
        self.process = Process(lines, hang=hang)
        self.assets = None
        self.request = None
        self.caps = RuntimeCapabilities(
            evidence="synthetic_plumbing_only",
            cli_version="synthetic-cli",
            isolated=True,
            authenticated=True,
            configuration_verified=True,
            hard_caps=True,
            resume_supported=True,
        )

    async def capabilities(self, box):
        return self.caps

    async def stage(self, box, bundle):
        self.assets = bundle

    async def start(self, box, request):
        self.request = request
        return self.process


def raw(*events):
    return [json.dumps(event).encode() + b"\n" for event in events]


def provider_events(session="provider-session", tokens=9):
    return raw(
        {"type": "thread.started", "thread_id": session},
        {"type": "turn.started"},
        {"type": "item.completed", "item": {"id": "m1", "type": "agent_message", "text": "Ready"}},
        {
            "type": "turn.completed",
            "usage": {"input_tokens": tokens, "cached_input_tokens": 3, "output_tokens": 2},
        },
    )


@pytest.fixture
def setup(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'state.db'}")
    metadata.create_all(engine)
    context = HostContext(
        scope=TenantScope(user_id="synthetic-user", firm_id="synthetic-firm"),
        task_id="synthetic-task",
        deal_id="synthetic-deal",
        role="lead",
        session_id="host-session",
        release_id="synthetic-release",
        started_at=datetime.now(UTC),
    )
    root = tmp_path / "workspace"
    root.mkdir()
    inputs = Inputs()
    registry = ToolRegistry(
        engine=engine,
        context=context,
        workspace=root,
        inputs=inputs,
        settings=load(apply_environment=False),
    )
    provider = BufferedProvider()
    ws = Workspace(
        box=Box(user_id=context.scope.user_id, box_id="synthetic-box"), scope=context.scope
    )
    seg = SegmentSpec(
        task_id=context.task_id,
        deal_id=context.deal_id,
        release_id=context.release_id,
        segment_no=0,
        prompt="Synthetic plumbing request",
        max_turns=3,
        max_tokens=100,
    )
    yield registry, inputs, provider, ws, seg
    engine.dispose()


def build(setup, lines=None, **kwargs):
    registry, _, provider, _, _ = setup
    runtime = Streaming(provider, registry, provider_events() if lines is None else lines, **kwargs)
    runner = CodexRunner(
        provider=provider,
        runtime=runtime,
        registry=registry,
        brain_root=Path("brain").absolute(),
        model_provider="configured-provider",
    )
    return runner, runtime


async def collect(runner, seg, ws, policy):
    return [event async for event in runner.run_segment(seg, ws, policy)]


@pytest.mark.asyncio
async def test_t033_ac1_codex_generated_assets_usage_and_append_only_scope(setup):
    registry, _, _, ws, seg = setup
    runner, runtime = build(setup)
    result = await collect(runner, seg, ws, registry.context)
    assert runtime.request.argv[:3] == ("codex", "exec", "--json")
    assert runtime.request.cwd == f"/home/agent/work/deals/{seg.deal_id}"
    assert runtime.request.model == registry.settings.models.roles["lead"].model
    assert runtime.request.model_provider == "configured-provider"
    assert "AGENTS.md" in runtime.assets.files
    assert "Deliverable catalog" in runtime.assets.files["AGENTS.md"].decode()
    assert any(name.startswith(".agents/skills/") for name in runtime.assets.files)
    config = runtime.assets.files[".codex/config.toml"].decode()
    assert "[mcp_servers.cre]" in config
    assert "auth.json" not in runtime.assets.files
    assert all("raw" not in name and "eval" not in name for name in runtime.assets.files)
    usage = [e for e in result if e.kind == "usage"]
    assert len(usage) == 1
    assert usage[0].payload["host_tokens"] == 11  # cached input is a subset, not added again
    assert usage[0].payload["cached_input_tokens"] == 3
    assert usage[0].payload["session_id"] == "provider-session"
    assert result[-1].kind == "segment_end"
    assert result[-1].payload["reason"] == "completed"
    store = EventStore(registry.engine)
    assert store.list(seg.task_id, scope=ws.scope) == result
    assert store.append(result[0], scope=ws.scope) == result[0]
    other = TenantScope(user_id="other-user", firm_id=ws.scope.firm_id)
    assert store.list(seg.task_id, scope=other) == []
    with pytest.raises(SandboxError, match="scope"):
        await collect(runner, seg, ws.model_copy(update={"scope": other}), registry.context)


@pytest.mark.parametrize(
    "line",
    [
        b'{"type":"turn.started","type":"turn.completed"}\n',
        b"[]\n",
        b'{"type":NaN}\n',
        b"not json\n",
        b"\xff\n",
        b'{"type":"turn.started"}',
        b'{"type":"turn.completed","usage":{"input_tokens":true,"output_tokens":1}}\n',
        b'{"type":"turn.completed","usage":{"input_tokens":2,"cached_input_tokens":3,"output_tokens":1}}\n',
        b'{"type":"thread.started","thread_id":"../escape"}\n',
        b'{"type":"x","nested":' + b"[" * 25 + b"0" + b"]" * 25 + b"}\n",
        b"x" * 131073,
    ],
)
def test_t033_ac1_codex_hostile_jsonl_rejected_without_echo(setup, line):
    _, _, _, ws, seg = setup
    normalizer = Normalizer(seg, ws, Sanitizer(("private-secret",)))
    with pytest.raises(EventInputError) as error:
        normalizer.feed(line)
    assert "private-secret" not in str(error.value)
    assert "escape" not in str(error.value)


def test_t033_ac1_codex_redacts_unknown_events_and_nested_credentials(setup):
    _, _, _, ws, seg = setup
    normalizer = Normalizer(seg, ws, Sanitizer(("private-secret",)))
    frame = normalizer.feed(
        raw(
            {
                "type": "future.event",
                "payload": {
                    "api_key": "credential",
                    "text": "private-secret Bearer credential",
                    "token": "credential",
                },
            }
        )[0]
    )
    serialized = json.dumps(frame.raw) + "".join(e.model_dump_json() for e in frame.events)
    assert "private-secret" not in serialized
    assert "credential" not in serialized
    assert frame.events[0].kind == "runner_raw"
    assert frame.events[0].payload["unsupported"] is True


@pytest.mark.asyncio
async def test_t033_ac2_codex_resume_uses_persisted_session_and_caps(setup):
    registry, _, _, ws, seg = setup
    runner, _ = build(setup)
    await collect(runner, seg, ws, registry.context)
    resumed = seg.model_copy(update={"segment_no": 1, "resume_session_id": "provider-session"})
    runner2, runtime = build(setup, provider_events(tokens=5))
    events = await collect(runner2, resumed, ws, registry.context)
    assert runtime.request.argv[:3] == ("codex", "exec", "resume")
    assert "provider-session" in runtime.request.argv
    assert runtime.request.max_tokens == 100
    assert runtime.request.max_turns == 3
    assert runtime.request.timeout_s <= registry.settings.budget.segment_max_min * 60
    assert events[0].kind == "segment_start"
    wrong = resumed.model_copy(update={"resume_session_id": "unbound-session", "segment_no": 2})
    with pytest.raises(SandboxError, match="session"):
        await collect(runner2, wrong, ws, registry.context)


@pytest.mark.asyncio
@pytest.mark.parametrize("cap", ["tokens", "turns", "bytes", "malformed", "session"])
async def test_t033_ac2_codex_cap_cancel_and_fail_stop(setup, cap):
    registry, _, _, ws, seg = setup
    lines = provider_events()
    if cap == "tokens":
        seg = seg.model_copy(update={"max_tokens": 10})
    elif cap == "turns":
        seg = seg.model_copy(update={"max_turns": 1})
    elif cap == "bytes":
        lines = [b"x" * 131073]
    elif cap == "malformed":
        lines = [b'{"type":"turn.completed","usage":{}}\n']
    else:
        lines = raw(
            {"type": "thread.started", "thread_id": "first"},
            {"type": "thread.started", "thread_id": "second"},
        )
    runner, runtime = build(setup, lines)
    events = await collect(runner, seg, ws, registry.context)
    assert runtime.process.cancelled
    assert events[-1].kind == "segment_end"
    assert events[-1].payload["reason"] in {"budget", "invalid_event"}
    assert any(e.kind in {"budget", "error"} for e in events)


@pytest.mark.asyncio
async def test_t033_ac2_codex_timeout_cancel_and_consumer_close(setup):
    registry, _, _, ws, seg = setup
    runner, runtime = build(setup, [], hang=True)
    seg = seg.model_copy(update={"timeout_s": 0.02})
    events = await collect(runner, seg, ws, registry.context)
    assert runtime.process.cancelled
    assert events[-1].payload["reason"] == "budget"
    runner2, runtime2 = build(setup)
    stream = runner2.run_segment(seg.model_copy(update={"segment_no": 1}), ws, registry.context)
    await anext(stream)
    await stream.aclose()
    assert runtime2.process.cancelled


@pytest.mark.asyncio
@pytest.mark.parametrize("unavailable", ["missing", "auth", "caps", "isolation", "config"])
async def test_t033_ac3_codex_record_refuses_unavailable_runtime(setup, tmp_path, unavailable):
    registry, _, provider, ws, seg = setup
    runner, runtime = build(setup)
    if unavailable == "missing":
        runner = CodexRunner(
            provider=provider,
            registry=registry,
            brain_root=Path("brain").absolute(),
            model_provider="configured-provider",
        )
    else:
        field = {
            "auth": "authenticated",
            "caps": "hard_caps",
            "isolation": "isolated",
            "config": "configuration_verified",
        }[unavailable]
        runtime.caps = runtime.caps.model_copy(update={field: False})
    output = tmp_path / "refused-recording"
    with pytest.raises(SandboxError):
        await record_segment(runner, seg, ws, registry.context, output)
    assert not output.exists()
    assert runtime.request is None


@pytest.mark.asyncio
async def test_t033_ac3_codex_synthetic_manifest_hashes_and_tampering(setup, tmp_path):
    registry, _, _, ws, seg = setup
    runner, _ = build(setup)
    output = tmp_path / "synthetic-plumbing-only"
    manifest = await record_segment(runner, seg, ws, registry.context, output)
    assert manifest.evidence == "synthetic_plumbing_only"
    assert manifest.release_id == seg.release_id
    assert manifest.codex_cli_version == "synthetic-cli"
    assert manifest.raw_sha256 == hashlib.sha256((output / "raw.jsonl").read_bytes()).hexdigest()
    assert (
        manifest.events_sha256 == hashlib.sha256((output / "events.jsonl").read_bytes()).hexdigest()
    )
    assert manifest.session_id == "provider-session"
    assert load_recording(output, release_id=seg.release_id).manifest == manifest
    with pytest.raises(RecordError):
        load_recording(output, release_id="different-release")
    (output / "events.jsonl").write_bytes(b"{}\n")
    with pytest.raises(RecordError, match="hash"):
        load_recording(output, release_id=seg.release_id)


def test_t033_ac3_codex_cli_register_preserves_commands_and_refuses_no_host():
    result = CliRunner().invoke(create_app(), ["--help"])
    assert result.exit_code == 0
    for name in ("record", "knowledge", "evals", "tool", "mcp"):
        assert name in result.stdout
    generator = CliRunner().invoke(create_app(), ["evals", "--help"])
    assert generator.exit_code == 0
    assert "gen" in generator.stdout
    result = CliRunner().invoke(
        create_app(), ["record", "--request", "synthetic request", "--output", "ignored"]
    )
    assert result.exit_code == 1
    assert "missing_runtime" in result.stdout


@pytest.mark.requires_codex
@pytest.mark.asyncio
async def test_t033_ac3_codex_live_record_no_host_fallback(setup, tmp_path):
    """Live prerequisite marker; unavailable restricted adapter must still refuse.

    This is a refusal contract, not a live analyst execution/evidence claim.
    """
    registry, _, provider, ws, seg = setup
    runner = CodexRunner(
        provider=provider,
        registry=registry,
        brain_root=Path("brain").absolute(),
        model_provider="configured-provider",
    )
    with pytest.raises(SandboxError, match="streaming"):
        await record_segment(runner, seg, ws, registry.context, tmp_path / "no-live-record")


def draft(setup):
    registry, inputs, _, _, _ = setup
    path = registry.workspace / "deals" / registry.context.deal_id / "deliverables" / "memo.md"
    path.parent.mkdir(parents=True)
    path.write_text("Synthetic plumbing artifact without numbers.")
    d = Deliverable(
        d_id="memo",
        deal_ids=[registry.context.deal_id],
        kind=DeliverableKind.SCREEN,
        version=1,
        status="draft",
        path=str(path),
        gate_results=[],
        depends_on=[],
    )
    SqlVersionedStore(registry.engine, Deliverable).append(d, scope=registry.context.scope)
    inputs.artifacts[d.d_id] = Artifact(
        deliverable=d, sha256=hashlib.sha256(path.read_bytes()).hexdigest()
    )
    registry.gates = Gates(registry.context.scope)
    return d


@pytest.mark.asyncio
async def test_t033_ac4_fake_replay_real_tools_loose_ids_and_final_state(setup, tmp_path):
    registry, _, _, ws, seg = setup
    draft(setup)
    lines = raw(
        {"type": "thread.started", "thread_id": "provider-session"},
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {
                "id": "recorded-call",
                "type": "mcp_tool_call",
                "server": "cre",
                "tool": "finalize_deliverable",
                "arguments": {"deliverable_id": "memo"},
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "status": "ok",
                                    "data": {
                                        "deliverable_id": "different-recorded-id",
                                        "status": "final",
                                        "version": 2,
                                    },
                                }
                            ),
                        }
                    ]
                },
                "status": "completed",
            },
        },
        {"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}},
    )
    runner, _ = build(setup, lines)
    output = tmp_path / "synthetic-replay"
    await record_segment(runner, seg, ws, registry.context, output, expected_deliverables=("memo",))
    fake = FakeRunner(output, registry=registry)
    result = await collect(fake, seg.model_copy(update={"segment_no": 1}), ws, registry.context)
    assert any(e.kind == "tool_result" for e in result)
    assert result[-1].payload["plumbing_only"] is True
    current = SqlVersionedStore(registry.engine, Deliverable).get("memo", scope=ws.scope)
    assert current.status == "final"
    assert all(g.passed for g in current.gate_results)
    Path(current.path).write_text("tampered artifact")
    with pytest.raises(ReplayError):
        await collect(fake, seg.model_copy(update={"segment_no": 2}), ws, registry.context)


@pytest.mark.asyncio
async def test_t033_ac4_fake_unsupported_events_and_empty_final_state_fail(setup, tmp_path):
    registry, _, _, ws, seg = setup
    runner, _ = build(setup, provider_events() + raw({"type": "future.event"}))
    output = tmp_path / "unsupported-synthetic"
    await record_segment(runner, seg, ws, registry.context, output)
    with pytest.raises(ReplayError, match="unsupported"):
        await collect(FakeRunner(output, registry=registry), seg, ws, registry.context)
    runner2, _ = build(setup)
    output2 = tmp_path / "empty-synthetic"
    await record_segment(
        runner2, seg.model_copy(update={"segment_no": 1}), ws, registry.context, output2
    )
    with pytest.raises(ReplayError, match="final state"):
        await collect(FakeRunner(output2, registry=registry), seg, ws, registry.context)


@pytest.mark.asyncio
async def test_t033_ac2_codex_unconfirmed_cancellation_blocks_resume(setup):
    registry, _, _, ws, seg = setup
    runner, runtime = build(setup)
    runtime.process.cancel_confirmed = False
    capped = seg.model_copy(update={"max_turns": 1})
    with pytest.raises(SandboxError, match="cleanup_unverified"):
        await collect(runner, capped, ws, registry.context)
    history = EventStore(registry.engine).list(seg.task_id, scope=ws.scope)
    assert any(e.payload.get("category") == "cleanup_unverified" for e in history)
    assert not any(e.kind == "segment_end" for e in history)
    runner2, runtime2 = build(setup)
    with pytest.raises(SandboxError, match="recovery"):
        await collect(runner2, seg.model_copy(update={"segment_no": 1}), ws, registry.context)
    assert runtime2.request is None


@pytest.mark.asyncio
async def test_t033_ac2_codex_durable_usage_budget_and_duplicate_segment(setup):
    registry, _, _, ws, seg = setup
    runner, _ = build(setup)
    await collect(runner, seg, ws, registry.context)
    with pytest.raises(SandboxError, match="increase"):
        await collect(runner, seg, ws, registry.context)
    registry.limits = registry.limits.model_copy(update={"max_tokens": 15})
    runner2, runtime2 = build(setup)
    with pytest.raises(SandboxError, match="budget"):
        await collect(
            runner2, seg.model_copy(update={"segment_no": 1, "max_tokens": 5}), ws, registry.context
        )
    assert runtime2.request is None
    history = EventStore(registry.engine).list(seg.task_id, scope=ws.scope)
    assert sum(e.payload.get("host_tokens", 0) for e in history) == 11


@pytest.mark.asyncio
async def test_t033_ac2_codex_stop_only_for_authoritative_state(setup):
    registry, _, _, ws, seg = setup
    runner, runtime = build(setup)
    original = runtime.process.stdout

    async def authoritative_stream():
        async for line in original():
            if b"turn.started" in line:
                with registry.transaction() as state:
                    state.event("confirmation_request", {"cid": "synthetic-confirmation"})
            yield line

    runtime.process.stdout = authoritative_stream
    events = await collect(runner, seg, ws, registry.context)
    assert runtime.process.cancelled
    assert events[-1].payload["reason"] == "confirmation"
    assert not any(e.kind == "usage" for e in events)


@pytest.mark.asyncio
async def test_t033_ac3_codex_record_secrets_source_hash_and_no_overwrite(setup, tmp_path):
    registry, _, _, ws, seg = setup
    lines = provider_events() + raw({"type": "unknown.event", "api_key": "planted-secret"})
    runner, _ = build(setup, lines)
    runner.sanitizer = Sanitizer(("planted-secret",))
    output = tmp_path / "synthetic-secret-capture"
    manifest = await record_segment(runner, seg, ws, registry.context, output)
    assert manifest.source_raw_sha256 == hashlib.sha256(b"".join(lines)).hexdigest()
    assert manifest.source_raw_sha256 != manifest.raw_sha256
    for file in output.iterdir():
        assert b"planted-secret" not in file.read_bytes()
    before = {file.name: file.read_bytes() for file in output.iterdir()}
    with pytest.raises(RecordError, match="new recording"):
        await record_segment(runner, seg, ws, registry.context, output, refresh=True)
    assert before == {file.name: file.read_bytes() for file in output.iterdir()}


@pytest.mark.asyncio
async def test_t033_ac3_codex_manifest_metadata_tampering_and_symlink(setup, tmp_path):
    registry, _, _, ws, seg = setup
    runner, _ = build(setup)
    output = tmp_path / "synthetic-manifest"
    await record_segment(runner, seg, ws, registry.context, output)
    manifest_path = output / "manifest.json"
    content = manifest_path.read_bytes()
    forged = json.loads(content)
    forged["codex_cli_version"] = "altered"
    manifest_path.write_text(json.dumps(forged))  # synthetic attacker fixture, never production
    with pytest.raises(RecordError, match="hash"):
        load_recording(output, release_id=seg.release_id)
    manifest_path.write_bytes(content)
    link = tmp_path / "recording-link"
    link.symlink_to(output, target_is_directory=True)
    with pytest.raises(RecordError):
        load_recording(link, release_id=seg.release_id)


@pytest.mark.asyncio
async def test_t033_ac3_codex_synthetic_capture_cannot_enter_transcripts(setup, tmp_path):
    registry, _, _, ws, seg = setup
    runner, _ = build(setup)
    directory = tmp_path / "transcripts"
    directory.mkdir()
    with pytest.raises(RecordError, match="Synthetic"):
        await record_segment(runner, seg, ws, registry.context, directory / "synthetic")
    assert not (directory / "synthetic").exists()


@pytest.mark.asyncio
async def test_t033_ac4_fake_host_id_adapter_and_key_matching(setup, tmp_path):
    registry, _, _, ws, seg = setup
    draft(setup)
    lines = raw(
        {"type": "thread.started", "thread_id": "provider-session"},
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {
                "id": "arbitrary-provider-id",
                "type": "mcp_tool_call",
                "server": "cre",
                "tool": "finalize_deliverable",
                "arguments": {"deliverable_id": "old-artifact-id"},
                "result": {"content": [{"type": "text", "text": '{"status":"ok","data":{}}'}]},
                "status": "completed",
            },
        },
        {"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}},
    )
    runner, _ = build(setup, lines)
    output = tmp_path / "synthetic-id-adaptation"
    await record_segment(
        runner, seg, ws, registry.context, output, expected_deliverables=("old-artifact-id",)
    )

    class BadMapping:
        def arguments(self, tool, recorded):
            return {"wrong_key": "memo"}

        def deliverable_id(self, recorded):
            return "memo"

    with pytest.raises(ReplayError, match="argument keys"):
        await collect(
            FakeRunner(output, registry=registry, arguments=BadMapping()),
            seg.model_copy(update={"segment_no": 1}),
            ws,
            registry.context,
        )
    current = SqlVersionedStore(registry.engine, Deliverable).get("memo", scope=ws.scope)
    assert current.status == "draft"

    class Mapping(BadMapping):
        def arguments(self, tool, recorded):
            return {"deliverable_id": "memo"}

    events = await collect(
        FakeRunner(output, registry=registry, arguments=Mapping()),
        seg.model_copy(update={"segment_no": 1}),
        ws,
        registry.context,
    )
    assert events[-1].payload["reason"] == "replayed"


@pytest.mark.asyncio
async def test_t033_ac4_fake_manifest_binding_survives_rehashed_tampering(setup, tmp_path):
    from cre_brain.runner.record import RecordingManifest

    registry, _, _, ws, seg = setup
    runner, _ = build(setup)
    output = tmp_path / "synthetic-rehashed-attack"
    await record_segment(runner, seg, ws, registry.context, output)
    path = output / "manifest.json"
    manifest = RecordingManifest.model_validate_json(path.read_bytes())
    changed = manifest.model_copy(update={"expected_deliverables": ("forged-id",)})
    changed = changed.model_copy(update={"manifest_sha256": changed.checksum()})
    path.write_text(changed.model_dump_json())  # synthetic attacker fixture only
    with pytest.raises(ReplayError, match="trusted manifest"):
        await collect(
            FakeRunner(output, registry=registry),
            seg.model_copy(update={"segment_no": 1}),
            ws,
            registry.context,
        )


@pytest.mark.asyncio
async def test_t033_ac2_codex_cancellation_receipt_accounts_unreported_usage(setup):
    from cre_brain.runner.streaming import CancellationReceipt

    registry, _, _, ws, seg = setup
    runner, runtime = build(setup, [], hang=True)

    async def cancel_receipt():
        runtime.process.cancelled = True
        return CancellationReceipt(confirmed=True, total_tokens=6)

    runtime.process.cancel = cancel_receipt
    events = await collect(runner, seg.model_copy(update={"timeout_s": 0.02}), ws, registry.context)
    assert events[-1].payload["tokens"] == 6
    assert events[-1].payload["usage_complete"] is True
    history = EventStore(registry.engine).list(seg.task_id, scope=ws.scope)
    assert sum(e.payload.get("host_tokens", 0) for e in history) == 6


@pytest.mark.asyncio
async def test_t033_ac2_codex_unmetered_cancel_refuses_next_segment(setup):
    from cre_brain.runner.streaming import CancellationReceipt

    registry, _, _, ws, seg = setup
    runner, runtime = build(setup, [], hang=True)

    async def unmetered():
        return CancellationReceipt(confirmed=True, total_tokens=None)

    runtime.process.cancel = unmetered
    events = await collect(runner, seg.model_copy(update={"timeout_s": 0.02}), ws, registry.context)
    assert events[-1].payload["usage_complete"] is False
    runner2, runtime2 = build(setup)
    with pytest.raises(SandboxError, match="usage"):
        await collect(runner2, seg.model_copy(update={"segment_no": 1}), ws, registry.context)
    assert runtime2.request is None


@pytest.mark.asyncio
async def test_t033_ac2_codex_existing_policy_deadline_limits_runtime(setup):
    from datetime import timedelta

    registry, _, _, ws, seg = setup
    registry.context = registry.context.model_copy(
        update={"started_at": datetime.now(UTC) - timedelta(seconds=9)}
    )
    registry.limits = registry.limits.model_copy(update={"max_session_s": 10})
    runner, runtime = build(setup)
    await collect(runner, seg, ws, registry.context)
    assert 0 < runtime.request.timeout_s <= 1


@pytest.mark.asyncio
@pytest.mark.parametrize("unmetered", [False, True])
async def test_t033_ac2_parent_cancel_during_cleanup_is_propagated(setup, unmetered):
    registry, _, _, ws, seg = setup
    runner, runtime = build(setup)
    started = asyncio.Event()
    finish = asyncio.Event()

    async def receipt():
        started.set()
        await finish.wait()
        runtime.process.cancelled = True
        return CancellationReceipt(
            confirmed=True, total_tokens=None if unmetered else runtime.process.metered_tokens
        )

    runtime.process.cancel = receipt
    if unmetered:
        seg = seg.model_copy(update={"max_tokens": 1})
    task = asyncio.create_task(collect(runner, seg, ws, registry.context))
    await asyncio.wait_for(started.wait(), 1)
    task.cancel()
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert runtime.process.cancelled
    history = EventStore(registry.engine).list(seg.task_id, scope=ws.scope)
    assert history[-1].kind == "segment_end"
    assert history[-1].payload["reason"] == "interrupted"
    assert history[-1].payload["usage_complete"] is (not unmetered)


@pytest.mark.asyncio
async def test_t033_ac2_deadline_during_budget_cleanup_remains_budget_stop(setup):
    registry, _, _, ws, seg = setup
    runner, runtime = build(setup)

    async def receipt():
        await asyncio.sleep(0.05)
        runtime.process.cancelled = True
        return CancellationReceipt(confirmed=True, total_tokens=runtime.process.metered_tokens)

    runtime.process.cancel = receipt
    events = await collect(
        runner, seg.model_copy(update={"max_tokens": 1, "timeout_s": 0.02}), ws, registry.context
    )
    assert events[-1].payload["reason"] == "budget"
    assert events[-1].payload["usage_complete"] is True
    assert any(e.kind == "budget" and e.payload["cap"] == "wallclock" for e in events)


def test_t033_ac3_sanitizer_scrubs_embedded_json_and_escaped_registered_secret():
    secret = 'registered"crédential'
    for ensure_ascii in (True, False):
        value = json.dumps(
            {"password": "credential value", "note": secret}, ensure_ascii=ensure_ascii
        )
        scrubbed = Sanitizer((secret,)).text(value)
        assert "credential value" not in scrubbed
        assert secret not in scrubbed
        assert json.loads(scrubbed)["note"] == "[REDACTED]"
        assert scrubbed.count("[REDACTED]") == 2


def test_t033_ac3_sanitizer_decodes_registered_secrets_in_embedded_json():
    secret = 'registered"crédential'
    escaped = "".join(f"\\u{ord(char):04X}" for char in secret)
    value = '{"note":"' + escaped + '"}'
    sanitizer = Sanitizer((secret,))
    assert json.loads(sanitizer.text(value))["note"] == "[REDACTED]"
    nested = json.dumps({"note": value})
    assert json.loads(json.loads(sanitizer.text(nested))["note"])["note"] == "[REDACTED]"


def test_t033_ac3_sanitizer_decodes_json_arrays_and_string_literals():
    secret = 'registered"crédential'
    literal = '"' + "".join(f"\\u{ord(char):04X}" for char in secret) + '"'
    sanitizer = Sanitizer((secret,))
    assert json.loads(sanitizer.text(literal)) == "[REDACTED]"
    assert json.loads(sanitizer.text("[" + literal + "]")) == ["[REDACTED]"]


def test_t033_ac3_sanitizer_redacts_rejected_structured_text_entirely():
    secret = 'registered"crédential'
    literal = '"' + "".join(f"\\u{ord(char):04X}" for char in secret) + '"'
    sanitizer = Sanitizer((secret,))
    for value in (
        '{"note":' + literal + ',"x":1,"x":2}',
        '{},"note":' + literal,
        "[" * 25 + literal + "]" * 25,
        '{"note":' + literal,
    ):
        assert sanitizer.text(value) == "[REDACTED]"


@pytest.mark.asyncio
async def test_t033_ac1_generated_config_disables_ambient_plugin_and_agent_loading(setup):
    import tomllib

    registry, _, _, ws, seg = setup
    runner, runtime = build(setup)
    await collect(runner, seg, ws, registry.context)
    config = tomllib.loads(runtime.assets.files[".codex/config.toml"].decode())
    for feature in ("plugins", "apps", "multi_agent", "skill_mcp_dependency_install"):
        assert config["features"][feature] is False
    assert set(config["mcp_servers"]) == {"cre"}


@pytest.mark.asyncio
async def test_t033_ac2_reservation_cannot_extend_canonical_deadline(setup, monkeypatch):
    import time

    from cre_brain.runner.state_adapter import RunnerState

    registry, _, _, ws, seg = setup
    original = RunnerState.reserve

    def slow_reserve(self, *args):
        time.sleep(0.03)
        return original(self, *args)

    monkeypatch.setattr(RunnerState, "reserve", slow_reserve)
    runner, runtime = build(setup)
    events = await collect(runner, seg.model_copy(update={"timeout_s": 0.01}), ws, registry.context)
    assert runtime.request is None
    assert events[-1].kind == "segment_end"
    assert events[-1].payload["reason"] == "budget"


@pytest.mark.asyncio
async def test_t033_ac2_adapter_receives_time_remaining_after_staging(setup):
    registry, _, _, ws, seg = setup
    runner, runtime = build(setup)
    original_stage = runtime.stage

    async def slow_stage(*args):
        await asyncio.sleep(0.03)
        await original_stage(*args)

    runtime.stage = slow_stage
    await collect(runner, seg.model_copy(update={"timeout_s": 0.1}), ws, registry.context)
    assert 0 < runtime.request.timeout_s < 0.09


@pytest.mark.asyncio
async def test_t033_ac2_repeated_cancellation_cannot_interrupt_cleanup(setup):
    registry, _, _, ws, seg = setup
    runner, runtime = build(setup, [], hang=True)
    started = asyncio.Event()
    finished = asyncio.Event()
    runtime.process.alive = True

    async def slow_cancel():
        started.set()
        await asyncio.sleep(0.03)
        runtime.process.alive = False
        finished.set()
        return CancellationReceipt(confirmed=True, total_tokens=0)

    runtime.process.cancel = slow_cancel
    consumer = asyncio.create_task(collect(runner, seg, ws, registry.context))
    await asyncio.sleep(0.01)
    consumer.cancel()
    await asyncio.wait_for(started.wait(), 0.1)
    consumer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await consumer
    await asyncio.wait_for(finished.wait(), 0.1)
    assert runtime.process.alive is False


@pytest.mark.asyncio
async def test_t033_ac2_runtime_cancelled_cleanup_refuses_without_hanging(setup):
    registry, _, _, ws, seg = setup
    runner, runtime = build(setup)

    async def cancelled_cleanup():
        raise asyncio.CancelledError

    runtime.process.cancel = cancelled_cleanup
    with pytest.raises(SandboxError, match="cleanup_unverified"):
        await asyncio.wait_for(collect(runner, seg, ws, registry.context), 0.1)


@pytest.mark.asyncio
async def test_t033_ac2_cleanup_task_cancelled_before_entry_refuses(setup, monkeypatch):
    registry, _, _, ws, seg = setup
    runner, _ = build(setup)
    create_task = asyncio.create_task
    shield = asyncio.shield
    attempts = 0

    def cancelled_before_entry(coro):
        task = create_task(coro)
        if coro.cr_code.co_name == "bounded_cancel":
            task.cancel()
        return task

    def bounded_attempts(task):
        nonlocal attempts
        attempts += 1
        if attempts > 3:
            raise RuntimeError("Cleanup spun on a cancelled task")
        return shield(task)

    monkeypatch.setattr(asyncio, "create_task", cancelled_before_entry)
    monkeypatch.setattr(asyncio, "shield", bounded_attempts)
    with pytest.raises(SandboxError, match="cleanup_unverified"):
        await collect(runner, seg, ws, registry.context)


@pytest.mark.asyncio
async def test_t033_ac1_codex_rejects_competing_registry_adapter(setup):
    registry, _, _, ws, seg = setup
    runner, runtime = build(setup)
    runtime.registry = registry.clone()
    with pytest.raises(SandboxError, match="registry"):
        await collect(runner, seg, ws, registry.context)
    assert runtime.request is None


def test_t033_ac4_fake_final_gates_use_authenticated_snapshot(setup, monkeypatch):
    from cre_brain.runner.fake import RegistryReplayAdapter

    registry, inputs, _, _, _ = setup
    draft(setup)
    assert registry.call("finalize_deliverable", {"deliverable_id": "memo"})["status"] == "ok"
    expected = Path(inputs.artifacts["memo"].deliverable.path).read_bytes()
    snapshots = []

    def legacy(*args):
        raise AssertionError("Mutable-path gate reads must not be used")

    def bound(name, deliverable, snapshot):
        snapshots.append(snapshot)
        assert snapshot.data == expected
        assert snapshot.sha256 == hashlib.sha256(expected).hexdigest()
        return GateResult(passed=True, failures=[], metrics={})

    monkeypatch.setattr(registry.gates, "check", legacy)
    monkeypatch.setattr(registry.gates, "check_bytes", bound)
    RegistryReplayAdapter(registry).assert_final(("memo",))
    assert len(snapshots) == 3
    assert all(snapshot is snapshots[0] for snapshot in snapshots)


def test_t033_ac4_fake_rechecks_artifact_after_final_gates(setup, monkeypatch):
    from cre_brain.runner.fake import RegistryReplayAdapter

    registry, inputs, _, _, _ = setup
    draft(setup)
    assert registry.call("finalize_deliverable", {"deliverable_id": "memo"})["status"] == "ok"
    path = Path(inputs.artifacts["memo"].deliverable.path)

    def substitute(*args):
        path.write_text("Unauthenticated replacement")
        return GateResult(passed=True, failures=[], metrics={})

    monkeypatch.setattr(registry.gates, "check", substitute)
    monkeypatch.setattr(registry.gates, "check_bytes", substitute)
    with pytest.raises(ReplayError, match="authenticated"):
        RegistryReplayAdapter(registry).assert_final(("memo",))
