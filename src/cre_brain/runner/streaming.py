"""Trusted extension of SandboxProvider. Buffered exec is insufficient for live caps.

There is deliberately no host subprocess or LocalDockerProvider implementation.
An owner adapter must enforce caps on ALL internal model calls BEFORE further
usage, stream bounded complete JSONL frames with backpressure, and cancel the
whole process lifetime boundary (including detached descendants). A turn-completed
report is accounting, not a preventative token limit. hard_caps cannot be set
based on stdout, TOML intent, or post-hoc rejection.

capabilities must independently verify containment/auth, CLI flags/schema, MCP
approval and effective instructions/skills/config inventory in the SAME box.
stage replaces only trusted generated assets, removes retired skills, no-follows
all paths, keeps auth/session storage private, and binds MCP to the existing
host-authenticated ToolRegistry. No raw seller files, repo, evals, other tenants,
ambient host config, plugins, or credentials may be exposed. start cleans up its
lifetime boundary if cancelled before returning a handle, and rechecks this
binding and the isolated CODEX_HOME even on resume. Operations must be bounded;
a confirmed cancellation receipt means all descendants are absent.
"""

import asyncio
from collections.abc import AsyncIterator, Coroutine
from typing import Any, Literal, Protocol

from pydantic import Field

from cre_brain.runner.segment import SegmentSpec
from cre_brain.runner.tools.contracts import Boundary
from cre_brain.runner.tools.registry import ToolRegistry
from cre_brain.sandbox.base import Box, SandboxProvider


async def bounded_operation[T](
    operation: Coroutine[Any, Any, T], pending: set[asyncio.Task[Any]]
) -> T:
    """A hard acknowledgement bound, even if the adapter suppresses cancellation.

    Retain unsettled tasks and consume late failures; a late result never changes
    the durable recovery verdict made by the caller at the deadline.
    """
    task = asyncio.create_task(operation)
    pending.add(task)

    def settled(finished: asyncio.Task[T]) -> None:
        pending.discard(finished)
        if not finished.cancelled():
            finished.exception()

    task.add_done_callback(settled)
    try:
        done, _ = await asyncio.wait((task,), timeout=5)
        if not done:
            raise TimeoutError("Runtime acknowledgement timed out")
        return task.result()
    finally:
        if not task.done():
            task.cancel()


class RuntimeCapabilities(Boundary):
    evidence: Literal["isolated_runtime", "synthetic_plumbing_only"]
    cli_version: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_. +:-]+$")
    adapter_version: Literal["codex-jsonl-v1"] = "codex-jsonl-v1"
    isolated: bool = Field(strict=True)
    authenticated: bool = Field(strict=True)
    configuration_verified: bool = Field(strict=True)
    hard_caps: bool = Field(strict=True)
    resume_supported: bool = Field(strict=True)


class InstructionBundle(Boundary):
    cwd: str
    files: dict[str, bytes]
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class ExecutionRequest(Boundary):
    argv: tuple[str, ...]
    cwd: str
    codex_home: str
    model: str
    model_provider: str
    timeout_s: float = Field(gt=0, le=86400)
    max_turns: int = Field(strict=True, ge=1)
    max_tokens: int = Field(strict=True, ge=1)
    max_output_bytes: int = Field(strict=True, ge=1)
    max_line_bytes: int = 131072
    segment: SegmentSpec


class CancellationReceipt(Boundary):
    """Trusted native meter for ALL segment usage, including interrupted turns.

    None means accounting is incomplete: further segments must fail closed.
    cancel is idempotent and must return the same cumulative total on retry.
    """

    confirmed: bool = Field(strict=True)
    total_tokens: int | None = Field(strict=True, ge=0, le=1000000000)


class RunningProcess(Protocol):
    def stdout(self) -> AsyncIterator[bytes]: ...
    async def wait(self) -> int: ...
    async def cancel(self) -> CancellationReceipt: ...


class StreamingAdapter(Protocol):
    provider: SandboxProvider
    registry: ToolRegistry

    async def capabilities(self, box: Box) -> RuntimeCapabilities: ...
    async def stage(self, box: Box, bundle: InstructionBundle) -> None: ...
    async def start(self, box: Box, request: ExecutionRequest) -> RunningProcess: ...
