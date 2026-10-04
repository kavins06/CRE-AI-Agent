from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ResourceId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{0,99}$")]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Disposition = Literal["DOWNLOAD_ALLOWED", "REFERENCE_ONLY"]
DownloadPolicy = Literal["off", "ask", "on"]


class ImportError(ValueError):
    pass


def public_url(url: str) -> str:
    parts = urlsplit(url)
    host = parts.hostname or ""
    if (
        parts.scheme != "https"
        or not host
        or parts.username is not None
        or parts.password is not None
        or parts.port not in (None, 443)
        or parts.fragment
        or parts.query
        or any(c.isspace() or ord(c) < 32 for c in url)
        or host == "sec.gov"
        or host.endswith(".sec.gov")
    ):
        raise ValueError("Only credential-free HTTPS public catalog URLs; SEC is disabled.")
    return url


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Resource(Model):
    id: ResourceId
    aliases: tuple[ResourceId, ...] = ()
    title: str = Field(min_length=1)
    authors: tuple[str, ...]
    publisher: str
    publication_date: str
    canonical_url: str
    download_url: str | None
    allowed_urls: tuple[str, ...] = ()
    format: str
    topics: tuple[str, ...]
    license: str
    license_url: str
    rights_basis: str = Field(min_length=20)
    commercial_reuse_allowed: bool
    disposition: Disposition
    jurisdictions: tuple[Literal["US"], ...] = ()
    applicability: str
    caveats: str
    verified_at: date
    verification_source: str

    @field_validator("canonical_url", "license_url")
    @classmethod
    def safe_url(cls, value: str) -> str:
        # Citation URLs may have public query strings (e.g. U.S. Code section identifiers).
        parsed = urlsplit(value)
        public_url(parsed._replace(query="").geturl())
        if any(c.isspace() or ord(c) < 32 for c in value):
            raise ValueError("Invalid citation URL")
        return value

    @model_validator(mode="after")
    def rights(self) -> Resource:
        if self.disposition == "REFERENCE_ONLY":
            if self.download_url or self.allowed_urls or self.commercial_reuse_allowed:
                raise ValueError("REFERENCE_ONLY cannot authorize ingestion or commercial reuse.")
        elif not (
            self.download_url
            and self.commercial_reuse_allowed
            and self.jurisdictions
            and self.download_url in self.allowed_urls
        ):
            raise ValueError("DOWNLOAD_ALLOWED needs an exact URL, rights basis and jurisdiction.")
        for url in self.allowed_urls:
            public_url(url)
        return self


class Catalog(Model):
    schema_version: Literal[1]
    resources: tuple[Resource, ...]

    @model_validator(mode="after")
    def unique(self) -> Catalog:
        names: list[str] = []
        urls: list[str] = []
        for resource in self.resources:
            names.extend((resource.id, *resource.aliases))
            urls.append(resource.canonical_url)
        if len(names) != len(set(names)) or len(urls) != len(set(urls)):
            raise ValueError("Duplicate resource identity or canonical URL")
        return self

    def get(self, resource_id: str) -> Resource:
        for resource in self.resources:
            if resource_id == resource.id or resource_id in resource.aliases:
                return resource
        raise ValueError(
            "Unknown catalog resource ID; arbitrary URLs and local files are prohibited."
        )


class Citation(Model):
    resource_id: ResourceId
    title: str
    source_url: str
    canonical_url: str
    publication_date: str
    license: str
    license_url: str
    page: int | None = Field(default=None, ge=1)
    section: str | None = None
    sha256: Digest | None = None
    retrieved_at: datetime | None = None


class Chunk(Model):
    chunk_id: Digest
    text: str = Field(min_length=1, max_length=2000)
    citation: Citation
    scope: Literal["global_public"] = "global_public"
    evidence_role: Literal["public_reference_not_deal_fact"] = "public_reference_not_deal_fact"


class Artifact(Model):
    resource_id: ResourceId
    sha256: Digest
    chunks_sha256: Digest
    catalog_sha256: Digest
    final_url: str
    retrieved_at: datetime
    byte_count: int = Field(ge=1, le=25_000_000)
    page_count: int = Field(ge=1, le=1000)
    chunk_count: int = Field(ge=1, le=10000)
    parser_version: str
    skipped_pages: tuple[int, ...] = ()


class ImportResult(Model):
    status: Literal[
        "disabled", "pending_confirmation", "imported", "unchanged", "changed_requires_review"
    ]
    resource_id: ResourceId
    artifact: Artifact | None = None
    cache_path: str | None = None


class SearchRequest(Model):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=8, ge=1, le=20)
    max_chars: int = Field(default=12000, ge=100, le=20000)
    scope: Literal["global_public"] = "global_public"


class SearchHit(Model):
    text: str | None = None
    citation: Citation
    score: float
    status: Literal["chunk", "reference_only", "not_cached"]
    applicability: str
    caveats: str
    scope: Literal["global_public"] = "global_public"
    evidence_role: Literal["public_reference_not_deal_fact"] = "public_reference_not_deal_fact"


class SearchResult(Model):
    hits: tuple[SearchHit, ...]
    scope: Literal["global_public"] = "global_public"
