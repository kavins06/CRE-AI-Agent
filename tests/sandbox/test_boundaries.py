import io
import re
import tarfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from cre_brain.sandbox.base import Box, ExecResult, SandboxProvider
from cre_brain.sandbox.files import validate_path
from cre_brain.sandbox.proxy import resolve_target, validate_domains
from tests.sandbox.contract import assert_isolation, assert_snapshot_contents


def test_t031_ac1_typed_contract() -> None:
    assert SandboxProvider
    assert Box(user_id="alice", box_id="box-a").model_dump()["user_id"] == "alice"
    assert ExecResult(exit_code=0, stdout="ok", stderr="").stdout == "ok"
    with pytest.raises(ValidationError):
        Box(user_id="", box_id="box-a")


@pytest.mark.parametrize(
    "path",
    [
        "/srv/raw/x",
        "../memory/x",
        "/home/agent/work/deals/../firms/x",
        "/home/agent/work/firms/x",
        "/home/agent/work/.codex/auth.json",
        "/home/agent/work/memory",
        "/home/agent/work/memory//a",
        "/etc/passwd",
    ],
)
def test_transfer_rejects_unsafe_paths(path: str) -> None:
    with pytest.raises(ValueError):
        validate_path(path)


def test_t031_ac2_workspace_paths() -> None:
    assert validate_path("/home/agent/work/memory/ok") == ("memory", "ok")


@pytest.mark.parametrize(
    "domains",
    [["*"], ["127.0.0.1"], ["https://api.example.org"], ["example.org:443"], ["api.example.org."]],
)
def test_proxy_rejects_non_exact_domains(domains: list[str]) -> None:
    with pytest.raises(ValueError):
        validate_domains(domains)


def test_proxy_denies_private_and_rebound_addresses() -> None:
    for address in (
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "::1",
        "::ffff:127.0.0.1",
        "224.0.0.1",
        "ff02::1",
    ):
        with pytest.raises(ValueError):
            resolve_target(
                "api.example.org:443",
                ("api.example.org",),
                resolver=lambda *_, address=address, **kwargs: [
                    (None, None, None, None, (address, 443))
                ],
            )
    with pytest.raises(ValueError):
        resolve_target("api.example.org.evil:443", ("api.example.org",))


def test_file_helper_rejects_symlink_parents(tmp_path: Path) -> None:
    from cre_brain.sandbox.files import read_file, write_file

    (tmp_path / "memory").mkdir()
    (tmp_path / "memory" / "link").symlink_to(tmp_path.parent, target_is_directory=True)
    with pytest.raises(OSError):
        read_file(("memory", "link", "secret"), root=tmp_path)
    with pytest.raises(OSError):
        write_file(("memory", "link", "secret"), b"x", root=tmp_path)


def test_snapshot_artifact_requires_expected_bounded_workspace_contents() -> None:
    def archive(name: str, data: bytes) -> bytes:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as output:
            member = tarfile.TarInfo(name)
            member.size = len(data)
            output.addfile(member, io.BytesIO(data))
        return buffer.getvalue()

    expected = b"binary\x00state\xff"
    assert_snapshot_contents(archive("memory/own.txt", expected), expected)
    with pytest.raises(AssertionError):
        assert_snapshot_contents(archive("memory/auth.json", b"credential"), expected)
    with pytest.raises(AssertionError):
        assert_snapshot_contents(archive("../../host", expected), expected)
    with pytest.raises(AssertionError):
        assert_snapshot_contents(archive("memory/own.txt", b"wrong-artifact"), expected)


@pytest.mark.asyncio
@pytest.mark.parametrize("protected", ["/srv/raw", "/var/run/docker.sock"])
async def test_contract_does_not_treat_failed_cat_as_resource_absence(protected: str) -> None:
    class ExistingResourceProvider:
        async def exec(self, box: Box, cmd: list[str], timeout_s: int) -> ExecResult:
            command = cmd[-1]
            if command == "id -u":
                return ExecResult(exit_code=0, stdout="1000", stderr="")
            if command.startswith("test -r "):
                return ExecResult(exit_code=0, stdout="", stderr="")
            if command.startswith("test ! -e "):
                return ExecResult(
                    exit_code=int(command.startswith(f"test ! -e {protected} ")),
                    stdout="",
                    stderr="",
                )
            return ExecResult(exit_code=1, stdout="", stderr="cat failed")

    first = Box(user_id="alice", box_id="first")
    second = Box(user_id="bob", box_id="second")
    with pytest.raises(AssertionError, match=re.escape(f"test ! -e {protected} ")):
        await assert_isolation(ExistingResourceProvider(), first, second)
