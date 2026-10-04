"""Pinned private source namespaces and identity-bound, descriptor-relative cleanup.

Mode 0700 excludes other UIDs, not root or another process using our UID.
"""

from __future__ import annotations

import ctypes
import errno
import os
import stat
from pathlib import Path
from uuid import uuid4

DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def validate_destinations(packages: Path, truth: Path) -> tuple[Path, Path]:
    paths = tuple(Path(p).absolute() for p in (packages, truth))
    for path in paths:
        if ".." in path.parts or "\\" in str(path):
            raise ValueError("Output paths must not contain traversal or ambiguous separators")
    p, t = paths
    if p == t or p in t.parents or t in p.parents:
        raise ValueError("Package and truth roots must be separate and nonoverlapping")
    return p, t


def _open_directory(path: Path) -> int:
    """Walk from root using directory descriptors, rejecting every symlink component."""
    descriptor = os.open("/", DIRECTORY_FLAGS)
    try:
        for component in path.parts[1:]:
            next_descriptor = os.open(component, DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except OSError as error:
        os.close(descriptor)
        raise ValueError("Output parents must exist and contain no symlink aliases") from error


def _rename_new(parents: tuple[int, int], source: str, destination: str) -> None:
    """Publish between distinct pinned source/destination FDs with RENAME_NOREPLACE."""
    source_parent, destination_parent = parents
    library = ctypes.CDLL(None, use_errno=True)
    rename = getattr(library, "renameat2", None)
    if rename is None:
        raise RuntimeError("Safe fixture publication requires Linux renameat2")
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(source_parent, os.fsencode(source), destination_parent, os.fsencode(destination), 1):
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise ValueError("Output directory already exists; refusing overwrite")
        raise OSError(error, "Unable to publish generated fixture")


def _same_identity(current: os.stat_result, owned: os.stat_result) -> bool:
    return (current.st_dev, current.st_ino, stat.S_IFMT(current.st_mode)) == (
        owned.st_dev,
        owned.st_ino,
        stat.S_IFMT(owned.st_mode),
    )


def _remove_owned(parent: int, name: str, owned: os.stat_result, *, recursive: bool) -> None:
    """Bind an opened directory to its recorded identity before traversing it.

    Never pass a re-resolved pathname to rmtree. Uncertain identities, unexpected
    entries, or concurrent changes leave residue. Final rmdir cannot remove a
    replacement containing another writer's files.
    """
    try:
        current = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if not _same_identity(current, owned):
            return
        if not stat.S_ISDIR(owned.st_mode):
            os.unlink(name, dir_fd=parent)
            return
        descriptor = os.open(name, DIRECTORY_FLAGS, dir_fd=parent)
        try:
            if not _same_identity(os.fstat(descriptor), owned):
                return
            if recursive:
                for child in os.listdir(descriptor):
                    child_identity = os.stat(child, dir_fd=descriptor, follow_symlinks=False)
                    _remove_owned(descriptor, child, child_identity, recursive=True)
            # Traversal stays on the verified FD even if the parent name changes.
            if _same_identity(os.stat(name, dir_fd=parent, follow_symlinks=False), owned):
                os.rmdir(name, dir_fd=parent)
        finally:
            os.close(descriptor)
    except OSError:
        # Rollback is best effort; uncertainty must never justify deleting replacements.
        return


class Destination:
    """Own a retained private job FD containing a separately recorded payload."""

    def __init__(self, path: Path):
        self.name = path.name
        self.parent = _open_directory(path.parent)
        self.job: int | None = None
        self.job_name: str | None = None
        self.job_identity: os.stat_result | None = None
        self.stage_name: str | None = None
        self.identity: os.stat_result | None = None
        self.published = False
        try:
            self.check_absent()
        except BaseException:
            os.close(self.parent)
            raise

    def check_absent(self) -> None:
        try:
            os.stat(self.name, dir_fd=self.parent, follow_symlinks=False)
        except FileNotFoundError:
            return
        raise ValueError("Output path already exists; refusing overwrite")

    def _create_job(self, prefix: str) -> int:
        if self.job is not None:
            raise RuntimeError("Output is already staged")
        name = prefix + uuid4().hex
        # A collision is unowned: record nothing until exclusive creation succeeds.
        os.mkdir(name, mode=0o700, dir_fd=self.parent)
        created = os.stat(name, dir_fd=self.parent, follow_symlinks=False)
        descriptor = os.open(name, DIRECTORY_FLAGS, dir_fd=self.parent)
        try:
            opened = os.fstat(descriptor)
            if (
                not _same_identity(opened, created)
                or opened.st_uid != os.geteuid()
                or stat.S_IMODE(opened.st_mode) & 0o077
            ):
                raise ValueError("Private stage job identity changed")
            os.fchmod(descriptor, 0o700)
        except BaseException:
            os.close(descriptor)
            # A name observed during uncertain acquisition is not an owned job.
            raise
        self.job_name = name
        self.job_identity = opened
        self.job = descriptor
        return descriptor

    def stage(self) -> Path:
        job = self._create_job(".cre-gen-")
        os.mkdir("payload", mode=0o700, dir_fd=job)
        self.stage_name = "payload"
        self.identity = os.stat(self.stage_name, dir_fd=job, follow_symlinks=False)
        return Path(f"/proc/self/fd/{job}") / self.stage_name

    def stage_document(self, content: bytes) -> None:
        job = self._create_job(".cre-gen-document-")
        descriptor = os.open(
            "payload", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=job
        )
        # Failed O_EXCL never assigns ownership and therefore never unlinks a collision.
        try:
            self.stage_name = "payload"
            self.identity = os.fstat(descriptor)
            with os.fdopen(descriptor, "wb", closefd=False) as handle:
                handle.write(content)
        finally:
            os.close(descriptor)

    def publish(self) -> None:
        if self.job is None or self.stage_name is None or self.identity is None:
            raise RuntimeError("Output must be staged before publication")
        current = os.stat(self.stage_name, dir_fd=self.job, follow_symlinks=False)
        if not _same_identity(current, self.identity):
            raise ValueError("Payload stage type or identity changed")
        # The check is defense in depth; the mode-0700 pinned source namespace
        # supplies race protection against other UIDs with writable parent access.
        _rename_new((self.job, self.parent), self.stage_name, self.name)
        self.published = True

    def close(self, *, success: bool) -> None:
        try:
            if self.identity is not None and self.stage_name is not None and self.job is not None:
                if self.published:
                    if not success:
                        _remove_owned(self.parent, self.name, self.identity, recursive=True)
                else:
                    _remove_owned(self.job, self.stage_name, self.identity, recursive=True)
            if self.job_name is not None and self.job_identity is not None:
                # Do not recursively delete unexpected/unowned job entries.
                _remove_owned(self.parent, self.job_name, self.job_identity, recursive=False)
        finally:
            job, self.job = self.job, None
            try:
                if job is not None:
                    os.close(job)
            finally:
                os.close(self.parent)


def write_document(path: Path, content: bytes) -> None:
    """Stage a document in a private pinned namespace and publish without replacement."""
    path = Path(path).absolute()
    if ".." in path.parts or "\\" in str(path):
        raise ValueError("Document path must not contain traversal")
    if path.parts[:4] == ("/", "proc", "self", "fd"):
        raise ValueError("Render documents through ordinary paths or the private batch renderer")
    destination = Destination(path)
    success = False
    try:
        destination.stage_document(content)
        destination.publish()
        success = True
    finally:
        destination.close(success=success)
