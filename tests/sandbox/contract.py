"""Run with python -m tests.sandbox.contract --factory module:factory --image IMAGE."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import tempfile
import uuid
from pathlib import Path

from cre_brain.sandbox.base import Box, SandboxProvider

WORK = "/home/agent/work"


async def assert_isolation(provider: SandboxProvider, first: Box, second: Box) -> None:
    async def shell(command: str, code: int | None = None) -> str:
        result = await provider.exec(first, ["sh", "-c", command], 8)
        if code is None:
            assert result.exit_code != 0, (command, result)
        else:
            assert result.exit_code == code, (command, result)
        return result.stdout

    assert (await shell("id -u", 0)).strip() != "0"
    await shell(f"test -r {WORK}/memory/own.txt", 0)
    for directory in (
        "/tmp",
        "/home/agent",
        "/etc",
        "/dev/shm",
        WORK + "/firms",
        WORK + "/.agents",
        WORK + "/.codex",
    ):
        await shell(f"echo denied > {directory}/unauthorized")
    await shell("cat /srv/raw/document.json")
    await shell("cat /var/run/docker.sock")
    await shell(f"cat {WORK}/memory/peer-secret.txt")
    await shell("curl --max-time 2 -fsS https://example.com/")
    # Unset proxy variables, and attack by literal IP to bypass application-level policy and DNS.
    await shell("curl --noproxy '*' --max-time 2 -fsS https://1.1.1.1/")
    await shell("curl --noproxy '*' --max-time 2 -fsS http://169.254.169.254/")
    await shell("curl --noproxy '*' --max-time 2 -fsS 'http://[::1]:8765/'")
    peer = await provider.exec(second, ["hostname", "-I"], 5)
    assert peer.exit_code == 0 and peer.stdout.strip()
    server = await provider.exec(
        second,
        [
            "python",
            "-c",
            "import subprocess; subprocess.Popen(['python','-m','http.server','8765',"
            "'--bind','0.0.0.0','--directory','/home/agent/work/memory'],"
            "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,"
            "start_new_session=True)",
        ],
        5,
    )
    assert server.exit_code == 0
    listening = await provider.exec(
        second,
        [
            "python",
            "-c",
            "import time; "
            "ready=lambda: any(row.split()[1].endswith(':223D') and row.split()[3]=='0A' "
            "for row in open('/proc/net/tcp').readlines()[1:]); "
            "[(time.sleep(0.1)) for _ in range(20) if not ready()]; assert ready()",
        ],
        5,
    )
    assert listening.exit_code == 0, listening
    await shell(f"curl --noproxy '*' --max-time 2 -fsS http://{peer.stdout.split()[0]}:8765/")


async def run_contract(provider: SandboxProvider, image: str) -> str:
    """No FakeRunner or tool server: direct shell, lifecycle, binary transfer and snapshot."""
    boxes: list[Box] = []
    with tempfile.TemporaryDirectory(prefix="cre-provider-contract-") as temp:
        directory = Path(temp)
        source = directory / "input"
        source.write_bytes(b"binary\x00state\xff")
        try:
            first = await provider.create("contract-a-" + uuid.uuid4().hex, image)
            boxes.append(first)
            second = await provider.create("contract-b-" + uuid.uuid4().hex, image)
            boxes.append(second)
            await provider.put(first, source, WORK + "/memory/own.txt")
            await provider.put(second, source, WORK + "/memory/peer-secret.txt")
            destination = directory / "output"
            await provider.get(first, WORK + "/memory/own.txt", destination)
            assert destination.read_bytes() == source.read_bytes()
            resumed = await provider.resume(first.user_id)
            assert resumed == first
            await assert_isolation(provider, first, second)
            snapshot = await provider.snapshot(first)
            assert snapshot
            timed = await provider.exec(first, ["sleep", "30"], 1)
            assert timed.exit_code != 0
            return snapshot
        finally:
            for box in reversed(boxes):
                await provider.destroy(box)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--factory", required=True, help="module:zero_argument_provider_factory")
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    module, name = args.factory.split(":")
    provider = getattr(importlib.import_module(module), name)()
    assert isinstance(provider, SandboxProvider)
    snapshot = asyncio.run(run_contract(provider, args.image))
    print(f"PASS: physical isolation, binary transfers, lifecycle, timeout; snapshot={snapshot}")


if __name__ == "__main__":
    main()
