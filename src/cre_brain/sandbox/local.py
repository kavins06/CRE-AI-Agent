"""Trusted Docker orchestration. Analyst code never receives the daemon socket."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import os
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cre_brain.sandbox.base import Box, ExecResult, SandboxError
from cre_brain.sandbox.files import MAX_BYTES, WORK, WRITABLE, validate_path
from cre_brain.sandbox.proxy import validate_domains


class DockerConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    state_dir: Path
    namespace: str = Field(pattern=r"^[a-z][a-z0-9-]{2,24}$")
    images: tuple[str, ...] = Field(min_length=1)
    proxy_image: str = "cre-egress:local"
    docker_binary: str = "docker"
    docker_host: str = "unix:///var/run/docker.sock"
    domains: tuple[str, ...] = ()
    model_domains: tuple[str, ...] = ()
    dns_server: str = "1.1.1.1"
    memory_mb: int = Field(default=4096, ge=512)
    cpus: int = Field(default=2, ge=1, le=32)
    pids: int = Field(default=256, ge=16, le=4096)

    @field_validator("state_dir")
    @classmethod
    def mount_source(cls, value: Path) -> Path:
        if any(character in str(value) for character in (",", '"', "\n", "\r", "\x00")):
            raise ValueError("Provider state path contains Docker mount delimiters")
        return value.resolve()

    @field_validator("domains", "model_domains")
    @classmethod
    def domain_names(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return validate_domains(value)

    @field_validator("docker_host")
    @classmethod
    def unix_only(cls, value: str) -> str:
        if not value.startswith("unix:///"):
            raise ValueError("Local provider requires a Unix daemon socket")
        return value

    @field_validator("dns_server")
    @classmethod
    def public_dns(cls, value: str) -> str:
        address = ipaddress.ip_address(value)
        if (
            address.version != 4
            or not address.is_global
            or address.is_multicast
            or address.is_reserved
        ):
            raise ValueError("Proxy DNS must be a public IPv4 resolver")
        return str(address)


SecretSource = Callable[[str], Mapping[str, str]]


class LocalDockerProvider:
    def __init__(self, config: DockerConfig, *, secrets: SecretSource | None = None) -> None:
        self.config = config
        self.secrets = secrets or (lambda _: {})
        self._values: set[bytes] = set()
        self._lock = asyncio.Lock()
        config.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        (config.state_dir / "client").mkdir(mode=0o700, exist_ok=True)

    def _name(self, user_id: str) -> str:
        Box(user_id=user_id, box_id="validation")
        digest = hashlib.sha256(user_id.encode()).hexdigest()[:24]
        return f"cre-{self.config.namespace}-{digest}"

    def _own(self, box: Box) -> None:
        base = self._name(box.user_id)
        if box.kind == "analyst" and box.box_id == base:
            return
        if box.kind == "extractor" and re.fullmatch(
            re.escape(base) + r"-x-[0-9a-f]{12}", box.box_id
        ):
            return
        raise SandboxError("Box ownership mismatch")

    async def _run(
        self,
        args: list[str],
        *,
        data: bytes | None = None,
        env: Mapping[str, str] | None = None,
        timeout: int = 60,
        check: bool = True,
    ) -> tuple[int, bytes, bytes]:
        command = [
            self.config.docker_binary,
            "--host",
            self.config.docker_host,
            "--config",
            str(self.config.state_dir / "client"),
            *args,
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={"PATH": os.defpath, "LANG": "C.UTF-8", **(env or {})},
            )

            async def read(stream: asyncio.StreamReader | None) -> bytes:
                assert stream is not None
                chunks = bytearray()
                while chunk := await stream.read(65536):
                    chunks.extend(chunk)
                    if len(chunks) > MAX_BYTES:
                        raise SandboxError("Docker output exceeds limit")
                return bytes(chunks)

            async def feed() -> None:
                assert process.stdin is not None
                try:
                    process.stdin.write(data or b"")
                    await process.stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    process.stdin.close()

            try:
                async with asyncio.timeout(timeout):
                    output, error, _ = await asyncio.gather(
                        read(process.stdout), read(process.stderr), feed()
                    )
                    code = await process.wait()
            except BaseException:
                if process.returncode is None:
                    process.kill()
                await process.wait()
                raise
        except (OSError, TimeoutError) as exc:
            raise SandboxError("Docker runtime unavailable or timed out") from exc
        if check and code:
            # Daemon errors may contain user-supplied paths/credentials; do not echo them.
            raise SandboxError(f"Docker operation {args[0]} failed (exit {code})")
        return code, output, error

    def _labels(self, box: Box) -> list[str]:
        return [
            "--label",
            f"cre.namespace={self.config.namespace}",
            "--label",
            f"cre.owner={self._name(box.user_id)}",
            "--label",
            f"cre.kind={box.kind}",
        ]

    async def _inspect(self, box: Box, *, absent_ok: bool = False) -> dict[str, Any] | None:
        self._own(box)
        code, output, _ = await self._run(["container", "inspect", box.box_id], check=False)
        if code:
            if absent_ok:
                # Distinguish an absent resource from an unavailable daemon.
                await self._run(["info", "--format", "{{.ServerVersion}}"])
                return None
            raise SandboxError("Box does not exist")
        info: dict[str, Any] = json.loads(output)[0]
        labels = info["Config"].get("Labels") or {}
        if any(
            labels.get(key) != value
            for key, value in {
                "cre.namespace": self.config.namespace,
                "cre.owner": self._name(box.user_id),
                "cre.kind": box.kind,
            }.items()
        ):
            raise SandboxError("Box ownership labels mismatch")
        return info

    def _limits(self) -> list[str]:
        return [
            "--read-only",
            "--ipc=none",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit",
            str(self.config.pids),
            "--memory",
            f"{self.config.memory_mb}m",
            "--memory-swap",
            f"{self.config.memory_mb}m",
            "--cpus",
            str(self.config.cpus),
        ]

    async def _resource(self, kind: str, name: str, box: Box) -> bool:
        code, output, _ = await self._run([kind, "inspect", name], check=False)
        if code:
            return False
        info = json.loads(output)[0]
        labels = (info["Config"] if kind == "container" else info).get("Labels") or {}
        expected = {
            "cre.namespace": self.config.namespace,
            "cre.owner": self._name(box.user_id),
            "cre.kind": box.kind,
        }
        if any(labels.get(key) != value for key, value in expected.items()):
            raise SandboxError("Resource ownership labels mismatch; refusing to modify")
        return True

    async def _proxy(self, box: Box, domains: tuple[str, ...]) -> None:
        name = box.box_id + "-egress"
        resolver = self.config.state_dir / (box.box_id + ".dns")
        resolver.write_text("nameserver " + self.config.dns_server + "\n")
        resolver.chmod(0o444)
        await self._run(["network", "create", *self._labels(box), name])
        await self._run(
            [
                "create",
                "--name",
                name,
                *self._labels(box),
                "--network",
                name,
                "--mount",
                f"type=bind,src={resolver.resolve()},dst=/etc/resolv.conf,readonly",
                *self._limits(),
                "--cap-add=NET_ADMIN",
                "--cap-add=SETUID",
                "--cap-add=SETGID",
                "--cap-add=SETPCAP",
                "--sysctl",
                "net.ipv6.conf.all.disable_ipv6=1",
                "--env",
                "ALLOW_DOMAINS=" + " ".join(domains),
                "--env",
                "DNS_SERVER=" + self.config.dns_server,
                self.config.proxy_image,
            ]
        )
        await self._run(["start", name])
        for _ in range(50):
            code, _, _ = await self._run(
                [
                    "exec",
                    "--user=1000:1000",
                    name,
                    "python3",
                    "-c",
                    "import socket; socket.create_connection(('127.0.0.1',3128),1).close()",
                ],
                check=False,
            )
            if not code:
                return
            await asyncio.sleep(0.1)
        raise SandboxError("Egress firewall/proxy did not become ready")

    async def create(self, user_id: str, image: str) -> Box:
        if image not in self.config.images:
            raise SandboxError("Image is not approved")
        box = Box(user_id=user_id, box_id=self._name(user_id))
        async with self._lock:
            if await self._inspect(box, absent_ok=True):
                raise SandboxError("Box already exists; use resume")
            for kind, name in [
                ("network", box.box_id + "-egress"),
                ("container", box.box_id + "-egress"),
                *[("volume", box.box_id + "-" + n) for n in ("work", *WRITABLE)],
            ]:
                if await self._resource(kind, name, box):
                    raise SandboxError("Leftover sandbox resources require explicit cleanup")
            try:
                for name in ("work", *WRITABLE):
                    await self._run(
                        ["volume", "create", *self._labels(box), box.box_id + "-" + name]
                    )
                mounts = ["--mount", f"type=volume,src={box.box_id}-work,dst={WORK}"]
                for name in WRITABLE:
                    mounts += [
                        "--mount",
                        f"type=volume,src={box.box_id}-{name},dst={WORK}/{name},volume-nocopy",
                    ]
                init = (
                    "import pathlib,os; w=pathlib.Path('/home/agent/work'); "
                    "[(w/p).mkdir(exist_ok=True) for p in "
                    "('firms','.agents','.codex','deals','memory','outbox','scratch')]; "
                    "[os.chown(w/p,1000,1000) for p in "
                    "('deals','memory','outbox','scratch')]"
                )
                await self._run(
                    [
                        "run",
                        "--rm",
                        "--network=none",
                        "--user=0:0",
                        *self._limits(),
                        "--cap-add=CHOWN",
                        "--cap-add=DAC_OVERRIDE",
                        *mounts,
                        "--entrypoint=python",
                        image,
                        "-c",
                        init,
                    ]
                )
                await self._proxy(box, self.config.domains)
                mounts[1] += ",readonly"
                await self._run(
                    [
                        "create",
                        "--name",
                        box.box_id,
                        *self._labels(box),
                        *self._limits(),
                        "--user=1000:1000",
                        "--network",
                        "container:" + box.box_id + "-egress",
                        *mounts,
                        "--workdir",
                        str(WORK),
                        "--env",
                        "HOME=/home/agent",
                        "--env",
                        "CODEX_HOME=/home/agent/work/scratch/codex",
                        "--env",
                        "HTTPS_PROXY=http://127.0.0.1:3128",
                        "--env",
                        "HTTP_PROXY=http://127.0.0.1:3128",
                        "--env",
                        "NO_PROXY=",
                        "--entrypoint=sleep",
                        image,
                        "infinity",
                    ]
                )
                await self._run(["start", box.box_id])
                return box
            except BaseException:
                await self._cleanup(box)
                raise

    async def resume(self, user_id: str) -> Box:
        box = Box(user_id=user_id, box_id=self._name(user_id))
        async with self._lock:
            await self._inspect(box)
            await self._run(["start", box.box_id + "-egress"])
            await self._run(["start", box.box_id])
            return box

    async def sleep(self, box: Box) -> None:
        async with self._lock:
            await self._inspect(box)
            await self._run(["stop", "--time=2", box.box_id])
            # Retain the proxy's network namespace so resume does not change namespace identity.

    async def exec(self, box: Box, cmd: list[str], timeout_s: int) -> ExecResult:
        self._own(box)
        if not cmd or any("\x00" in word for word in cmd) or not 1 <= timeout_s <= 3600:
            raise ValueError("Nonempty argv and timeout in 1..3600 required")
        await self._inspect(box)
        secrets = dict(self.secrets(box.user_id))
        if set(secrets) - {"CODEX_API_KEY", "OPENAI_API_KEY"}:
            raise SandboxError("Only runtime model credentials may enter the box")
        self._values.update(value.encode() for value in secrets.values() if value)
        flags = [part for key in secrets for part in ("--env", key)]
        code, output, error = await self._run(
            ["exec", *flags, box.box_id, "timeout", "--signal=KILL", str(timeout_s), *cmd],
            env=secrets,
            timeout=timeout_s + 10,
            check=False,
        )
        for secret in self._values:
            output, error = (
                output.replace(secret, b"[REDACTED]"),
                error.replace(secret, b"[REDACTED]"),
            )
        return ExecResult(
            exit_code=code,
            stdout=output.decode(errors="replace"),
            stderr=error.decode(errors="replace"),
        )

    async def _file(
        self, box: Box, operation: str, remote: str = "", data: bytes | None = None
    ) -> bytes:
        await self._inspect(box)
        if remote:
            validate_path(remote)
        _, output, _ = await self._run(
            [
                "exec",
                "-i",
                box.box_id,
                "python",
                "/opt/cre-transfer.py",
                operation,
                *([remote] if remote else []),
            ],
            data=data,
        )
        return output

    async def put(self, box: Box, local: Path, remote: str) -> None:
        validate_path(remote)
        if local.is_symlink() or not local.is_file() or local.stat().st_size > MAX_BYTES:
            raise ValueError("Transfer requires a bounded regular local file")
        await self._file(box, "put", remote, local.read_bytes())

    async def get(self, box: Box, remote: str, local: Path) -> None:
        data = await self._file(box, "get", remote)
        if local.is_symlink():
            raise ValueError("Refusing local symlink destination")
        local.write_bytes(data)

    async def snapshot(self, box: Box) -> str:
        await self._inspect(box)
        # The credential source covers fresh provider instances and key rotation.
        self._values.update(v.encode() for v in self.secrets(box.user_id).values() if v)
        data = await self._file(box, "snapshot")
        if any(value in data for value in self._values):
            raise SandboxError("Snapshot contains a runtime secret; refused")
        if re.search(rb"(?:sk-[A-Za-z0-9_-]{16,}|auth\.json|credentials\.json)", data):
            raise SandboxError("Snapshot contains credential material; refused")
        digest = hashlib.sha256(data).hexdigest()
        path = self.config.state_dir / (digest + ".tar")
        fd = (
            os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            if not path.exists()
            else None
        )
        if fd is not None:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
        return str(path)

    async def create_extraction(self, user_id: str, image: str, parsed: Path) -> Box:
        """Trusted pre-parser launches a disposable box with exactly one parsed JSON file."""
        if image not in self.config.images:
            raise SandboxError("Image is not approved")
        if parsed.is_symlink() or not parsed.is_file() or parsed.stat().st_size > MAX_BYTES:
            raise ValueError("Extraction requires a bounded parsed JSON file")
        data = parsed.read_bytes()
        if not isinstance(json.loads(data), dict):
            raise ValueError("Parsed document must be a JSON object")
        box = Box(
            user_id=user_id,
            box_id=self._name(user_id) + "-x-" + os.urandom(6).hex(),
            kind="extractor",
        )
        source = self.config.state_dir / (box.box_id + ".json")
        async with self._lock:
            source.write_bytes(data)
            source.chmod(0o444)
            try:
                network = ["--network=none"]
                if self.config.model_domains:
                    await self._proxy(box, self.config.model_domains)
                    network = ["--network", "container:" + box.box_id + "-egress"]
                await self._run(
                    [
                        "create",
                        "--name",
                        box.box_id,
                        *self._labels(box),
                        *self._limits(),
                        "--user=1000:1000",
                        *network,
                        "--mount",
                        f"type=bind,src={source.resolve()},dst=/home/agent/input/parsed.json,readonly",
                        "--tmpfs",
                        f"{WORK}/scratch:rw,noexec,nosuid,nodev,size=64m,uid=1000,gid=1000,mode=700",
                        "--workdir",
                        str(WORK),
                        "--env",
                        "HOME=/home/agent",
                        "--env",
                        "CODEX_HOME=/home/agent/work/scratch/codex",
                        "--env",
                        "HTTPS_PROXY=http://127.0.0.1:3128",
                        "--env",
                        "NO_PROXY=",
                        "--entrypoint=sleep",
                        image,
                        "infinity",
                    ]
                )
                await self._run(["start", box.box_id])
                return box
            except BaseException:
                await self._cleanup(box)
                source.unlink(missing_ok=True)
                raise

    async def _cleanup(self, box: Box) -> None:
        for name in (box.box_id, box.box_id + "-egress"):
            if await self._resource("container", name, box):
                await self._run(["rm", "--force", name])
        if await self._resource("network", box.box_id + "-egress", box):
            await self._run(["network", "rm", box.box_id + "-egress"])
        for name in ("work", *WRITABLE):
            if await self._resource("volume", box.box_id + "-" + name, box):
                await self._run(["volume", "rm", box.box_id + "-" + name])
        (self.config.state_dir / (box.box_id + ".dns")).unlink(missing_ok=True)

    async def destroy(self, box: Box) -> None:
        async with self._lock:
            await self._inspect(box)
            await self._cleanup(box)
            if box.kind == "extractor":
                (self.config.state_dir / (box.box_id + ".json")).unlink(missing_ok=True)


def provider_from_env() -> LocalDockerProvider:
    """Owner contract CLI factory; credentials deliberately omitted in the isolation harness."""
    return LocalDockerProvider(
        DockerConfig(
            state_dir=Path(os.environ["CRE_SANDBOX_STATE"]),
            namespace=os.environ["CRE_SANDBOX_NAMESPACE"],
            images=(os.environ["CRE_SANDBOX_IMAGE"],),
            proxy_image=os.environ.get("CRE_SANDBOX_PROXY_IMAGE", "cre-egress:local"),
            docker_binary=os.environ.get("CRE_SANDBOX_DOCKER", "docker"),
            docker_host=os.environ.get("DOCKER_HOST", "unix:///var/run/docker.sock"),
            domains=tuple(os.environ.get("CRE_SANDBOX_DOMAINS", "").split()),
            model_domains=tuple(os.environ.get("CRE_SANDBOX_MODEL_DOMAINS", "").split()),
        )
    )
