from __future__ import annotations

import hashlib
import os
import re
import stat
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from pydantic import TypeAdapter

from cre_brain.knowledge.models import Artifact, Chunk

MAX_CACHE_BYTES = 30_000_000
CHUNKS = TypeAdapter(tuple[Chunk, ...])


def default_cache_dir() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "cre-brain" / "public-knowledge"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class CacheStore:
    """Public catalog-only cache, outside Git, with no-follow directory/file IO."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(os.path.abspath(root if root is not None else default_cache_dir()))
        for ancestor in (self.root, *self.root.parents):
            if ancestor.is_symlink():
                raise ValueError("Cache path cannot contain a symlink")
            if (ancestor / ".git").exists():
                raise ValueError("Knowledge cache must be outside every Git checkout")
        if any(
            part.lower() in ("deals", "firms", "evals", "private-eval", "truth")
            for part in self.root.parts
        ):
            raise ValueError("Public knowledge cache cannot share tenant/evaluation folders")
        if self.root.name != "public-knowledge":
            raise ValueError("Use a dedicated external directory named public-knowledge")

    @staticmethod
    def _name(value: str) -> str:
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,100}", value) or ".." in value:
            raise ValueError("Invalid cache path component")
        return value

    @contextmanager
    def _directory(self, *parts: str, create: bool = False) -> Iterator[int]:
        for part in parts:
            self._name(part)
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in (*self.root.parts[1:], *parts):
                if create:
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
                try:
                    os.stat(".git", dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise ValueError("Knowledge cache must be outside every Git checkout")
            yield fd
        except OSError as exc:
            if isinstance(exc, FileNotFoundError):
                raise
            raise ValueError("Unsafe cache path or symlink") from exc
        finally:
            os.close(fd)

    def _read(self, parts: tuple[str, ...], name: str) -> bytes | None:
        self._name(name)
        try:
            with self._directory(*parts) as fd:
                file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                with os.fdopen(file_fd, "rb") as stream:
                    info = os.fstat(stream.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise ValueError("Cache path is not a private regular file")
                    result = stream.read(MAX_CACHE_BYTES + 1)
                    if len(result) > MAX_CACHE_BYTES:
                        raise ValueError("Cache exceeds size limit")
                    return result
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise ValueError("Unsafe cache path or symlink") from exc

    def _write(self, parts: tuple[str, ...], name: str, data: bytes) -> None:
        if len(data) > MAX_CACHE_BYTES:
            raise ValueError("Cache exceeds size limit")
        self._name(name)
        with self._directory(*parts, create=True) as fd:
            try:
                existing = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if not stat.S_ISREG(existing.st_mode):
                    raise ValueError("Unsafe cache file or symlink")
            except FileNotFoundError:
                pass
            temporary = f".{uuid.uuid4().hex}"
            try:
                file_fd = os.open(
                    temporary,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    mode=0o600,
                    dir_fd=fd,
                )
                with os.fdopen(file_fd, "wb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, name, src_dir_fd=fd, dst_dir_fd=fd)
                os.fsync(fd)
            finally:
                try:
                    os.unlink(temporary, dir_fd=fd)
                except FileNotFoundError:
                    pass

    def current(self, resource_id: str) -> Artifact | None:
        raw = self._read((resource_id,), "current.json")
        if raw is None:
            return None
        metadata = Artifact.model_validate_json(raw)
        if metadata.resource_id != resource_id:
            raise ValueError("Cache identity mismatch")
        return self.artifact(resource_id, metadata.sha256)

    @contextmanager
    def import_lock(self, resource_id: str) -> Iterator[None]:
        import fcntl

        self._name(resource_id)
        with self._directory(resource_id, create=True) as fd:
            file_fd = os.open(
                "import.lock",
                os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                mode=0o600,
                dir_fd=fd,
            )
            with os.fdopen(file_fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError("Cache lock is not a private regular file")
                try:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise ValueError(
                        "Resource import already in progress; retry after completion"
                    ) from exc
                try:
                    yield
                finally:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def artifact(self, resource_id: str, digest: str) -> Artifact:
        if not re.fullmatch("[a-f0-9]{64}", digest):
            raise ValueError("Invalid cache hash")
        raw = self._read((resource_id, digest), "metadata.json")
        if raw is None:
            raise ValueError("Missing cache artifact")
        metadata = Artifact.model_validate_json(raw)
        document = self._read((resource_id, digest), "document.pdf")
        chunks = self._read((resource_id, digest), "chunks.json")
        if metadata.resource_id != resource_id or metadata.sha256 != digest:
            raise ValueError("Cache identity mismatch")
        if document is None or sha256(document) != digest or len(document) != metadata.byte_count:
            raise ValueError("Cached document hash mismatch")
        if chunks is None or sha256(chunks) != metadata.chunks_sha256:
            raise ValueError("Cached chunks hash mismatch")
        return metadata

    def chunks(self, metadata: Artifact) -> tuple[Chunk, ...]:
        self.artifact(metadata.resource_id, metadata.sha256)
        raw = self._read((metadata.resource_id, metadata.sha256), "chunks.json")
        assert raw is not None
        chunks = CHUNKS.validate_json(raw)
        if len(chunks) != metadata.chunk_count:
            raise ValueError("Chunk count mismatch")
        for chunk in chunks:
            if (
                chunk.citation.resource_id != metadata.resource_id
                or chunk.citation.sha256 != metadata.sha256
                or chunk.citation.retrieved_at != metadata.retrieved_at
                or chunk.citation.source_url != metadata.final_url
                or chunk.citation.page is None
                or chunk.citation.page > metadata.page_count
            ):
                raise ValueError("Chunk provenance mismatch")
        return chunks

    def store(self, metadata: Artifact, document: bytes, chunks: tuple[Chunk, ...]) -> None:
        parts = (metadata.resource_id, metadata.sha256)
        if self._read(parts, "metadata.json") is not None:
            self.artifact(*parts)
            return
        self._write(parts, "document.pdf", document)
        self._write(parts, "chunks.json", CHUNKS.dump_json(chunks))
        self._write(parts, "metadata.json", metadata.model_dump_json().encode())

    def activate(self, metadata: Artifact) -> None:
        self.artifact(metadata.resource_id, metadata.sha256)
        self._write((metadata.resource_id,), "current.json", metadata.model_dump_json().encode())

    def path(self, metadata: Artifact) -> Path:
        return self.root / metadata.resource_id / metadata.sha256
