"""An owner contract must not certify unbounded or protected snapshot material."""

import gzip
import io
import tarfile
from pathlib import Path

import pytest

from cre_brain.sandbox.base import SandboxProvider, SnapshotContractAdapter, SnapshotReader
from cre_brain.sandbox.local import DockerConfig, LocalDockerProvider
from tests.sandbox.contract import assert_snapshot_contents


def _archive(entries: list[tuple[str, bytes, dict[str, str]]], *, mode: str = "w:gz") -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode=mode) as archive:
        for name, payload, metadata in entries:
            member = tarfile.TarInfo(name)
            member.size = len(payload)
            member.pax_headers = metadata
            archive.addfile(member, io.BytesIO(payload))
    return buffer.getvalue()


def test_t031_ac4_snapshot_contract_bounds_total_decompressed_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("tests.sandbox.contract.MAX_BYTES", 65536)
    payload = b"x" * 40000
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name in ("memory/own.txt", "outbox/other.txt"):
            member = tarfile.TarInfo(name)
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
    assert len(buffer.getvalue()) < 65536
    with pytest.raises(AssertionError, match="decompressed"):
        assert_snapshot_contents(buffer.getvalue(), payload)


@pytest.mark.parametrize(
    ("name", "metadata"),
    [
        ("outbox/contract-credential-probe", {}),
        ("outbox/safe", {"comment": "contract-credential-probe"}),
        ("outbox/safe", {"contract-credential-probe": "present"}),
    ],
)
def test_t031_ac4_snapshot_contract_scans_decompressed_metadata(
    name: str, metadata: dict[str, str]
) -> None:
    data = _archive([("memory/own.txt", b"expected", {}), (name, b"safe", metadata)])
    assert b"contract-credential-probe" not in data
    with pytest.raises(AssertionError, match="credential"):
        assert_snapshot_contents(data, b"expected")


@pytest.mark.parametrize("alias", ["./memory/own.txt", "memory//own.txt", "memory/./own.txt"])
def test_t031_ac4_snapshot_contract_rejects_noncanonical_destination_aliases(alias: str) -> None:
    data = _archive([("memory/own.txt", b"expected", {}), (alias, b"conflicting", {})])
    with pytest.raises(AssertionError, match="canonical"):
        assert_snapshot_contents(data, b"expected")


@pytest.mark.parametrize("mode", ["w", "w:gz", "w:bz2", "w:xz"])
def test_t031_ac4_snapshot_contract_accepts_bounded_safe_archives(mode: str) -> None:
    payload = b"binary\x00state\xff"
    assert_snapshot_contents(_archive([("memory/own.txt", payload, {})], mode=mode), payload)


@pytest.mark.parametrize("compressed", [False, True])
def test_t031_ac4_snapshot_contract_rejects_concatenated_tar_archives(compressed: bool) -> None:
    first = _archive([("memory/own.txt", b"expected", {})], mode="w")
    second = _archive([("memory/auth.json", b"unrelated-credential-material", {})], mode="w")
    data = gzip.compress(first + second) if compressed else first + second
    with pytest.raises(AssertionError, match="trailer"):
        assert_snapshot_contents(data, b"expected")


def test_t031_ac4_snapshot_contract_requires_complete_zero_padding() -> None:
    data = _archive([("memory/own.txt", b"expected", {})], mode="w")
    for malformed in (data[:1536], data[:-1] + b"x"):
        with pytest.raises(AssertionError, match="trailer"):
            assert_snapshot_contents(malformed, b"expected")
    assert_snapshot_contents(data[:2048], b"expected")


@pytest.mark.parametrize("compressed", [False, True])
def test_t031_ac4_snapshot_contract_rejects_swallowed_invalid_header(compressed: bool) -> None:
    data = _archive([("memory/own.txt", b"expected", {})], mode="w")
    invalid = b"memory/auth.json unrelated-credential-material".ljust(512, b"\x00")
    malformed = data[:1024] + invalid + b"\x00" * 512
    with pytest.raises(AssertionError, match="trailer"):
        assert_snapshot_contents(gzip.compress(malformed) if compressed else malformed, b"expected")


def test_t031_ac4_snapshot_contract_rejects_sparse_physical_offsets() -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.GNU_FORMAT) as archive:
        own = tarfile.TarInfo("memory/own.txt")
        own.size = len(b"expected")
        archive.addfile(own, io.BytesIO(b"expected"))
        sparse = tarfile.TarInfo("outbox/sparse")
        sparse.type = tarfile.GNUTYPE_SPARSE
        archive.addfile(sparse)
    with pytest.raises(AssertionError, match="non-sparse regular"):
        assert_snapshot_contents(buffer.getvalue(), b"expected")


@pytest.mark.asyncio
async def test_t031_ac4_documented_reader_adapter_preserves_the_base_provider_contract(
    tmp_path: Path,
) -> None:
    class Reader:
        async def read_snapshot(self, snapshot_id: str) -> bytes:
            assert snapshot_id == "opaque-owner-handle"
            return b"snapshot-bytes"

    provider = LocalDockerProvider(
        DockerConfig(state_dir=tmp_path, namespace="tests", images=("image",))
    )
    adapter = SnapshotContractAdapter(provider, Reader())
    assert isinstance(adapter, SandboxProvider)
    assert isinstance(adapter, SnapshotReader)
    assert await adapter.read_snapshot("opaque-owner-handle") == b"snapshot-bytes"
