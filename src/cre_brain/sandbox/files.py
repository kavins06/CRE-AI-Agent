"""Bounded, no-follow transfers. Executed inside the box, without host filesystem access."""

from __future__ import annotations

import io
import os
import stat
import sys
import tarfile
from pathlib import Path

WORK = Path("/home/agent/work")
WRITABLE = ("deals", "outbox", "memory", "scratch")
MAX_BYTES = 16 * 1024 * 1024


def validate_path(path: str) -> tuple[str, ...]:
    prefix = str(WORK) + "/"
    if not path.startswith(prefix) or "\x00" in path:
        raise ValueError("Path must be within writable workspace directories")
    parts = tuple(path[len(prefix) :].split("/"))
    if len(parts) < 2 or parts[0] not in WRITABLE or any(p in ("", ".", "..") for p in parts):
        raise ValueError("Path must be a canonical file in deals/outbox/memory/scratch")
    return parts


def _parent(parts: tuple[str, ...], root: Path, create: bool = False) -> int:
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_file(parts: tuple[str, ...], *, root: Path = WORK) -> bytes:
    parent = _parent(parts, root)
    try:
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("Only regular, non-hardlinked files may be transferred")
            data = stream.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError("File exceeds transfer limit")
            return data
    finally:
        os.close(parent)


def write_file(parts: tuple[str, ...], data: bytes, *, root: Path = WORK) -> None:
    if len(data) > MAX_BYTES:
        raise ValueError("File exceeds transfer limit")
    parent = _parent(parts, root, True)
    temp = ".transfer-" + os.urandom(12).hex()
    try:
        fd = os.open(
            temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent
        )
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(temp, parts[-1], src_dir_fd=parent, dst_dir_fd=parent)
    finally:
        try:
            os.unlink(temp, dir_fd=parent)
        except FileNotFoundError:
            pass
        os.close(parent)


def archive(*, root: Path = WORK) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for directory in WRITABLE:
            for path, dirs, files in os.walk(root / directory, followlinks=False):
                if any((Path(path) / d).is_symlink() for d in dirs):
                    raise ValueError("Snapshots reject symlinks")
                for name in files:
                    relative = (Path(path) / name).relative_to(root)
                    data = read_file(relative.parts, root=root)
                    member = tarfile.TarInfo(relative.as_posix())
                    member.size = len(data)
                    member.mode = 0o600
                    tar.addfile(member, io.BytesIO(data))
                    if buffer.tell() > MAX_BYTES:
                        raise ValueError("Snapshot exceeds transfer limit")
    return buffer.getvalue()


def main() -> None:
    if sys.argv[1] == "snapshot":
        sys.stdout.buffer.write(archive())
    elif sys.argv[1] == "get":
        sys.stdout.buffer.write(read_file(validate_path(sys.argv[2])))
    elif sys.argv[1] == "put":
        write_file(validate_path(sys.argv[2]), sys.stdin.buffer.read(MAX_BYTES + 1))
    else:
        raise ValueError("Unsupported transfer")


if __name__ == "__main__":
    main()
