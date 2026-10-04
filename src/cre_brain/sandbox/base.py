"""Owner-implemented physical sandbox contract; orchestration is trusted host code."""

from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class Box(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    user_id: str = Field(min_length=1, max_length=128)
    box_id: str = Field(min_length=1, max_length=128)
    kind: Literal["analyst", "extractor"] = "analyst"


class ExecResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    exit_code: int
    stdout: str
    stderr: str


class SandboxError(RuntimeError):
    """Unavailable runtime or rejected operation; never fall back to host execution."""


@runtime_checkable
class SandboxProvider(Protocol):
    async def create(self, user_id: str, image: str) -> Box: ...
    async def resume(self, user_id: str) -> Box: ...
    async def exec(self, box: Box, cmd: list[str], timeout_s: int) -> ExecResult: ...
    async def put(self, box: Box, local: Path, remote: str) -> None: ...
    async def get(self, box: Box, remote: str, local: Path) -> None: ...
    async def snapshot(self, box: Box) -> str: ...
    async def destroy(self, box: Box) -> None: ...
