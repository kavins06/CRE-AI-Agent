"""Recorder of actual adapter output; synthetic harness captures are explicitly labeled.

Only cre record/record_segment produces artifacts. Raw means SANITIZED provider
JSONL: its on-disk hash is verifiable; source_raw_sha256 binds the byte-exact
transient source (which is never stored with secrets). Hashes detect corruption,
not authorship: trusted manifest binding is persisted separately in EventStore.
"""

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from cre_brain.domain import AgentEvent
from cre_brain.domain.base import TenantScope
from cre_brain.runner.codex import CodexRunner
from cre_brain.runner.policy import HostContext
from cre_brain.runner.segment import SegmentSpec, Workspace
from cre_brain.runner.streaming import InstructionBundle, RuntimeCapabilities
from cre_brain.runner.tools import files
from cre_brain.runner.tools.contracts import ID, Boundary
from cre_brain.runner.tools.json_io import MAX_BYTES, canonical, parse
from cre_brain.state.events import EventStore

MAX_RECORD_BYTES = 16777216


class RecordError(ValueError):
    pass


class RecordingManifest(Boundary):
    schema_version: Literal[1] = 1
    adapter_version: Literal["codex-jsonl-v1"] = "codex-jsonl-v1"
    event_schema_version: Literal[1] = 1
    evidence: Literal["isolated_runtime", "synthetic_plumbing_only"]
    raw_sanitized: Literal[True] = True
    codex_cli_version: str = Field(min_length=1, max_length=128)
    release_id: ID
    scope: TenantScope
    task_id: ID
    deal_id: ID
    segment_no: int = Field(strict=True, ge=0)
    session_id: ID | None
    model: str
    model_provider: str
    instructions_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    raw_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_raw_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    events_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    event_count: int = Field(strict=True, ge=2, le=100000)
    expected_deliverables: tuple[ID, ...] = ()

    def checksum(self) -> str:
        return files.digest(
            canonical(self.model_dump(mode="json", exclude={"manifest_sha256"})).encode()
        )


@dataclass(frozen=True)
class Recording:
    manifest: RecordingManifest
    events: tuple[AgentEvent, ...]


class Recorder:
    """Bounded observer; accepts only events emitted by the running adapter pipeline."""

    def __init__(self) -> None:
        self.caps: RuntimeCapabilities | None = None
        self.bundle: InstructionBundle | None = None
        self.raw_lines = bytearray()
        self.event_lines = bytearray()
        self.source_hash = hashlib.sha256()
        self.count = 0

    def bind(self, caps: RuntimeCapabilities, bundle: InstructionBundle) -> None:
        self.caps, self.bundle = caps, bundle

    def raw(self, source: bytes, sanitized: dict[str, Any]) -> None:
        self.source_hash.update(source)
        self.raw_lines.extend(canonical(sanitized).encode() + b"\n")
        self.bound()

    def event(self, event: AgentEvent) -> None:
        self.count += 1
        self.event_lines.extend(canonical(event.model_dump(mode="json")).encode() + b"\n")
        self.bound()

    def bound(self) -> None:
        if len(self.raw_lines) + len(self.event_lines) > MAX_RECORD_BYTES or self.count > 100000:
            raise RecordError("Recording output exceeds bounds")


async def record_segment(
    runner: CodexRunner,
    seg: SegmentSpec,
    ws: Workspace,
    policy: HostContext,
    output: Path,
    *,
    expected_deliverables: tuple[str, ...] = (),
    refresh: bool = False,
) -> RecordingManifest:
    """A capture is published only after safe completion and confirmed cleanup.

    Refresh creates a NEW capture path; recorded files are never edited/replaced.
    All provider events come from the adapter, never from a fallback FakeRunner.
    """
    output = output.absolute()
    # Validate parent without following even ancestor symlinks. No overwrite.
    with files.directory(output.parent, ()):
        if output.exists() or output.is_symlink():
            raise RecordError("Use a new recording path; --refresh never overwrites evidence")
    recorder = Recorder()
    stream = runner.with_capture(recorder).run_segment(seg, ws, policy)
    last: AgentEvent | None = None
    try:
        async for event in stream:
            last = event
    finally:
        await stream.aclose()
    if (
        recorder.caps is None
        or recorder.bundle is None
        or last is None
        or last.kind != "segment_end"
        or last.payload.get("usage_complete") is not True
        or last.payload.get("reason")
        not in {"completed", "budget", "deliverable", "question", "confirmation"}
    ):
        raise RecordError("Refuse incomplete or failed runtime recording")
    if recorder.caps.evidence == "synthetic_plumbing_only" and "transcripts" in output.parts:
        raise RecordError("Synthetic plumbing recordings cannot be stored under transcripts/")
    session_id = last.payload.get("session_id")
    if session_id is not None and not isinstance(session_id, str):
        raise RecordError("Invalid recorded session identity")
    manifest = RecordingManifest(
        evidence=recorder.caps.evidence,
        codex_cli_version=recorder.caps.cli_version,
        release_id=seg.release_id,
        scope=ws.scope,
        task_id=seg.task_id,
        deal_id=seg.deal_id,
        segment_no=seg.segment_no,
        session_id=session_id,
        model=runner.registry.settings.models.roles["lead"].model,
        model_provider=runner.model_provider,
        instructions_sha256=recorder.bundle.sha256,
        raw_sha256=files.digest(bytes(recorder.raw_lines)),
        source_raw_sha256=recorder.source_hash.hexdigest(),
        events_sha256=files.digest(bytes(recorder.event_lines)),
        event_count=recorder.count,
        expected_deliverables=expected_deliverables,
        manifest_sha256="0" * 64,
    )
    manifest = manifest.model_copy(update={"manifest_sha256": manifest.checksum()})
    # Stage under the validated parent. Publish exclusively, with manifest last.
    with tempfile.TemporaryDirectory(prefix=".record-", dir=output.parent) as temporary:
        root = Path(temporary)
        files.write(root, ("raw.jsonl",), bytes(recorder.raw_lines))
        files.write(root, ("events.jsonl",), bytes(recorder.event_lines))
        files.write(root, ("manifest.json",), canonical(manifest.model_dump(mode="json")).encode())
        with files.directory(output.parent, ()) as parent:
            os.mkdir(output.name, mode=0o700, dir_fd=parent)
        # Use the existing bounded exclusive no-follow file writer at publication.
        for name in ("raw.jsonl", "events.jsonl", "manifest.json"):
            files.write(output, (name,), files.read(root, root / name))
    # Independent durable authenticity binding, absent from provider-controlled JSONL.
    binding = last.model_copy(
        update={
            "event_id": "record-" + manifest.manifest_sha256,
            "seq": None,
            "origin": None,
            "runner": "recorder",
            "kind": "runner_raw",
            "source": "system",
            "payload": {"recording_manifest_hash": manifest.manifest_sha256, "refresh": refresh},
        }
    )
    EventStore(runner.registry.engine).append(binding, scope=ws.scope)
    return manifest


def load_recording(output: Path, *, release_id: str) -> Recording:
    """Validate artifact integrity; callers must also authenticate the manifest hash."""
    output = output.absolute()
    try:
        manifest_bytes = files.read(output, output / "manifest.json")
        if len(manifest_bytes) > MAX_BYTES:
            raise RecordError("Manifest exceeds bounds")
        manifest = RecordingManifest.model_validate(parse(manifest_bytes.decode()))
        if manifest.checksum() != manifest.manifest_sha256:
            raise RecordError("Manifest hash mismatch")
        if manifest.release_id != release_id:
            raise RecordError("Recording release binding mismatch")
        raw = files.read(output, output / "raw.jsonl")
        normalized = files.read(output, output / "events.jsonl")
        if len(raw) + len(normalized) > MAX_RECORD_BYTES:
            raise RecordError("Recording exceeds bounds")
        if (
            files.digest(raw) != manifest.raw_sha256
            or files.digest(normalized) != manifest.events_sha256
        ):
            raise RecordError("Recording hash mismatch")
        for line in raw.splitlines(keepends=True):
            if not line.endswith(b"\n"):
                raise RecordError("Recording JSONL framing mismatch")
            parse(line.decode())
        events: list[AgentEvent] = []
        box_id: str | None = None
        for line in normalized.splitlines(keepends=True):
            if not line.endswith(b"\n"):
                raise RecordError("Recording JSONL framing mismatch")
            event = AgentEvent.model_validate(parse(line.decode()))
            if (
                event.schema_version != 1
                or event.task_id != manifest.task_id
                or event.release_id != manifest.release_id
                or event.runner != "codex"
                or event.origin is None
                or event.origin[1] != manifest.segment_no
                or event.origin[2] != len(events) + 1
                or (box_id is not None and event.origin[0] != box_id)
            ):
                raise RecordError("Recording event identity/schema mismatch")
            box_id = event.origin[0]
            events.append(event)
        if len(events) != manifest.event_count or not events:
            raise RecordError("Recording event count mismatch")
        if events[0].kind != "segment_start" or events[-1].kind != "segment_end":
            raise RecordError("Recording segment framing mismatch")
        if events[-1].payload.get("session_id") != manifest.session_id:
            raise RecordError("Recording session binding mismatch")
        return Recording(manifest=manifest, events=tuple(events))
    except RecordError:
        raise
    except Exception:
        raise RecordError("Invalid or unsupported recording") from None
