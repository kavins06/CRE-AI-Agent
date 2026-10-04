from __future__ import annotations

import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cre_brain.cli import create_app
from cre_brain.knowledge import CacheStore, KnowledgeLibrary, load_catalog
from cre_brain.knowledge.fetch import BoundedFetcher, FetchError, Response
from cre_brain.knowledge.models import ImportError, SearchRequest


def pdf(*pages: str) -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids ["
        + b" ".join(f"{4 + i * 2} 0 R".encode() for i in range(len(pages)))
        + f"] /Count {len(pages)} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for i, text in enumerate(pages):
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 12 Tf 50 700 Td ({escaped}) Tj ET".encode()
        objects.extend(
            [
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + i * 2} 0 R >>".encode(),
                f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
            ]
        )
    result = b"%PDF-1.4\n"
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    start = len(result)
    result += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    result += b"".join(f"{x:010d} 00000 n \n".encode() for x in offsets[1:])
    return (
        result
        + f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF".encode()
    )


class Transport:
    def __init__(self, *responses: Response) -> None:
        self.responses = iter(responses)
        self.urls: list[str] = []

    def get(self, url: str, *, timeout: float, max_bytes: int) -> Response:
        self.urls.append(url)
        return next(self.responses)


def response(data: bytes, **headers: str) -> Response:
    return Response(status=200, headers={"content-type": "application/pdf", **headers}, body=data)


@pytest.fixture
def cache_dir() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="cre-knowledge-test-") as folder:
        yield Path(folder) / "public-knowledge"


def library(cache_dir: Path, *responses: Response, max_bytes: int = 10_000_000) -> KnowledgeLibrary:
    return KnowledgeLibrary(
        cache=CacheStore(cache_dir),
        fetcher=BoundedFetcher(transport=Transport(*responses), max_bytes=max_bytes),
        download_policy="on",
    )


SOURCE = "mfuv-occ-cre-lending-2022"


def test_catalog_deduplicates_editions_and_preserves_rights() -> None:
    catalog = load_catalog()
    assert len(catalog.resources) == 34
    assert catalog.get("occ-cre-lending-2022").id == SOURCE
    assert catalog.get(SOURCE).commercial_reuse_allowed
    assert catalog.get("openstax-principles-finance-2e-2026").download_url is None
    assert not catalog.get("pnnl-om-best-practices-release-3").commercial_reuse_allowed
    assert all(r.verified_at and r.rights_basis and r.license_url for r in catalog.resources)


def test_license_and_network_policy_fail_closed(cache_dir: Path) -> None:
    transport = Transport()
    lib = KnowledgeLibrary(cache=CacheStore(cache_dir), fetcher=BoundedFetcher(transport=transport))
    assert lib.import_resource(SOURCE).status == "disabled"
    lib.download_policy = "ask"
    assert lib.import_resource(SOURCE).status == "pending_confirmation"
    lib.download_policy = "on"
    with pytest.raises(ImportError, match="REFERENCE_ONLY"):
        lib.import_resource("astm-e2018-24-pca")
    with pytest.raises(ImportError, match="US"):
        lib.import_resource(SOURCE, jurisdiction="CA")
    with pytest.raises(ValueError):
        lib.import_resource("https://www.sec.gov/anything.pdf")
    assert transport.urls == []
    assert not cache_dir.exists()


def test_import_has_usable_citations_and_is_idempotent(cache_dir: Path) -> None:
    data = pdf(
        "Debt service coverage DSCR equals net operating income divided by debt service.",
        "Loan to value LTV is a collateral risk indicator.",
    )
    lib = library(cache_dir, response(data), response(data))
    first = lib.import_resource(SOURCE)
    second = lib.import_resource(SOURCE)
    assert first.status == "imported"
    assert second.status == "unchanged"
    assert first.artifact == second.artifact
    result = lib.search(SearchRequest(query="DSCR net operating income"))
    hit = result.hits[0]
    assert "DSCR" in hit.text
    assert hit.citation.page == 1
    assert hit.citation.sha256 == first.artifact.sha256
    assert hit.citation.retrieved_at
    assert hit.citation.source_url == load_catalog().get(SOURCE).download_url
    assert hit.evidence_role == "public_reference_not_deal_fact"
    assert hit.scope == "global_public"


def test_hash_change_needs_explicit_acceptance_and_preserves_old(cache_dir: Path) -> None:
    old, new = pdf("DSCR old official text."), pdf("DSCR new official text.")
    lib = library(cache_dir, response(old), response(new), response(new))
    first = lib.import_resource(SOURCE)
    changed = lib.import_resource(SOURCE)
    assert changed.status == "changed_requires_review"
    assert lib.cache.current(SOURCE) == first.artifact
    accepted = lib.import_resource(SOURCE, accept_change=True)
    assert accepted.artifact.sha256 != first.artifact.sha256
    assert lib.cache.artifact(SOURCE, first.artifact.sha256).sha256 == first.artifact.sha256
    assert "new official" in lib.search(SearchRequest(query="DSCR")).hits[0].text


@pytest.mark.parametrize(
    "data,headers",
    [
        (b"<html>challenge</html>", {}),
        (b"%PDF-1.4 corrupt", {}),
        (pdf("okay"), {"content-type": "text/html"}),
        (pdf("okay"), {"content-encoding": "gzip"}),
        (pdf("okay"), {"content-length": "999999999"}),
    ],
)
def test_rejects_corrupt_challenge_or_unbounded_content(
    cache_dir: Path, data: bytes, headers: dict[str, str]
) -> None:
    lib = library(cache_dir, response(data, **headers))
    with pytest.raises((ImportError, FetchError)):
        lib.import_resource(SOURCE)
    assert lib.cache.current(SOURCE) is None


def test_actual_body_size_is_bounded(cache_dir: Path) -> None:
    lib = library(cache_dir, response(pdf("a" * 10000)), max_bytes=100)
    with pytest.raises(FetchError, match="size"):
        lib.import_resource(SOURCE)


@pytest.mark.parametrize(
    "location",
    [
        "http://www.occ.gov/file.pdf",
        "https://www.sec.gov/file.pdf",
        "https://user:password@www.occ.gov/file.pdf",
        "https://127.0.0.1/file.pdf",
        "https://www.occ.gov/other.pdf",
        "file:///etc/passwd",
        "https://www.occ.gov:444/other.pdf",
    ],
)
def test_redirect_allowlist_blocks_attacks_before_request(cache_dir: Path, location: str) -> None:
    transport = Transport(Response(status=302, headers={"location": location}, body=b""))
    lib = KnowledgeLibrary(
        cache=CacheStore(cache_dir),
        fetcher=BoundedFetcher(transport=transport),
        download_policy="on",
    )
    with pytest.raises(FetchError):
        lib.import_resource(SOURCE)
    assert len(transport.urls) == 1


def test_approved_redirect_works_and_cycles_are_bounded(cache_dir: Path) -> None:
    r = load_catalog().get(SOURCE)
    alternate = next(url for url in r.allowed_urls if url != r.download_url)
    transport = Transport(Response(302, {"location": alternate}, b""), response(pdf("DSCR")))
    lib = KnowledgeLibrary(
        cache=CacheStore(cache_dir),
        fetcher=BoundedFetcher(transport=transport),
        download_policy="on",
    )
    assert lib.import_resource(SOURCE).artifact.final_url == alternate
    transport = Transport(*(Response(302, {"location": r.download_url}, b"") for _ in range(5)))
    with pytest.raises(FetchError, match="redirect"):
        BoundedFetcher(transport=transport).fetch(r)
    assert len(transport.urls) <= 4


def test_cache_rejects_traversal_symlink_and_repository(cache_dir: Path) -> None:
    cache = CacheStore(cache_dir)
    with pytest.raises(ValueError):
        cache.current("../../etc")
    cache_dir.mkdir()
    (cache_dir / SOURCE).symlink_to(cache_dir.parent, target_is_directory=True)
    with pytest.raises(ValueError, match="path|symlink"):
        library(cache_dir, response(pdf("DSCR"))).import_resource(SOURCE)
    with pytest.raises(ValueError, match="Git"):
        CacheStore(Path(__file__).parents[2] / ".cache" / "knowledge")


def test_cache_tampering_is_detected_before_retrieval(cache_dir: Path) -> None:
    lib = library(cache_dir, response(pdf("DSCR original.")))
    imported = lib.import_resource(SOURCE)
    path = cache_dir / SOURCE / imported.artifact.sha256 / "document.pdf"
    path.write_bytes(pdf("DSCR injected."))
    with pytest.raises(ValueError, match="hash"):
        lib.search(SearchRequest(query="DSCR"))


def test_retrieval_relevance_caps_and_reference_only_fallback(cache_dir: Path) -> None:
    lib = library(
        cache_dir,
        response(
            pdf("DSCR net operating income and repayment capacity.", "maintenance unrelated noise")
        ),
    )
    lib.import_resource(SOURCE)
    result = lib.search(SearchRequest(query="DSCR", limit=1, max_chars=6000))
    assert len(result.hits) == 1 and "DSCR" in result.hits[0].text
    assert len(result.model_dump_json()) <= 6000
    refs = lib.search(SearchRequest(query="property condition assessments"))
    astm = next(x for x in refs.hits if x.citation.resource_id == "astm-e2018-24-pca")
    assert astm.text is None and astm.status == "reference_only"
    assert astm.citation.page is None
    assert not lib.search(SearchRequest(query="zzzz_no_match")).hits
    assert lib.search(SearchRequest(query="DSCR")).hits[0].citation.sha256


def test_excludes_third_party_pages_and_has_no_tenant_ingest_api(cache_dir: Path) -> None:
    lib = library(
        cache_dir,
        response(
            pdf(
                "DSCR official government text.",
                "Copyright third party PRIVATE_FIXTURE_SENTINEL lease secret",
                "Missing Children NCMEC photos external work",
            )
        ),
    )
    imported = lib.import_resource(SOURCE)
    assert imported.artifact.skipped_pages == (2, 3)
    assert not lib.search(SearchRequest(query="PRIVATE_FIXTURE_SENTINEL")).hits
    assert not hasattr(lib, "import_path")
    with pytest.raises(ValueError):
        SearchRequest(query="DSCR", scope="firm_private")


def test_cli_catalog_search_and_default_disabled_import(cache_dir: Path) -> None:
    runner = CliRunner()
    app = create_app()
    assert runner.invoke(app, ["knowledge", "catalog"]).exit_code == 0
    result = runner.invoke(
        app, ["knowledge", "search", "property condition", "--cache-dir", str(cache_dir)]
    )
    assert result.exit_code == 0 and "reference_only" in result.stdout
    result = runner.invoke(app, ["knowledge", "import", SOURCE, "--cache-dir", str(cache_dir)])
    assert result.exit_code == 0 and "disabled" in result.stdout
