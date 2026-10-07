"""Canonical append-only storage seam; implementations must enforce tenant scope."""

from typing import Protocol, TypeVar

from pydantic import BaseModel

from cre_brain.domain.base import TenantScope

RecordT = TypeVar("RecordT", bound=BaseModel)


class VersionedStore(Protocol[RecordT]):
    def append(self, record: RecordT, *, scope: TenantScope) -> RecordT: ...

    def get(
        self, record_id: str, *, scope: TenantScope, version: int | None = None
    ) -> RecordT | None: ...
