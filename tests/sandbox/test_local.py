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
