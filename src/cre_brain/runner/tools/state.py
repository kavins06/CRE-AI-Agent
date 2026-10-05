"""Atomic operations over existing scoped state tables; no parallel state registry."""

import hashlib
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Connection, select

from cre_brain.domain import AgentEvent, Deliverable
from cre_brain.domain.base import TenantScope
from cre_brain.domain.models import AgentEventKind
from cre_brain.runner.tools.contracts import AuthenticatedContext
from cre_brain.runner.tools.json_io import canonical
from cre_brain.state.events import _append_locked
from cre_brain.state.graph import _adjacency, _new_event_id, _topological_order
from cre_brain.state.schema import edges, events, metadata
from cre_brain.state.store import COLLECTIONS, StateConflict, tenant_filter


class ToolState:
    def __init__(self, connection: Connection, context: AuthenticatedContext) -> None:
        self.connection = connection
        self.context = context
        self.scope: TenantScope = context.scope

    def history(self, *, task_only: bool = True) -> list[AgentEvent]:
        query = select(events.c.payload).where(tenant_filter(events, self.scope))
        if task_only:
            query = query.where(events.c.task_id == self.context.task_id)
            query = query.order_by(events.c.seq)
        return [AgentEvent.model_validate(p) for p in self.connection.execute(query).scalars()]

    def event(self, kind: AgentEventKind, payload: dict[str, Any]) -> None:
        timestamp = datetime.now(UTC)
        event = AgentEvent(
            event_id=_new_event_id(timestamp),
            task_id=self.context.task_id,
            seq=None,
            origin=None,
            ts=timestamp,
            source="tool",
            kind=kind,
            cause_id=None,
            release_id=self.context.release_id,
            runner="tools",
            payload=payload,
        )
        # Publication release metadata must fit the streamable envelope. Existing
        # workbook state bindings contain full descriptors; their storage contract
        # predates the release boundary and is not a tool JSON response.
        if kind == "deliverable":
            canonical(event.model_dump(mode="json", warnings=False))
        _append_locked(self.connection, event, self.scope)

    def records[T: BaseModel](self, model: type[T], identity: str) -> list[T]:
        table = metadata.tables[COLLECTIONS[model][0]]
        query = (
            select(table.c.payload)
            .where(tenant_filter(table, self.scope), table.c.record_id == identity)
            .order_by(table.c.version)
        )
        return [model.model_validate(p) for p in self.connection.execute(query).scalars()]

    def current[T: BaseModel](self, model: type[T], identity: str) -> T | None:
        records = self.records(model, identity)
        return records[-1] if records else None

    def all_current[T: BaseModel](self, model: type[T]) -> list[T]:
        table = metadata.tables[COLLECTIONS[model][0]]
        identities = self.connection.execute(
            select(table.c.record_id).where(tenant_filter(table, self.scope)).distinct()
        ).scalars()
        records = [self.current(model, identity) for identity in identities]
        return [record for record in records if record is not None]

    def append[T: BaseModel](
        self, record: T, *, identity: str | None = None, publication: bytes | None = None
    ) -> T:
        record = type(record).model_validate(record.model_dump(warnings=False))
        table_name, id_field = COLLECTIONS[type(record)]
        native_id = getattr(record, id_field)
        identity = identity or native_id
        records = self.records(type(record), identity)
        version = len(records) + 1
        if getattr(record, "version", version) != version:
            raise StateConflict("Reload current version before appending")
        if publication is not None and (
            not isinstance(record, Deliverable) or record.status != "final"
        ):
            raise ValueError("Publication requires a final canonical deliverable")
        self.connection.execute(
            metadata.tables[table_name]
            .insert()
            .values(
                user_id=self.scope.user_id,
                firm_id=self.scope.firm_id,
                record_id=identity,
                version=version,
                payload=record.model_dump(mode="json", warnings=False),
                **({"publication": publication} if publication is not None else {}),
            )
        )
        return record

    def fresh(self, identity: str) -> bool:
        return not any(
            e.kind == "stale" and e.payload.get("item_id") == identity
            for e in self.history(task_only=False)
        )

    def edge(self, source: str, destination: str) -> None:
        graph = _adjacency(self.connection, self.scope)
        if destination in graph.get(source, set()):
            return
        graph.setdefault(source, set()).add(destination)
        graph.setdefault(destination, set())
        _topological_order(graph)
        self.connection.execute(
            edges.insert().values(
                user_id=self.scope.user_id,
                firm_id=self.scope.firm_id,
                src_id=source,
                dst_id=destination,
            )
        )

    def invalidate(self, identity: str) -> None:
        graph = _adjacency(self.connection, self.scope)
        pending = list(graph.get(identity, set()))
        seen: set[str] = set()
        while pending:
            node = pending.pop()
            if node not in seen:
                seen.add(node)
                pending.extend(graph.get(node, set()))
        for node in _topological_order(graph):
            if node in seen:
                self.event("stale", {"item_id": node, "changed_id": identity})

    def binding(self, identity: str, category: str) -> dict[str, Any] | None:
        matches = [
            e
            for e in self.history(task_only=False)
            if e.payload.get("binding") == category and e.payload.get("identity") == identity
        ]
        if not matches:
            return None
        latest = max(matches, key=lambda event: (event.ts, event.seq or 0, event.event_id))
        return dict(latest.payload)


def fingerprint(record: BaseModel) -> str:
    return hashlib.sha256(record.model_dump_json(warnings=False).encode()).hexdigest()
