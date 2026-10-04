"""These tests fail, never skip, when a real isolated Docker runtime/image is missing."""

from __future__ import annotations

import json
import os
import tarfile
import uuid
from pathlib import Path

import pytest
import pytest_asyncio

from cre_brain.sandbox.base import SandboxError
from cre_brain.sandbox.local import DockerConfig, LocalDockerProvider
from tests.sandbox.contract import WORK, run_contract

pytestmark = pytest.mark.integration
SENTINEL = "sandbox-test-credential-not-a-live-api-key"


@pytest.fixture
def provider(tmp_path: Path) -> LocalDockerProvider:
    return LocalDockerProvider(
        DockerConfig(
            state_dir=tmp_path / "provider",
            namespace="test-" + uuid.uuid4().hex[:10],
            images=(
                os.environ.get("CRE_SANDBOX_IMAGE", "cre-box:local"),
                os.environ.get("CRE_SANDBOX_EXTRACT_IMAGE", "cre-extract:local"),
            ),
            docker_binary=os.environ.get("CRE_SANDBOX_DOCKER", "docker"),
            docker_host=os.environ.get("DOCKER_HOST", "unix:///var/run/docker.sock"),
            proxy_image=os.environ.get("CRE_SANDBOX_PROXY_IMAGE", "cre-egress:local"),
            domains=("pypi.org",),
            model_domains=("pypi.org",),
        ),
        secrets=lambda _: {"CODEX_API_KEY": SENTINEL},
    )


@pytest_asyncio.fixture
async def box(provider: LocalDockerProvider):
    value = await provider.create("alice", provider.config.images[0])
    try:
        yield value
    finally:
        await provider.destroy(value)


@pytest.mark.asyncio
async def test_t031_ac1_reference_image_tools(provider, box) -> None:
    result = await provider.exec(
        box,
        [
            "sh",
            "-c",
            "python --version && cre --help >/dev/null && codex --version "
            "&& libreoffice --version && /usr/bin/python3 -c 'import uno,unoserver' "
            "&& python -c 'import playwright.sync_api; "
            "p=playwright.sync_api.sync_playwright().start(); "
            'b=p.chromium.launch(args=["--no-sandbox","--disable-dev-shm-usage"]); '
            'page=b.new_page(); page.set_content("<title>isolated</title>"); '
            'assert page.title()=="isolated"; b.close(); p.stop()\'',
        ],
        30,
    )
    assert result.exit_code == 0, result
    info = await provider._inspect(box)
    assert info and SENTINEL not in json.dumps(info["Config"])


@pytest.mark.asyncio
async def test_t031_ac2_runtime_mounts_proxy_and_persistence(provider, box, tmp_path) -> None:
    info = await provider._inspect(box)
    assert info
    assert info["Config"]["User"] == "1000:1000"
    assert info["HostConfig"]["ReadonlyRootfs"] is True
    assert info["HostConfig"]["CapDrop"] == ["ALL"]
    assert info["HostConfig"]["PidsLimit"] == provider.config.pids
    assert info["HostConfig"]["Memory"] == provider.config.memory_mb * 1024**2
    assert all(
        m["Destination"] == WORK or m["Destination"].startswith(WORK + "/") for m in info["Mounts"]
    )
    assert {m["Destination"] for m in info["Mounts"] if m["RW"]} == {
        WORK + "/" + p for p in ("deals", "memory", "scratch", "outbox")
    }
    positive = await provider.exec(
        box, ["curl", "--max-time", "10", "-fsS", "https://pypi.org/"], 12
    )
    assert positive.exit_code == 0, positive
    local = tmp_path / "persist"
    local.write_bytes(b"durable")
    await provider.put(box, local, WORK + "/memory/state")
    await provider.sleep(box)
    assert await provider.resume(box.user_id) == box
    await provider.get(box, WORK + "/memory/state", tmp_path / "after")
    assert (tmp_path / "after").read_bytes() == b"durable"


@pytest.mark.asyncio
async def test_t031_ac3_policy_disabled_os_contract(provider) -> None:
    assert await run_contract(provider, provider.config.images[0])


@pytest.mark.asyncio
async def test_t031_ac3_snapshots_exclude_runtime_secrets(provider, box, tmp_path) -> None:
    check = await provider.exec(
        box, ["python", "-c", f"import os; assert os.environ['CODEX_API_KEY']=={SENTINEL!r}"], 5
    )
    assert check.exit_code == 0
    path = Path(await provider.snapshot(box))
    assert SENTINEL.encode() not in path.read_bytes()
    with tarfile.open(path) as archive:
        assert all(not p.name.startswith((".codex", ".agents", "firms")) for p in archive)
    await provider.exec(
        box,
        [
            "python",
            "-c",
            "import os,pathlib; pathlib.Path('/home/agent/work/memory/leaked').write_text("
            "os.environ['CODEX_API_KEY'])",
        ],
        5,
    )
    with pytest.raises(SandboxError, match="secret"):
        await provider.snapshot(box)


@pytest.mark.asyncio
async def test_t031_ac1_extractor_parsed_only_no_mcp(provider, tmp_path) -> None:
    parsed = tmp_path / "parsed.json"
    parsed.write_text('{"text": "untrusted seller text", "anchors": []}')
    extracted = await provider.create_extraction("alice", provider.config.images[1], parsed)
    try:
        info = await provider._inspect(extracted)
        assert info
        binds = [m for m in info["Mounts"] if m["Type"] == "bind"]
        assert len(binds) == 1 and binds[0]["Destination"] == "/home/agent/input/parsed.json"
        assert not binds[0]["RW"]
        result = await provider.exec(
            extracted,
            [
                "sh",
                "-c",
                "python -c 'import json; assert json.load(open(\"/home/agent/input/parsed.json\"))'"
                " && test ! -e /srv/raw && test ! -e /home/agent/work/memory"
                ' && test ! -e /home/agent/work/.agents && test ! -e "$CODEX_HOME/config.toml"'
                " && ! command -v cre && ! echo nope >> /home/agent/input/parsed.json"
                " && codex --version",
            ],
            10,
        )
        assert result.exit_code == 0, result
    finally:
        await provider.destroy(extracted)


@pytest.mark.asyncio
async def test_t031_ac4_owner_contract(provider) -> None:
    # Same owner-importable contract is exercised against a real provider, not a mock.
    assert await run_contract(provider, provider.config.images[0])


@pytest.mark.asyncio
async def test_t031_ac3_foreign_resource_collision_preserved(provider) -> None:
    name = provider._name("collision") + "-work"
    await provider._run(["volume", "create", "--label", "cre.owner=foreign", name])
    try:
        with pytest.raises(SandboxError, match="ownership"):
            await provider.create("collision", provider.config.images[0])
        _, data, _ = await provider._run(["volume", "inspect", name])
        assert json.loads(data)[0]["Labels"]["cre.owner"] == "foreign"
    finally:
        await provider._run(["volume", "rm", name])
