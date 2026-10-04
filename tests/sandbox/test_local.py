import asyncio
import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from cre_brain.sandbox.base import Box, SandboxError, SandboxProvider
from cre_brain.sandbox.local import DockerConfig, LocalDockerProvider


class ResumeProvider(LocalDockerProvider):
    def __init__(
        self,
        config: DockerConfig,
        readiness: Sequence[int],
        readiness_gate: asyncio.Event | None = None,
    ) -> None:
        super().__init__(config)
        self.readiness = iter(readiness)
        self.readiness_gate = readiness_gate
        self.readiness_attempted = asyncio.Event()
        self.calls: list[list[str]] = []

    async def _inspect(self, box: Box, absent_ok: bool = False) -> dict[str, Any]:
        return {"State": {"Running": False}}

    async def _run(self, args: list[str], **kwargs: Any) -> tuple[int, bytes, bytes]:
        self.calls.append(args)
        if args[:1] == ["exec"]:
            self.readiness_attempted.set()
            if self.readiness_gate is not None:
                await self.readiness_gate.wait()
            return next(self.readiness, 1), b"", b""
        return 0, b"", b""


def test_local_configuration_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        DockerConfig(state_dir=tmp_path, namespace="../host", images=("image",))
    with pytest.raises(ValidationError):
        DockerConfig(state_dir=tmp_path, namespace="tests", images=("image",), domains=("*",))
    with pytest.raises(ValidationError):
        DockerConfig(state_dir=tmp_path / "mount,readonly", namespace="tests", images=("image",))
    provider = LocalDockerProvider(
        DockerConfig(state_dir=tmp_path, namespace="tests", images=("image",))
    )
    assert isinstance(provider, SandboxProvider)


@pytest.mark.asyncio
async def test_unavailable_runtime_never_executes_on_host(tmp_path: Path) -> None:
    provider = LocalDockerProvider(
        DockerConfig(
            state_dir=tmp_path,
            namespace="tests",
            images=("image",),
            docker_binary="/missing/docker",
        )
    )
    with pytest.raises(SandboxError, match="runtime"):
        await provider.create("alice", "image")
    assert not list(tmp_path.glob("*.tar"))


@pytest.mark.asyncio
async def test_foreign_box_rejected_before_runtime(tmp_path: Path) -> None:
    provider = LocalDockerProvider(
        DockerConfig(state_dir=tmp_path, namespace="tests", images=("image",))
    )
    with pytest.raises(SandboxError, match="ownership"):
        await provider.exec(Box(user_id="alice", box_id="someone-else"), ["true"], 1)
    with pytest.raises(SandboxError, match="approved"):
        await provider.create("alice", "attacker-image")


@pytest.mark.asyncio
async def test_resume_waits_for_proxy_before_starting_analyst(
    tmp_path: Path,
) -> None:
    gate = asyncio.Event()
    provider = ResumeProvider(
        DockerConfig(state_dir=tmp_path, namespace="tests", images=("image",)),
        readiness=(0,),
        readiness_gate=gate,
    )
    resume = asyncio.create_task(provider.resume("alice"))
    await provider.readiness_attempted.wait()
    box_id = provider._name("alice")
    assert ["start", box_id] not in provider.calls
    gate.set()
    box = await resume
    analyst_start = ["start", box.box_id]
    assert provider.calls[-1] == analyst_start
    assert provider.calls.index(analyst_start) > max(
        index for index, call in enumerate(provider.calls) if call[:1] == ["exec"]
    )


@pytest.mark.asyncio
async def test_resume_never_starts_analyst_when_proxy_readiness_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def no_wait(_: float) -> None:
        return None

    monkeypatch.setattr("cre_brain.sandbox.local.asyncio.sleep", no_wait)
    provider = ResumeProvider(
        DockerConfig(state_dir=tmp_path, namespace="tests", images=("image",)),
        readiness=(1,) * 50,
    )
    box_id = provider._name("alice")
    with pytest.raises(SandboxError, match="did not become ready"):
        await provider.resume("alice")
    assert ["start", box_id] not in provider.calls
    assert sum(call[:1] == ["exec"] for call in provider.calls) == 50


@pytest.mark.asyncio
async def test_host_transfer_rejects_symlink_ancestors(tmp_path: Path) -> None:
    class CaptureProvider(LocalDockerProvider):
        async def _file(self, *args, **kwargs) -> bytes:
            return b"result"

    provider = CaptureProvider(
        DockerConfig(state_dir=tmp_path / "state", namespace="tests", images=("image",))
    )
    directory = tmp_path / "actual"
    directory.mkdir()
    source = directory / "file"
    source.write_bytes(b"private")
    alias = tmp_path / "alias"
    alias.symlink_to(directory, target_is_directory=True)
    box = Box(user_id="alice", box_id=provider._name("alice"))
    with pytest.raises(OSError):
        await provider.put(box, alias / "file", "/home/agent/work/memory/file")
    with pytest.raises(OSError):
        await provider.get(box, "/home/agent/work/memory/file", alias / "output")
    assert not (directory / "output").exists()
    with pytest.raises(OSError):
        await provider.get(box, "/home/agent/work/memory/file", alias / "nested" / "output")
    assert not (directory / "nested").exists()


@pytest.mark.asyncio
async def test_snapshot_reader_accepts_only_owned_content_addressed_artifacts(
    tmp_path: Path,
) -> None:
    provider = LocalDockerProvider(
        DockerConfig(state_dir=tmp_path / "state", namespace="tests", images=("image",))
    )
    data = b"snapshot-artifact"
    path = provider.config.state_dir / (hashlib.sha256(data).hexdigest() + ".tar")
    path.write_bytes(data)
    assert await provider.read_snapshot(str(path)) == data
    with pytest.raises(SandboxError, match="owned"):
        await provider.read_snapshot(str(tmp_path / path.name))
    path.write_bytes(b"tampered")
    with pytest.raises(SandboxError, match="integrity"):
        await provider.read_snapshot(str(path))
