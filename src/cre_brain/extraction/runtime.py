"""Trusted T031/T033 composition seam; intentionally no concrete/host fallback.

Owner adapter obligations: create_extraction must clean up even on cancellation
before returning Box. Stage no-follows paths, replaces all ambient config/skills,
provisions auth privately, and never mutates parsed input. capabilities inspects
actual mounts, effective CLI/schema/config/auth and egress in the SAME box AFTER
stage; digest assertions must be independent inspection, not echoed request data.
Start rechecks the inspected binding and uses argv directly without a shell.
Enforce output/event/time/turn/token caps BEFORE every internal model call with
backpressure; cancellation covers detached descendants. No other source, repo,
raw seller document, CRE MCP, plugin, agent, credential store or tenant is exposed.
Synthetic evidence is allowed only in explicitly enabled test composition.
"""

from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field

from cre_brain.extraction.preparse.models import Digest
from cre_brain.extraction.schemas import ExtractionLimits
from cre_brain.runner.streaming import RunningProcess, RuntimeCapabilities
from cre_brain.runner.tools.contracts import Boundary
from cre_brain.sandbox.base import Box

CWD = "/home/agent/work/scratch"
CODEX_HOME = CWD + "/codex"
SCHEMA = CWD + "/schema.json"
PARSED = "/home/agent/input/parsed.json"


class ExtractionCapabilities(RuntimeCapabilities):
    model_only_egress: bool = Field(strict=True)
    no_mcp: bool = Field(strict=True)
    single_document_readonly: bool = Field(strict=True)
    bundle_sha256: Digest
    parsed_sha256: Digest


class ExtractionBundle(Boundary):
    cwd: str = CWD
    codex_home: str = CODEX_HOME
    files: dict[str, bytes]
    sha256: Digest
    parsed_sha256: Digest


class ExtractionRequest(ExtractionLimits):
    argv: tuple[str, ...]
    cwd: str = CWD
    codex_home: str = CODEX_HOME
    model: str
    model_provider: Literal["openai"]
    bundle_sha256: Digest
    parsed_sha256: Digest


class ExtractionProvider(Protocol):
    """Narrow extension of SandboxProvider.create_extraction (T031)."""

    async def create_extraction(self, user_id: str, image: str, parsed: Path) -> Box: ...
    async def destroy(self, box: Box) -> None: ...


class ExtractionRuntime(Protocol):
    provider: ExtractionProvider

    async def stage(self, box: Box, bundle: ExtractionBundle) -> None: ...
    async def capabilities(self, box: Box, bundle: ExtractionBundle) -> ExtractionCapabilities: ...
    async def start(self, box: Box, request: ExtractionRequest) -> RunningProcess: ...
