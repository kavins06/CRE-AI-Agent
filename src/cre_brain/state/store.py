"""Append-only domain collections implementing the canonical VersionedStore seam."""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel, TypeAdapter
from sqlalchemy import Connection, Engine, Table, and_, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.elements import ColumnElement

from cre_brain.domain import Assumption, CalcResult, Deliverable, Fact, Question
from cre_brain.domain.base import Identifier, TenantScope
from cre_brain.state.schema import metadata

COLLECTIONS: dict[type[BaseModel], tuple[str, str]] = {
    Fact: ("facts", "fact_id"),
    Assumption: ("assumptions", "key"),
    CalcResult: ("calcs", "calc_id"),
    Question: ("questions", "q_id"),
    Deliverable: ("deliverables", "d_id"),
}
identifier = TypeAdapter(Identifier)


class StateConflict(ValueError):
    """A stale append or conflicting identity; reload before retrying."""


def tenant_filter(table: Table, scope: TenantScope) -> ColumnElement[bool]:
    return and_(table.c.user_id == scope.user_id, table.c.firm_id == scope.firm_id)


def lock_append(connection: Connection, scope: TenantScope, key: tuple[str, ...]) -> None:
    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql("BEGIN IMMEDIATE")
    elif connection.dialect.name == "postgresql":
        encoded = json.dumps([scope.user_id, scope.firm_id, *key]).encode()
        lock_id = int.from_bytes(hashlib.sha256(encoded).digest()[:8], signed=True)
        connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})
    else:
        raise ValueError("State store supports PostgreSQL and unit-test SQLite only")


class SqlVersionedStore[RecordT: BaseModel]:
    def __init__(self, engine: Engine, model: type[RecordT]) -> None:
        if model not in COLLECTIONS:
            raise ValueError("Unsupported versioned domain model")
        self.engine = engine
        self.model = model
        name, self.id_field = COLLECTIONS[model]
        self.table = metadata.tables[name]

    def append(
        self, record: RecordT, *, scope: TenantScope, record_id: str | None = None
    ) -> RecordT:
        validated = self.model.model_validate(record.model_dump())
        native_id = getattr(validated, self.id_field)
        record_id = identifier.validate_python(record_id if record_id is not None else native_id)
        if self.model is not Assumption and record_id != native_id:
            raise StateConflict("Record ID must match its domain identity")
        where = and_(tenant_filter(self.table, scope), self.table.c.record_id == record_id)
        try:
            with self.engine.begin() as connection:
                lock_append(connection, scope, (self.table.name, record_id))
                latest = connection.execute(select(func.max(self.table.c.version)).where(where))
                next_version = int(latest.scalar_one() or 0) + 1
                version = getattr(validated, "version", next_version)
                if version != next_version:
                    raise StateConflict("Append requires the next version; reload current state")
                connection.execute(
                    self.table.insert().values(
                        user_id=scope.user_id,
                        firm_id=scope.firm_id,
                        record_id=record_id,
                        version=version,
                        payload=validated.model_dump(mode="json"),
                    )
                )
        except IntegrityError:
            raise StateConflict(
                "Append conflicts with existing state; reload before retrying"
            ) from None
        return validated

    def get(
        self, record_id: str, *, scope: TenantScope, version: int | None = None
    ) -> RecordT | None:
        record_id = identifier.validate_python(record_id)
        query = select(self.table.c.payload).where(
            tenant_filter(self.table, scope),
            self.table.c.record_id == record_id,
        )
        if version is not None:
            query = query.where(self.table.c.version == version)
        query = query.order_by(self.table.c.version.desc()).limit(1)
        with self.engine.connect() as connection:
            payload = connection.execute(query).scalar_one_or_none()
        return None if payload is None else self.model.model_validate(payload)

    def current(self, record_id: str, *, scope: TenantScope) -> RecordT | None:
        return self.get(record_id, scope=scope)
