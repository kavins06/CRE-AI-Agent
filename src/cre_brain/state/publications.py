"""Host-only lossless bytes in the canonical deliverable's protected SQL column.

A bounded JSON header precedes raw bodies; neither belongs to domain payloads or
streamable events. Prepare the entire blob before the final deadline, then INSERT
it with the final row in the caller's existing transaction. Whole-row immutable
state guards protect this column too. No mirror file is used during retrieval.
"""

import struct
from typing import Any

from pydantic import Field
from sqlalchemy import Connection, select

from cre_brain.domain import Deliverable
from cre_brain.domain.base import TenantScope
from cre_brain.gates.snapshot import ArtifactSnapshot
from cre_brain.runner.tools import files
from cre_brain.runner.tools.contracts import ID, Artifact, AuthenticatedContext, Boundary
from cre_brain.runner.tools.json_io import MAX_BYTES, canonical, parse
from cre_brain.state.schema import metadata
from cre_brain.state.store import tenant_filter

MAX_PUBLICATION_FILES = 5
MAX_PUBLICATION_BYTES = 32 * 1024 * 1024
MAX_STORED_BYTES = 32 * 1024 * 1024 + MAX_BYTES + 4


class PublicationReference(Boundary):
    publication_id: str = Field(pattern=r"^publication-[a-f0-9]{64}$")
    path: str = Field(min_length=1, max_length=4096)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size: int = Field(strict=True, ge=0, le=files.MAX_ARTIFACT_BYTES)


class Publication(Boundary):
    publication_id: str = Field(pattern=r"^publication-[a-f0-9]{64}$")
    path: str = Field(min_length=1, max_length=4096)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    body: bytes = Field(repr=False, max_length=files.MAX_ARTIFACT_BYTES)

    def reference(self) -> dict[str, str]:
        return {"publication_id": self.publication_id, "path": self.path, "sha256": self.sha256}


class Header(Boundary):
    scope: TenantScope
    task_id: ID
    deal_id: ID
    release_id: ID
    version: int = Field(strict=True, ge=2)
    anchor: Artifact
    entries: tuple[PublicationReference, ...] = Field(min_length=1, max_length=5)


def prepare(
    context: AuthenticatedContext, anchor: Artifact, snapshot: ArtifactSnapshot
) -> tuple[Publication, ...]:
    bodies = (
        (anchor.deliverable.path, snapshot.data, snapshot.sha256),
        *((str(c.path), c.data, c.sha256) for c in snapshot.companions),
    )
    if (
        len(bodies) > MAX_PUBLICATION_FILES
        or len({path for path, _, _ in bodies}) != len(bodies)
        or sum(len(body) for _, body, _ in bodies) > MAX_PUBLICATION_BYTES
        or any(len(body) > files.MAX_ARTIFACT_BYTES for _, body, _ in bodies)
    ):
        raise ValueError("Publication exceeds aggregate, file, count or unique path bounds")
    result = []
    for path, body, digest in bodies:
        if files.digest(body) != digest:
            raise ValueError("Publication bytes do not match authenticated snapshot")
        identity = canonical(
            [
                context.scope.model_dump(),
                context.task_id,
                context.deal_id,
                context.release_id,
                anchor.deliverable.d_id,
                anchor.deliverable.version + 1,
                path,
                digest,
            ]
        )
        result.append(
            Publication(
                publication_id="publication-" + files.digest(identity.encode()),
                path=path,
                sha256=digest,
                body=body,
            )
        )
    canonical([item.reference() for item in result])
    return tuple(result)


def encode(
    context: AuthenticatedContext, anchor: Artifact, prepared: tuple[Publication, ...]
) -> bytes:
    header = Header(
        scope=context.scope,
        task_id=context.task_id,
        deal_id=context.deal_id,
        release_id=context.release_id,
        version=anchor.deliverable.version + 1,
        anchor=anchor,
        entries=tuple(PublicationReference(**p.reference(), size=len(p.body)) for p in prepared),
    )
    encoded = canonical(header.model_dump(mode="json")).encode()
    body = struct.pack(">I", len(encoded)) + encoded + b"".join(p.body for p in prepared)
    if len(body) > MAX_STORED_BYTES:
        raise ValueError("Protected publication exceeds column bound")
    return body


def load_release(
    connection: Connection,
    context: AuthenticatedContext,
    identity: str,
    version: int,
) -> tuple[Artifact, tuple[Publication, ...]]:
    table = metadata.tables["deliverables"]
    row = connection.execute(
        select(table.c.payload, table.c.publication).where(
            tenant_filter(table, context.scope),
            table.c.record_id == identity,
            table.c.version == version,
        )
    ).one_or_none()
    if row is None or not isinstance(row.publication, bytes):
        raise ValueError("Missing protected publication")
    blob = row.publication
    if len(blob) < 4 or len(blob) > MAX_STORED_BYTES:
        raise ValueError("Invalid protected publication bound")
    size = struct.unpack(">I", blob[:4])[0]
    if not 0 < size <= MAX_BYTES or size + 4 > len(blob):
        raise ValueError("Invalid protected publication header")
    header = Header.model_validate(parse(blob[4 : 4 + size].decode()))
    current = Deliverable.model_validate(row.payload)
    if (
        header.scope != context.scope
        or (header.task_id, header.deal_id, header.release_id, header.version)
        != (context.task_id, context.deal_id, context.release_id, version)
        or header.anchor.deliverable.d_id != identity
        or header.anchor.deliverable.deal_ids != [context.deal_id]
        or header.anchor.deliverable.version + 1 != version
        or current.d_id != identity
        or current.version != version
        or current.status != "final"
        or len(header.entries) > MAX_PUBLICATION_FILES
        or sum(p.size for p in header.entries) > MAX_PUBLICATION_BYTES
    ):
        raise ValueError("Protected publication scope or version mismatch")
    offset = 4 + size
    result = []
    for reference in header.entries:
        body = blob[offset : offset + reference.size]
        offset += reference.size
        if len(body) != reference.size or files.digest(body) != reference.sha256:
            raise ValueError("Invalid protected publication digest")
        result.append(Publication(**reference.model_dump(exclude={"size"}), body=body))
    if offset != len(blob) or len({p.path for p in result}) != len(result):
        raise ValueError("Invalid protected publication bodies")
    return header.anchor, tuple(result)


def references(prepared: tuple[Publication, ...]) -> list[dict[str, Any]]:
    return [p.reference() for p in prepared]
