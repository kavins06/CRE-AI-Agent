"""Replay through the real registry: plumbing only, never analyst quality evidence."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Protocol

from cre_brain.domain import AgentEvent, Deliverable
from cre_brain.domain.models import AgentEventKind
from cre_brain.runner.normalizer import Normalizer, Sanitizer
from cre_brain.runner.policy import ADVISORY, HostContext, required_gates
from cre_brain.runner.record import RecordError, load_recording
from cre_brain.runner.segment import SegmentSpec, Workspace
from cre_brain.runner.state_adapter import RunnerState
from cre_brain.runner.tools.json_io import canonical, parse
from cre_brain.runner.tools.registry import CORE_TOOLS, ToolRegistry


class ReplayError(ValueError):
    pass


class ArgumentAdapter(Protocol):
    """Host-owned ID remapping for a recorded tool, never loaded from the transcript."""

    def arguments(self, tool: str, recorded: dict[str, Any]) -> dict[str, Any]: ...
    def deliverable_id(self, recorded: str) -> str: ...


class RegistryReplayAdapter:
    """Typed adapter to T032; there is no alternate tool/gate or authoritative store."""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def assert_final(self, identities: tuple[str, ...]) -> None:
        if not identities:
            raise ReplayError("Replay requires nonempty expected final state")
        try:
            self.registry.require_gates()
            assert self.registry.gates is not None
            with self.registry.transaction() as state:
                for identity in identities:
                    current = state.current(Deliverable, identity)
                    if current is None or current.status != "final":
                        raise ReplayError("Replay final state is not a finalized deliverable")
                    anchor, snapshot = self.registry.artifact_snapshot(
                        state, identity, final_replay=True
                    )
                    names = required_gates(current.kind, anchor.extraction)
                    if len(current.gate_results) != len(names):
                        raise ReplayError("Replay final state has incomplete gate results")
                    for name, result in zip(names, current.gate_results, strict=True):
                        if name in ADVISORY:
                            continue
                        fresh = self.registry.gates.check_bytes(name, current, snapshot)
                        if (
                            not result.passed
                            or result.failures
                            or fresh.passed is not True
                            or fresh.failures
                        ):
                            raise ReplayError("Replay final state has failing blocking gates")
                    if not any(
                        e.kind == "deliverable"
                        and e.release_id == self.registry.context.release_id
                        and e.payload.get("d_id") == identity
                        and e.payload.get("version") == current.version
                        and e.payload.get("sha256") == anchor.sha256
                        for e in state.history()
                    ):
                        raise ReplayError("Replay final state has no trusted release transition")
                    self.registry.artifact(state, identity, final_replay=True)
                    self.registry.deadline(state)
        except ReplayError:
            raise
        except Exception:
            raise ReplayError("Replay final state could not be authenticated") from None


def result_status(payload: dict[str, Any]) -> str:
    result = payload.get("result")
    if payload.get("error") is not None or not isinstance(result, dict):
        raise ReplayError("Unsupported recorded MCP result")
    content = result.get("content")
    if not isinstance(content, list) or len(content) != 1 or not isinstance(content[0], dict):
        raise ReplayError("Unsupported recorded MCP content")
    block = content[0]
    if block.get("type") != "text" or not isinstance(block.get("text"), str):
        raise ReplayError("Unsupported recorded MCP text")
    try:
        status = parse(block["text"]).get("status")
        if status not in {"ok", "refused", "pending_confirmation"}:
            raise ValueError
        return str(status)
    except (ValueError, TypeError):
        raise ReplayError("Unsupported recorded tool response") from None


class FakeRunner:
    def __init__(
        self,
        recording: Path,
        *,
        registry: ToolRegistry,
        arguments: ArgumentAdapter | None = None,
        trusted_manifest_hash: str | None = None,
    ) -> None:
        self.recording = recording
        self.registry = registry
        self.arguments = arguments
        self.trusted_manifest_hash = trusted_manifest_hash

    async def run_segment(
        self, seg: SegmentSpec, ws: Workspace, policy: HostContext
    ) -> AsyncIterator[AgentEvent]:
        seg = SegmentSpec.model_validate(seg.model_dump())
        ws = Workspace.model_validate(ws.model_dump())
        policy = HostContext.model_validate(policy.model_dump())
        state = RunnerState(self.registry)
        state.validate(seg, ws, policy)
        try:
            recording = load_recording(self.recording, release_id=seg.release_id)
        except RecordError:
            raise ReplayError("Invalid or unsupported transcript") from None
        manifest = recording.manifest
        if manifest.scope != ws.scope or (manifest.task_id, manifest.deal_id) != (
            seg.task_id,
            seg.deal_id,
        ):
            raise ReplayError("Recording scope does not match the host registry")
        with self.registry.transaction() as tools_state:
            bound = any(
                e.runner == "recorder"
                and e.payload.get("recording_manifest_hash") == manifest.manifest_sha256
                and e.release_id == manifest.release_id
                for e in tools_state.history()
            )
        if not bound and self.trusted_manifest_hash != manifest.manifest_sha256:
            raise ReplayError("Transcript requires a trusted manifest binding")
        if any(
            e.kind == "runner_raw" and e.payload.get("unsupported") is not False
            for e in recording.events
        ):
            raise ReplayError("Replay refuses unsupported provider events/tools")
        if not manifest.expected_deliverables:
            raise ReplayError("Replay requires nonempty expected final state")
        if recording.events[-1].payload.get("reason") not in {
            "completed",
            "budget",
            "deliverable",
            "question",
            "confirmation",
        }:
            raise ReplayError("Replay refuses failed/incomplete transcripts")
        calls = [e for e in recording.events if e.kind == "tool_call"]
        results = [e for e in recording.events if e.kind == "tool_result"]
        if not calls or len(calls) != len(results):
            raise ReplayError("Replay requires paired CRE tool calls/results")
        # Preflight ALL calls before performing a single effect.
        prepared = []
        for call, result in zip(calls, results, strict=True):
            tool = call.payload.get("tool")
            args = call.payload.get("arguments")
            if (
                not isinstance(tool, str)
                or tool not in CORE_TOOLS
                or not isinstance(args, dict)
                or call.payload.get("call_id") != result.payload.get("call_id")
                or tool != result.payload.get("tool")
                or "[REDACTED]" in canonical(args)
                or tool == "send_external"
            ):
                raise ReplayError("Unsupported or unsafe recorded tool call")
            actual = self.arguments.arguments(tool, args) if self.arguments else args
            actual = parse(canonical(actual))
            if set(actual) != set(args):
                raise ReplayError("Loose matching requires the same tool and argument keys")
            try:
                CORE_TOOLS[tool].model_validate(actual)
            except ValueError:
                raise ReplayError("Unsupported recorded tool arguments") from None
            prepared.append((tool, actual, result_status(result.payload)))
        normalizer = Normalizer(seg, ws, Sanitizer())

        def persist(kind: AgentEventKind, payload: dict[str, Any]) -> AgentEvent:
            event = normalizer.make(kind, payload).model_copy(update={"runner": "fake"})
            return state.append(event)

        yield persist(
            "segment_start", {"plumbing_only": True, "manifest_hash": manifest.manifest_sha256}
        )
        for index, (tool, args, expected_status) in enumerate(prepared):
            # Recorded call IDs are ignored. Stable local IDs let the real registry
            # enforce idempotency; reference values are preserved unless host-mapped.
            request_id = f"fake-{manifest.manifest_sha256[:32]}-{seg.segment_no}-{index}"
            response = self.registry.call(tool, args, request_id=request_id)
            yield persist("tool_call", {"tool": tool, "argument_keys": sorted(args)})
            yield persist("tool_result", {"tool": tool, "status": response.get("status")})
            if response.get("status") != expected_status:
                raise ReplayError("Real tool response changed; re-record through cre record")
        identities = tuple(
            self.arguments.deliverable_id(identity) if self.arguments else identity
            for identity in manifest.expected_deliverables
        )
        RegistryReplayAdapter(self.registry).assert_final(identities)
        yield persist("segment_end", {"plumbing_only": True, "reason": "replayed"})
