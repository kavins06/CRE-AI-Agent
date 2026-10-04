from pathlib import Path

import pytest
from pydantic import ValidationError

from cre_brain.sandbox.base import Box, SandboxError, SandboxProvider
from cre_brain.sandbox.local import DockerConfig, LocalDockerProvider


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
