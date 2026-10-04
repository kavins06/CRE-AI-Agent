"""Owner-implemented physical sandbox contract; orchestration is trusted host code."""

from dataclasses import dataclass
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


@runtime_checkable
class SnapshotReader(Protocol):
    """Trusted contract-only access to the bytes of an opaque snapshot handle."""

    async def read_snapshot(self, snapshot_id: str) -> bytes: ...


@dataclass(frozen=True)
class SnapshotContractAdapter:
    """Add artifact inspection to an existing provider without changing its protocol."""

    provider: SandboxProvider
    snapshot_reader: SnapshotReader

    async def create(self, user_id: str, image: str) -> Box:
        return await self.provider.create(user_id, image)

    async def resume(self, user_id: str) -> Box:
        return await self.provider.resume(user_id)

    async def exec(self, box: Box, cmd: list[str], timeout_s: int) -> ExecResult:
        return await self.provider.exec(box, cmd, timeout_s)

    async def put(self, box: Box, local: Path, remote: str) -> None:
        await self.provider.put(box, local, remote)

    async def get(self, box: Box, remote: str, local: Path) -> None:
        await self.provider.get(box, remote, local)

    async def snapshot(self, box: Box) -> str:
        return await self.provider.snapshot(box)

    async def read_snapshot(self, snapshot_id: str) -> bytes:
        return await self.snapshot_reader.read_snapshot(snapshot_id)

    async def destroy(self, box: Box) -> None:
        await self.provider.destroy(box)
