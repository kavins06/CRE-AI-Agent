from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from cre_brain.domain import CalcResult, Fact
from cre_brain.knowledge import CacheStore, KnowledgeLibrary, SearchRequest, load_catalog
from cre_brain.knowledge.fetch import (
    BoundedFetcher,
    FetchError,
    PublicHTTPS,
    Response,
    resolve_public,
)
from cre_brain.knowledge.models import Resource
from cre_brain.knowledge.parse import PdfParser

from .test_library import SOURCE, Transport, cache_dir, library, pdf, response

__all__ = ["cache_dir"]


@pytest.mark.parametrize(
    "changes",
    [
        {"commercial_reuse_allowed": False},
        {"download_url": "https://evil.example.com/book.pdf"},
        {"allowed_urls": ["https://www.sec.gov/file.pdf"]},
        {"allowed_urls": ["https://key:password@www.occ.gov/file.pdf"]},
        {"disposition": "REFERENCE_ONLY"},
        {"rights_basis": ""},
        {"jurisdictions": ["CA"]},
    ],
)
def test_resource_metadata_cannot_silently_expand_permission(changes: dict[str, object]) -> None:
    raw = load_catalog().get(SOURCE).model_dump()
    raw.update(changes)
    with pytest.raises(ValidationError):
        Resource.model_validate(raw)


@pytest.mark.parametrize(
    "addresses",
    [
        ["127.0.0.1"],
        ["169.254.169.254"],
        ["10.1.1.1"],
        ["::1"],
        ["fd00::1"],
        ["8.8.8.8", "192.168.1.1"],
        ["100.64.0.1"],
        ["224.0.0.1"],
        ["ff02::1"],
        ["::ffff:8.8.8.8"],
        [],
    ],
)
def test_dns_private_mixed_and_reserved_destinations_fail_closed(addresses: list[str]) -> None:
    with patch("cre_brain.knowledge.fetch.subprocess.run") as run:
        run.return_value = subprocess.CompletedProcess([], 0, json.dumps(addresses).encode())
        with pytest.raises(FetchError):
            resolve_public("www.occ.gov", 2)


def test_dns_pins_one_verified_public_ip_with_sanitized_environment() -> None:
    with patch("cre_brain.knowledge.fetch.subprocess.run") as run:
        run.return_value = subprocess.CompletedProcess([], 0, b'["8.8.8.8"]')
        assert resolve_public("www.occ.gov", 2) == "8.8.8.8"
        assert run.call_args.kwargs["env"] == {}
        assert run.call_args.kwargs["timeout"] == 2


def test_fetch_timeout_and_unexpected_status_do_not_write_cache(cache_dir: Path) -> None:
    lib = library(cache_dir, Response(202, {"content-type": "text/html"}, b"challenge"))
    with pytest.raises(FetchError, match="202"):
        lib.import_resource(SOURCE)
    assert lib.cache.current(SOURCE) is None
    clock = iter([0.0, 0.0, 31.0])
    with patch("cre_brain.knowledge.fetch.time.monotonic", side_effect=lambda: next(clock)):
        with pytest.raises(FetchError, match="timeout"):
            BoundedFetcher(transport=Transport(response(pdf("okay")))).fetch(
                load_catalog().get(SOURCE)
            )


def test_pdf_parser_timeout_is_bounded_and_does_not_leak_child_stderr() -> None:
    with patch("cre_brain.knowledge.parse.subprocess.run") as run:
        run.side_effect = subprocess.TimeoutExpired("parse", 1, stderr=b"SECRET_FIXTURE")
        with pytest.raises(ValueError, match="PDF parsing failed") as error:
            PdfParser(timeout=1).parse(pdf("okay"))
        assert "SECRET_FIXTURE" not in str(error.value)
        assert run.call_args.kwargs["timeout"] == 1
        assert set(run.call_args.kwargs["env"]) == {"PATH", "PYTHONUTF8"}
        assert "-I" in run.call_args.args[0]


def test_unknown_cache_files_never_become_retrievable_sources(cache_dir: Path) -> None:
    cache_dir.mkdir()
    (cache_dir / "tenant-private.txt").write_text("PRIVATE_FIXTURE_SENTINEL")
    lib = KnowledgeLibrary(cache=CacheStore(cache_dir))
    assert not lib.search(SearchRequest(query="PRIVATE_FIXTURE_SENTINEL")).hits


def test_file_symlink_and_chunk_tampering_fail_closed(cache_dir: Path) -> None:
    lib = library(cache_dir, response(pdf("DSCR government text.")))
    imported = lib.import_resource(SOURCE)
    path = lib.cache.path(imported.artifact) / "chunks.json"
    path.write_bytes(b"[]")
    with pytest.raises(ValueError, match="hash"):
        lib.search(SearchRequest(query="DSCR"))
    path.unlink()
    path.symlink_to(Path("/etc/passwd"))
    with pytest.raises(ValueError, match="symlink"):
        lib.search(SearchRequest(query="DSCR"))


def test_parser_uses_real_pdf_text_and_preserves_page_heading(cache_dir: Path) -> None:
    lib = library(cache_dir, response(pdf("Net Operating Income\nDSCR underwriting test")))
    result = lib.import_resource(SOURCE)
    chunks = lib.cache.chunks(result.artifact)
    assert chunks[0].citation.section == "Net Operating Income"
    assert chunks[0].citation.page == 1


def test_global_reference_provider_rejects_extra_private_context() -> None:
    with pytest.raises(ValidationError):
        SearchRequest(query="DSCR", firm_id="other-firm")


def test_fetch_transport_receives_only_exact_url_and_bounds() -> None:
    transport = Mock()
    transport.get.return_value = response(pdf("okay"))
    resource = load_catalog().get(SOURCE)
    BoundedFetcher(transport=transport, max_bytes=1024, timeout=2).fetch(resource)
    assert transport.get.call_args.args == (resource.download_url,)
    assert set(transport.get.call_args.kwargs) == {"timeout", "max_bytes"}
    assert transport.get.call_args.kwargs["max_bytes"] == 1024


def test_per_resource_import_lock_is_nonblocking_and_exclusive(cache_dir: Path) -> None:
    lib = library(cache_dir, response(pdf("DSCR")))
    with lib.cache.import_lock(SOURCE):
        with pytest.raises(ValueError, match="already in progress"):
            lib.import_resource(SOURCE)
    assert lib.import_resource(SOURCE).status == "imported"


def test_fifo_and_hardlink_cache_attacks_are_rejected(cache_dir: Path) -> None:
    cache_dir.mkdir()
    folder = cache_dir / SOURCE
    folder.mkdir()
    os.mkfifo(folder / "current.json")
    with pytest.raises(ValueError, match="regular file"):
        CacheStore(cache_dir).current(SOURCE)
    (folder / "current.json").unlink()
    outside = cache_dir.parent / "external.json"
    outside.write_bytes(b"SECRET_FIXTURE")
    os.link(outside, folder / "current.json")
    with pytest.raises(ValueError, match="regular file"):
        CacheStore(cache_dir).current(SOURCE)


def test_new_git_checkout_created_after_cache_construction_is_rejected(cache_dir: Path) -> None:
    store = CacheStore(cache_dir)
    cache_dir.parent.joinpath(".git").mkdir()
    with pytest.raises(ValueError, match="Git"):
        with store.import_lock(SOURCE):
            pytest.fail("Must not write in a Git checkout")


def test_pdf_extraction_budget_is_enforced_on_real_document(cache_dir: Path) -> None:
    lib = library(cache_dir, response(pdf("a" * 80001)))
    with pytest.raises(ValueError, match="PDF parsing failed"):
        lib.import_resource(SOURCE)
    assert lib.cache.current(SOURCE) is None


def test_catalog_change_and_citation_tampering_refuse_retrieval(cache_dir: Path) -> None:
    lib = library(cache_dir, response(pdf("DSCR official text")))
    lib.import_resource(SOURCE)
    lib.catalog_sha256 = "0" * 64
    with pytest.raises(ValueError, match="Catalog changed"):
        lib.search(SearchRequest(query="DSCR"))


@pytest.mark.parametrize("budget", [100, 800, 2000, 4000, 5999, 6000, 12000, 20000])
def test_complete_json_retrieval_budget_is_never_exceeded(cache_dir: Path, budget: int) -> None:
    lib = library(cache_dir, response(pdf("DSCR " * 300, "DSCR " * 300)))
    lib.import_resource(SOURCE)
    result = lib.search(SearchRequest(query="DSCR", max_chars=budget))
    assert len(result.model_dump_json()) <= budget


def test_reference_only_cannot_be_fetched_even_outside_library() -> None:
    resource = load_catalog().get("openstax-principles-finance-2e-2026")
    transport = Transport()
    with pytest.raises(FetchError, match="REFERENCE_ONLY"):
        BoundedFetcher(transport=transport).fetch(resource)
    assert not transport.urls


def test_https_total_deadline_stops_dripping_response_headers() -> None:
    client, server = socket.socketpair()
    finished = threading.Event()
    connection = Mock()

    def drip() -> None:
        try:
            while not finished.wait(0.005):
                server.sendall(b"x")
        except OSError:
            pass

    def headers() -> None:
        while client.recv(1):
            pass
        raise ConnectionResetError("Interrupted headers")

    connection.getresponse.side_effect = headers
    thread = threading.Thread(target=drip, daemon=True)
    thread.start()
    try:
        with (
            patch("cre_brain.knowledge.fetch.resolve_public", return_value="8.8.8.8"),
            patch(
                "cre_brain.knowledge.fetch.socket.create_connection", return_value=client
            ) as connect,
            patch("cre_brain.knowledge.fetch.ssl.create_default_context") as tls,
            patch("cre_brain.knowledge.fetch.http.client.HTTPSConnection", return_value=connection),
        ):
            tls.return_value.wrap_socket.return_value = client
            start = time.monotonic()
            with pytest.raises(FetchError):
                PublicHTTPS().get(
                    load_catalog().get(SOURCE).download_url, timeout=0.15, max_bytes=1024
                )
            assert time.monotonic() - start < 2
            assert connect.call_args.args == (("8.8.8.8", 443),)
            assert tls.return_value.wrap_socket.call_args.kwargs == {
                "server_hostname": "www.occ.gov"
            }
            headers_sent = connection.request.call_args.kwargs["headers"]
            assert set(headers_sent) == {"User-Agent", "Accept", "Accept-Encoding"}
            assert headers_sent["Accept-Encoding"] == "identity"
            connection.close.assert_called_once()
    finally:
        finished.set()
        client.close()
        server.close()
        thread.join(timeout=1)


def test_reference_hits_do_not_validate_as_canonical_deal_evidence(cache_dir: Path) -> None:
    lib = library(cache_dir, response(pdf("DSCR 1.25 net operating income.")))
    lib.import_resource(SOURCE)
    hit = lib.search(SearchRequest(query="DSCR")).hits[0]
    assert hit.evidence_role == "public_reference_not_deal_fact"
    for model in (Fact, CalcResult):
        with pytest.raises(ValidationError):
            model.model_validate(hit.model_dump())
