from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from typing import Literal, Protocol

from pydantic import Field

from cre_brain.knowledge.cache import sha256
from cre_brain.knowledge.models import Chunk, Citation, ImportError, Model, Resource


class Page(Model):
    page: int = Field(ge=1, le=1000)
    text: str = Field(min_length=1, max_length=80000)


class ParsedDocument(Model):
    pages: tuple[Page, ...] = Field(min_length=1, max_length=1000)
    skipped_pages: tuple[int, ...]
    page_count: int = Field(ge=1, le=1000)
    parser_version: Literal["pypdf-6.19.0/text-v1"]


class Parser(Protocol):
    def parse(self, data: bytes) -> ParsedDocument: ...


class PdfParser:
    def __init__(self, timeout: float = 40) -> None:
        if not 0 < timeout <= 60:
            raise ValueError("PDF parser requires a bounded timeout")
        self.timeout = timeout

    def parse(self, data: bytes) -> ParsedDocument:
        try:
            result = subprocess.run(
                [sys.executable, "-I", "-m", "cre_brain.knowledge._pdf_worker"],
                input=data,
                capture_output=True,
                timeout=self.timeout,
                check=True,
                env={"PATH": "/usr/bin:/bin", "PYTHONUTF8": "1"},
            )
            if len(result.stdout) > 20_000_000:
                raise ImportError("Parsed document exceeds size limit")
            return ParsedDocument.model_validate(json.loads(result.stdout))
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            raise ImportError(
                "PDF parsing failed: corrupt/encrypted/non-text/over-budget PDF, or missing "
                "security-reviewed pypdf 6.19.0. Install the patched documents extra."
            ) from exc


def citation(
    resource: Resource,
    *,
    source_url: str | None = None,
    digest: str | None = None,
    retrieved_at: datetime | None = None,
    page: int | None = None,
    section: str | None = None,
) -> Citation:
    return Citation(
        resource_id=resource.id,
        title=resource.title,
        source_url=source_url or resource.canonical_url,
        canonical_url=resource.canonical_url,
        publication_date=resource.publication_date,
        license=resource.license,
        license_url=resource.license_url,
        page=page,
        section=section,
        sha256=digest,
        retrieved_at=retrieved_at,
    )


def chunks_for(
    resource: Resource,
    document: ParsedDocument,
    *,
    source_url: str,
    digest: str,
    retrieved_at: datetime,
) -> tuple[Chunk, ...]:
    chunks: list[Chunk] = []
    for page in document.pages:
        lines = [line.strip() for line in page.text.splitlines() if line.strip()]
        section = lines[0][:120] if len(lines) > 1 else None
        text = " ".join(page.text.split())
        while text:
            end = min(1600, len(text))
            if end < len(text):
                boundary = text.rfind(" ", 0, end)
                if boundary > end // 2:
                    end = boundary
            piece, text = text[:end], text[end:].lstrip()
            chunks.append(
                Chunk(
                    chunk_id=sha256(f"{resource.id}:{digest}:{page.page}:{len(chunks)}".encode()),
                    text=piece,
                    citation=citation(
                        resource,
                        source_url=source_url,
                        digest=digest,
                        retrieved_at=retrieved_at,
                        page=page.page,
                        section=section,
                    ),
                )
            )
            if len(chunks) > 10000:
                raise ImportError("Document exceeds chunk limit")
    return tuple(chunks)
