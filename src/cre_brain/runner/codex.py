"""Short Codex segments through a trusted streaming adapter, never host execution."""

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, Protocol

from cre_brain.domain import AgentEvent
from cre_brain.runner.instructions import generate
from cre_brain.runner.normalizer import EventInputError, Normalizer, Sanitizer
from cre_brain.runner.policy import HostContext
from cre_brain.runner.segment import SegmentSpec, Workspace
from cre_brain.runner.state_adapter import RunnerState
from cre_brain.runner.streaming import (
    CancellationReceipt,
    ExecutionRequest,
    InstructionBundle,
    RunningProcess,
    RuntimeCapabilities,
    StreamingAdapter,
)
from cre_brain.runner.tools.registry import ToolRegistry
from cre_brain.sandbox.base import SandboxError, SandboxProvider


class CaptureSink(Protocol):
    def bind(self, caps: RuntimeCapabilities, bundle: InstructionBundle) -> None: ...
    def raw(self, source: bytes, sanitized: dict[str, Any]) -> None: ...
    def event(self, event: AgentEvent) -> None: ...


class CodexRunner:
    def __init__(
        self,
        *,
        provider: SandboxProvider,
        registry: ToolRegistry,
        brain_root: Path,
        model_provider: str,
        runtime: StreamingAdapter | None = None,
        sanitizer: Sanitizer | None = None,
        firm_summary: str = "",
        user_memory: str = "",
        capture: CaptureSink | None = None,
    ) -> None:
        self.provider = provider
        self.runtime = runtime
        self.registry = registry
        self.brain_root = brain_root
        if not model_provider or len(model_provider) > 128 or not model_provider.isascii():
            raise ValueError("Host must configure a model provider identifier")
        self.model_provider = model_provider
        self.sanitizer = sanitizer or Sanitizer()
        self.firm_summary = firm_summary
        self.user_memory = user_memory
        self.capture = capture

    def with_capture(self, capture: CaptureSink) -> "CodexRunner":
        return CodexRunner(
            provider=self.provider,
            runtime=self.runtime,
            registry=self.registry,
            brain_root=self.brain_root,
            model_provider=self.model_provider,
            sanitizer=self.sanitizer,
            firm_summary=self.firm_summary,
            user_memory=self.user_memory,
            capture=capture,
        )

    async def ready(self, ws: Workspace, seg: SegmentSpec) -> RuntimeCapabilities:
        if self.runtime is None or self.runtime.provider is not self.provider:
            raise SandboxError(
                "missing_runtime: trusted sandbox streaming/cancellation adapter required"
            )
        if self.runtime.registry is not self.registry:
            raise SandboxError("Runtime registry must be the canonical host tool registry")
        try:
            caps = await asyncio.wait_for(self.runtime.capabilities(ws.box), 5)
            caps = RuntimeCapabilities.model_validate(caps.model_dump())
        except Exception:
            raise SandboxError("missing_runtime: restricted capabilities unavailable") from None
        if not caps.isolated or not caps.configuration_verified:
            raise SandboxError(
                "missing_container: verified isolated runtime/configuration required"
            )
        if not caps.authenticated:
            raise SandboxError("missing_auth: authorized runtime authentication required")
        if not caps.hard_caps:
            raise SandboxError("missing_capabilities: preventive turn/token caps required")
        if seg.resume_session_id and not caps.resume_supported:
            raise SandboxError("missing_capabilities: verified resume syntax required")
        role = self.registry.settings.models.roles["lead"]
        if role.runner != "codex":
            raise SandboxError("unsupported_runner: configure the Codex lead role")
        if caps.evidence == "isolated_runtime" and (
            "<" in role.model or ">" in role.model or not role.model.strip()
        ):
            raise SandboxError("missing_model: owner must configure a runtime model")
        return caps

    async def run_segment(
        self, seg: SegmentSpec, ws: Workspace, policy: HostContext
    ) -> AsyncGenerator[AgentEvent, None]:
        seg = SegmentSpec.model_validate(seg.model_dump())
        try:
            ws = Workspace.model_validate(ws.model_dump())
            policy = HostContext.model_validate(policy.model_dump())
        except ValueError:
            raise SandboxError("Invalid runner scope/policy") from None
        state = RunnerState(self.registry)
        state.validate(seg, ws, policy)
        caps = await self.ready(ws, seg)
        assert self.runtime is not None
        bundle = generate(
            self.brain_root,
            seg,
            self.registry,
            self.model_provider,
            firm_summary=self.firm_summary,
            user_memory=self.user_memory,
        )
        role = self.registry.settings.models.roles["lead"]
        timeout = min(
            seg.timeout_s or self.registry.settings.budget.segment_max_min * 60,
            self.registry.settings.budget.segment_max_min * 60,
            state.remaining_seconds(),
        )
        if timeout <= 0:
            raise SandboxError("Canonical policy budget exhausted")
        deadline = asyncio.get_running_loop().time() + timeout
        argv = (
            (
                "codex",
                "exec",
                "resume",
                seg.resume_session_id,
                "--json",
                "-m",
                role.model,
                seg.prompt,
            )
            if seg.resume_session_id
            else (
                "codex",
                "exec",
                "--json",
                "--cd",
                seg.cwd,
                "-p",
                role.profile,
                "--sandbox",
                "workspace-write",
                "-m",
                role.model,
                seg.prompt,
            )
        )
        request = ExecutionRequest(
            argv=argv,
            cwd=seg.cwd,
            codex_home=seg.cwd + "/.codex",
            model=role.model,
            model_provider=self.model_provider,
            timeout_s=timeout,
            max_turns=seg.max_turns,
            max_tokens=seg.max_tokens,
            max_output_bytes=seg.max_output_bytes,
            segment=seg,
        )
        normalizer = Normalizer(seg, ws, self.sanitizer)
        start = normalizer.make(
            "segment_start",
            {
                "deal_id": seg.deal_id,
                "resume_session_id": seg.resume_session_id,
                "evidence": caps.evidence,
                "instructions_sha256": bundle.sha256,
                "max_turns": seg.max_turns,
                "max_tokens": seg.max_tokens,
                "timeout_s": timeout,
            },
        )
        stored_start = state.reserve(seg, ws, start)
        if self.capture:
            self.capture.bind(caps, bundle)
            self.capture.event(stored_start)
        process: RunningProcess | None = None
        reason = "interrupted"
        cancelled = False
        usage_complete = False
        cleanup_events: list[AgentEvent] = []
        cancel_task: asyncio.Task[CancellationReceipt] | None = None
        interruption: asyncio.CancelledError | None = None

        def persist(event: AgentEvent) -> AgentEvent:
            stored = state.append(event)
            if self.capture:
                self.capture.event(stored)
            return stored

        async def cancel(*, shield_interruptions: bool = False) -> None:
            nonlocal cancelled, usage_complete, cancel_task, interruption
            if process is None or cancelled:
                return
            target = process

            async def bounded_cancel() -> CancellationReceipt:
                try:
                    result = await asyncio.wait_for(target.cancel(), 5)
                    return CancellationReceipt.model_validate(result.model_dump())
                except asyncio.CancelledError:
                    return CancellationReceipt(confirmed=False, total_tokens=None)
                except Exception:
                    return CancellationReceipt(confirmed=False, total_tokens=None)

            if cancel_task is None:
                cancel_task = asyncio.create_task(bounded_cancel())
            while True:
                try:
                    receipt = await asyncio.shield(cancel_task)
                    break
                except asyncio.CancelledError as error:
                    if cancel_task.cancelled():
                        persist(normalizer.make("error", {"category": "cleanup_unverified"}))
                        raise SandboxError(
                            "cleanup_unverified: runtime cancellation not confirmed"
                        ) from None
                    if interruption is None:
                        interruption = error
                    continue
            if not receipt.confirmed:
                persist(normalizer.make("error", {"category": "cleanup_unverified"}))
                raise SandboxError("cleanup_unverified: runtime cancellation not confirmed")
            cancelled = True
            if receipt.total_tokens is None or receipt.total_tokens < normalizer.tokens:
                usage_complete = False
            else:
                usage_complete = True
                additional = receipt.total_tokens - normalizer.tokens
                if additional:
                    cleanup_events.append(
                        persist(
                            normalizer.make(
                                "usage",
                                {
                                    "host_tokens": additional,
                                    "session_id": normalizer.session_id,
                                    "accounting": "trusted_cancellation_meter",
                                },
                            )
                        )
                    )
                    normalizer.tokens = receipt.total_tokens
            if interruption is not None and not shield_interruptions:
                raise interruption

        try:
            # Entire stage/start/stream/wait shares one wall-clock deadline.
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError
            async with asyncio.timeout_at(deadline):
                await self.runtime.stage(ws.box, bundle)
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError
                request = request.model_copy(update={"timeout_s": remaining})
                process = await self.runtime.start(ws.box, request)
                yield stored_start
                count = 0
                byte_count = 0
                async for line in process.stdout():
                    byte_count += len(line)
                    count += 1
                    if byte_count > seg.max_output_bytes or count > seg.max_events:
                        reason = "budget"
                        await cancel()
                        for event in cleanup_events:
                            yield event
                        cleanup_events.clear()
                        yield persist(normalizer.make("budget", {"cap": "event_output"}))
                        break
                    frame = normalizer.feed(line)
                    if self.capture:
                        self.capture.raw(line, frame.raw)
                    limit = normalizer.tokens >= seg.max_tokens or normalizer.turns >= seg.max_turns
                    provider_error = any(e.kind == "error" for e in frame.events)
                    stored = [persist(event) for event in frame.events]
                    stop = state.stop_reason(stored_start.seq or 0)
                    if limit or provider_error or stop:
                        reason = (
                            "budget" if limit else "provider_error" if provider_error else str(stop)
                        )
                        await cancel()  # Usage is durable; stop before yielding another frame.
                    for event in stored:
                        yield event
                    for event in cleanup_events:
                        yield event
                    cleanup_events.clear()
                    if limit:
                        yield persist(normalizer.make("budget", {"cap": "tokens_or_turns"}))
                    if limit or provider_error or stop:
                        break
                else:
                    exit_code = await process.wait()
                    if exit_code != 0 or normalizer.session_id is None or normalizer.turn_open:
                        reason = "provider_error"
                        await cancel()
                        for event in cleanup_events:
                            yield event
                        cleanup_events.clear()
                        yield persist(normalizer.make("error", {"category": "incomplete_segment"}))
                    else:
                        reason = "completed"
        except TimeoutError:
            interruption = None
            reason = "budget"
            await cancel()
            for event in cleanup_events:
                yield event
            cleanup_events.clear()
            yield persist(normalizer.make("budget", {"cap": "wallclock"}))
        except EventInputError:
            reason = "invalid_event"
            await cancel()
            for event in cleanup_events:
                yield event
            cleanup_events.clear()
            yield persist(normalizer.make("error", {"category": "invalid_event"}))
        except (asyncio.CancelledError, GeneratorExit):
            reason = "interrupted"
            raise
        except Exception:
            reason = "runtime_error"
            raise SandboxError(
                "Runtime segment failed; inspect trusted adapter diagnostics"
            ) from None
        finally:
            # Closing the consumer also cancels the runtime. Never silently abandon it.
            await cancel(shield_interruptions=True)
            if interruption is not None:
                reason = "interrupted"
            end = persist(
                normalizer.make(
                    "segment_end",
                    {
                        "reason": reason,
                        "session_id": normalizer.session_id,
                        "turns": normalizer.turns,
                        "tokens": normalizer.tokens,
                        "usage_complete": usage_complete,
                    },
                )
            )
            if interruption is not None:
                raise interruption
        for event in cleanup_events:
            yield event
        yield end
