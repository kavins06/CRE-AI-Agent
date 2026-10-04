from __future__ import annotations

import math
import re
from collections import Counter
from datetime import UTC, datetime
from typing import Protocol

from cre_brain.knowledge.cache import CHUNKS, CacheStore, sha256
from cre_brain.knowledge.catalog import catalog_bytes, load_catalog
from cre_brain.knowledge.fetch import BoundedFetcher
from cre_brain.knowledge.models import (
    Artifact,
    DownloadPolicy,
    ImportError,
    ImportResult,
    Resource,
    SearchHit,
    SearchRequest,
    SearchResult,
)
from cre_brain.knowledge.parse import Parser, PdfParser, chunks_for, citation


class KnowledgeProvider(Protocol):
    """Global public references only; firm/user memory belongs in separate providers."""

    def search(self, request: SearchRequest) -> SearchResult: ...


def tokens(text: str) -> Counter[str]:
    return Counter(re.findall(r"[a-z0-9]+", text.lower()))


class KnowledgeLibrary:
    def __init__(
        self,
        *,
        cache: CacheStore | None = None,
        fetcher: BoundedFetcher | None = None,
        parser: Parser | None = None,
        download_policy: DownloadPolicy = "off",
    ) -> None:
        self.catalog = load_catalog()
        self.catalog_sha256 = sha256(catalog_bytes())
        self.cache = cache if cache is not None else CacheStore()
        self.fetcher = fetcher if fetcher is not None else BoundedFetcher()
        self.parser = parser if parser is not None else PdfParser()
        self.download_policy = download_policy

    def import_resource(
        self,
        resource_id: str,
        *,
        jurisdiction: str = "US",
        accept_change: bool = False,
    ) -> ImportResult:
        resource = self.catalog.get(resource_id)
        if self.download_policy == "off":
            return ImportResult(status="disabled", resource_id=resource.id)
        if self.download_policy == "ask":
            return ImportResult(status="pending_confirmation", resource_id=resource.id)
        if self.download_policy != "on":
            raise ImportError("Unknown policy; fail closed")
        if resource.disposition != "DOWNLOAD_ALLOWED" or not resource.commercial_reuse_allowed:
            raise ImportError("REFERENCE_ONLY: metadata/citation only; no download or ingestion")
        if jurisdiction not in resource.jurisdictions:
            raise ImportError(
                "Only US reuse is established; other jurisdictions require rights review"
            )
        with self.cache.import_lock(resource.id):
            return self._import(resource, accept_change=accept_change)

    def _import(self, resource: Resource, *, accept_change: bool) -> ImportResult:
        previous = self.cache.current(resource.id)
        downloaded = self.fetcher.fetch(resource)
        digest = sha256(downloaded.body)
        if previous and previous.sha256 == digest:
            if previous.catalog_sha256 != self.catalog_sha256:
                raise ImportError(
                    "Catalog rights changed; remove/review this cache before reimport"
                )
            return ImportResult(
                status="unchanged",
                resource_id=resource.id,
                artifact=previous,
                cache_path=str(self.cache.path(previous)),
            )
        document = self.parser.parse(downloaded.body)
        retrieved_at = datetime.now(UTC)
        chunks = chunks_for(
            resource,
            document,
            source_url=downloaded.final_url,
            digest=digest,
            retrieved_at=retrieved_at,
        )
        metadata = Artifact(
            resource_id=resource.id,
            sha256=digest,
            chunks_sha256=sha256(CHUNKS.dump_json(chunks)),
            catalog_sha256=self.catalog_sha256,
            final_url=downloaded.final_url,
            retrieved_at=retrieved_at,
            byte_count=len(downloaded.body),
            page_count=document.page_count,
            chunk_count=len(chunks),
            parser_version=document.parser_version,
            skipped_pages=document.skipped_pages,
        )
        self.cache.store(metadata, downloaded.body, chunks)
        metadata = self.cache.artifact(resource.id, digest)
        if previous and not accept_change:
            return ImportResult(
                status="changed_requires_review",
                resource_id=resource.id,
                artifact=metadata,
                cache_path=str(self.cache.path(metadata)),
            )
        self.cache.activate(metadata)
        return ImportResult(
            status="imported",
            resource_id=resource.id,
            artifact=metadata,
            cache_path=str(self.cache.path(metadata)),
        )

    def search(self, request: SearchRequest) -> SearchResult:
        candidates: list[tuple[SearchHit, Counter[str]]] = []
        for resource in self.catalog.resources:
            metadata = (
                self.cache.current(resource.id)
                if resource.disposition == "DOWNLOAD_ALLOWED"
                else None
            )
            if metadata:
                if metadata.catalog_sha256 != self.catalog_sha256:
                    raise ValueError("Catalog changed; review cached rights before retrieval")
                if metadata.final_url not in resource.allowed_urls:
                    raise ValueError("Cached source is not allowlisted")
                for chunk in self.cache.chunks(metadata):
                    hit = SearchHit(
                        text=chunk.text,
                        citation=chunk.citation,
                        score=0,
                        status="chunk",
                        applicability=resource.applicability,
                        caveats=resource.caveats,
                    )
                    candidates.append((hit, tokens(chunk.text)))
            hit = SearchHit(
                citation=citation(resource),
                score=0,
                status="reference_only"
                if resource.disposition == "REFERENCE_ONLY"
                else "not_cached",
                applicability=resource.applicability,
                caveats=resource.caveats,
            )
            candidates.append(
                (
                    hit,
                    tokens(
                        " ".join(
                            (
                                resource.title,
                                *resource.topics,
                                resource.applicability,
                            )
                        )
                    ),
                )
            )
        query = set(tokens(request.query))
        frequency = Counter(term for _, words in candidates for term in query if term in words)
        ranked = []
        for hit, words in candidates:
            score = sum(
                math.log(1 + len(candidates) / (1 + frequency[term]))
                * (words[term] / (words[term] + 1))
                for term in query
                if words[term]
            )
            if score:
                # Actual text outranks metadata at comparable lexical relevance.
                score *= 1 if hit.text else 0.4
                ranked.append(hit.model_copy(update={"score": round(score, 6)}))
        ranked.sort(
            key=lambda hit: (
                -hit.score,
                hit.citation.resource_id,
                hit.citation.page or 0,
                hit.text or "",
            )
        )
        selected: list[SearchHit] = []
        remaining = request.max_chars - len(SearchResult(hits=()).model_dump_json())
        for hit in ranked:
            if len(selected) >= request.limit:
                break
            separator = 1 if selected else 0
            cost = len(hit.model_dump_json()) + separator
            # Budget includes citation/rights metadata as well as source text.
            if cost > remaining:
                if hit.text and remaining >= 300:
                    text_budget = (
                        remaining
                        - separator
                        - len(hit.model_copy(update={"text": ""}).model_dump_json())
                    )
                    if text_budget > 0:
                        hit = hit.model_copy(update={"text": hit.text[:text_budget]})
                        cost = len(hit.model_dump_json()) + separator
                if cost > remaining:
                    continue
            selected.append(hit)
            remaining -= cost
        return SearchResult(hits=tuple(selected))
