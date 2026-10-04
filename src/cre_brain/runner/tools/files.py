"""No-follow, bounded reads and exclusive writes beneath a host workspace."""

import hashlib
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from cre_brain.runner.policy import Refusal

MAX_ARTIFACT_BYTES = 16 * 1024 * 1024


def relative(root: Path, path: Path) -> tuple[str, ...]:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        raise Refusal(
            "unauthorized_path", "Use a host-registered artifact in this deal workspace."
        ) from None
    if not parts or any(p in {"", ".", ".."} for p in parts):
        raise Refusal(
            "unauthorized_path", "Artifact path must stay inside its authorized directory."
        )
    return parts


@contextmanager
def directory(root: Path, parts: tuple[str, ...], *, create: bool = False) -> Iterator[int]:
    if not root.is_absolute():
        raise Refusal("unauthorized_path", "Host workspace root must be absolute.")
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        root_parts = root.parts[1:]
        for index, part in enumerate((*root_parts, *parts)):
            if part in {"", ".", ".."} or "/" in part:
                raise Refusal("unauthorized_path", "Use canonical workspace components.")
            if create and index >= len(root_parts):
                try:
                    os.mkdir(part, mode=0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


def read(root: Path, path: Path) -> bytes:
    parts = relative(root, path)
    with directory(root, parts[:-1]) as parent:
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            import stat

            info = os.fstat(descriptor)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_size > MAX_ARTIFACT_BYTES
            ):
                raise Refusal(
                    "unauthorized_path", "Use a bounded regular artifact with no hard links."
                )
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                data = stream.read(MAX_ARTIFACT_BYTES + 1)
            if len(data) > MAX_ARTIFACT_BYTES:
                raise Refusal("invalid_input", "Artifact exceeds size limit.")
            return data
        finally:
            os.close(descriptor)


def write(root: Path, parts: tuple[str, ...], data: bytes) -> Path:
    if len(data) > MAX_ARTIFACT_BYTES:
        raise Refusal("invalid_input", "Artifact exceeds size limit.")
    with directory(root, parts[:-1], create=True) as parent:
        descriptor = os.open(
            parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    return root.joinpath(*parts)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
