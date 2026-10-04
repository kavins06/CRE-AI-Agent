"""Owned regular files and atomic output beneath trusted, no-follow directory roots."""

from __future__ import annotations

import os
import stat
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from cre_brain.extraction.preparse.models import PreparseError

DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def relative_parts(name: str) -> tuple[str, ...]:
    parts = tuple(name.split("/"))
    if (
        not name
        or len(name) > 1024
        or name.startswith("/")
        or "\\" in name
        or "\0" in name
        or any(part in ("", ".", "..") or len(part) > 255 for part in parts)
    ):
        raise PreparseError("Only confined relative paths are permitted")
    return parts


def _owned(info: os.stat_result, *, directory: bool = False) -> None:
    if info.st_uid != os.geteuid():
        raise PreparseError("Source/output must be owned by the parser user")
    if directory:
        if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o022:
            raise PreparseError("Parser directories must not be group/world writable")
    elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise PreparseError("Only singly linked regular files are permitted")


@contextmanager
def root_fd(path: Path, identity: tuple[int, int] | None = None) -> Iterator[int]:
    descriptor = os.open("/", DIRECTORY)
    try:
        for part in path.absolute().parts[1:]:
            next_fd = os.open(part, DIRECTORY, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_fd
        info = os.fstat(descriptor)
        _owned(info, directory=True)
        if identity is not None and (info.st_dev, info.st_ino) != identity:
            raise PreparseError("Trusted parser root has been replaced")
        yield descriptor
    except OSError as error:
        raise PreparseError("Cannot open a confined owned directory") from error
    finally:
        os.close(descriptor)


def root_identity(path: Path) -> tuple[int, int]:
    with root_fd(path) as descriptor:
        info = os.fstat(descriptor)
        return info.st_dev, info.st_ino


def read_source(root: Path, identity: tuple[int, int], name: str, maximum: int) -> bytes:
    parts = relative_parts(name)
    try:
        with root_fd(root, identity) as parent:
            directory = os.dup(parent)
            source = None
            try:
                for part in parts[:-1]:
                    next_fd = os.open(part, DIRECTORY, dir_fd=directory)
                    try:
                        _owned(os.fstat(next_fd), directory=True)
                    except PreparseError:
                        os.close(next_fd)
                        raise
                    os.close(directory)
                    directory = next_fd
                source = os.open(
                    parts[-1],
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                    dir_fd=directory,
                )
                before = os.fstat(source)
                _owned(before)
                if before.st_size > maximum:
                    raise PreparseError("Source file byte limit exceeded")
                chunks: list[bytes] = []
                remaining = maximum + 1
                while remaining:
                    chunk = os.read(source, min(remaining, 64 * 1024))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    remaining -= len(chunk)
                after = os.fstat(source)
                if (
                    remaining == 0
                    or before.st_size != after.st_size
                    or before.st_mtime_ns != after.st_mtime_ns
                    or before.st_ctime_ns != after.st_ctime_ns
                ):
                    raise PreparseError("Source changed or exceeded byte limit during read")
                return b"".join(chunks)
            finally:
                if source is not None:
                    os.close(source)
                os.close(directory)
    except OSError as error:
        raise PreparseError("Cannot read a confined owned regular source file") from error


def _matches_existing(directory: int, filename: str, content: bytes) -> bool:
    try:
        descriptor = os.open(
            filename,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
            dir_fd=directory,
        )
    except FileNotFoundError:
        return False
    try:
        before = os.fstat(descriptor)
        _owned(before)
        chunks: list[bytes] = []
        remaining = len(content) + 1
        while remaining:
            chunk = os.read(descriptor, min(remaining, 64 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        existing = b"".join(chunks)
        after = os.fstat(descriptor)
        if (
            before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or before.st_ctime_ns != after.st_ctime_ns
        ):
            raise PreparseError("Existing parsed output changed during read")
        if existing != content or before.st_size != len(content):
            raise PreparseError("Document ID already identifies a different parsed document")
        return True
    finally:
        os.close(descriptor)


def write_parsed(root: Path, identity: tuple[int, int], filename: str, content: bytes) -> Path:
    if len(relative_parts(filename)) != 1:
        raise PreparseError("Parsed output must have one safe filename")
    with root_fd(root, identity) as parent:
        try:
            try:
                os.mkdir("parsed", mode=0o700, dir_fd=parent)
            except FileExistsError:
                pass
            directory = os.open("parsed", DIRECTORY, dir_fd=parent)
            try:
                _owned(os.fstat(directory), directory=True)
                if _matches_existing(directory, filename, content):
                    return root / "parsed" / filename
                temporary = f".preparse-{uuid.uuid4().hex}"
                descriptor = os.open(
                    temporary,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                    0o600,
                    dir_fd=directory,
                )
                try:
                    with os.fdopen(descriptor, "wb") as target:
                        target.write(content)
                        target.flush()
                        os.fsync(target.fileno())
                    try:
                        os.link(
                            temporary,
                            filename,
                            src_dir_fd=directory,
                            dst_dir_fd=directory,
                            follow_symlinks=False,
                        )
                    except FileExistsError:
                        if not _matches_existing(directory, filename, content):
                            raise PreparseError("Parsed output disappeared during write") from None
                    os.unlink(temporary, dir_fd=directory)
                    os.fsync(directory)
                finally:
                    try:
                        os.unlink(temporary, dir_fd=directory)
                    except FileNotFoundError:
                        pass
            finally:
                os.close(directory)
        except OSError as error:
            raise PreparseError("Cannot write confined parsed output") from error
    return root / "parsed" / filename
