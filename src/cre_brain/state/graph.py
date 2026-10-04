"""Tenant-scoped dependency DAG and durable, event-sourced invalidation."""

import secrets
from datetime import UTC, datetime, timedelta
from graphlib import CycleError, TopologicalSorter
from heapq import heappop, heappush

from pydantic import TypeAdapter
from sqlalchemy import Connection, Engine, select

from cre_brain.domain import AgentEvent
from cre_brain.domain.base import Identifier, TenantScope
from cre_brain.state.events import _append_locked
from cre_brain.state.schema import edges, events
from cre_brain.state.store import lock_append, tenant_filter

identifier = TypeAdapter(Identifier)


def _new_event_id(timestamp: datetime) -> str:
    milliseconds = (timestamp - datetime(1970, 1, 1, tzinfo=UTC)) // timedelta(milliseconds=1)
    value = int.from_bytes(milliseconds.to_bytes(6, "big") + secrets.token_bytes(10), "big")
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    return "".join(alphabet[(value >> shift) & 31] for shift in range(125, -1, -5))


class GraphCycle(ValueError):
    """A dependency would form a cycle and is not persisted."""


def _adjacency(connection: Connection, scope: TenantScope) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    query = select(edges.c.src_id, edges.c.dst_id).where(tenant_filter(edges, scope))
    for source, destination in connection.execute(query):
        graph.setdefault(source, set()).add(destination)
        graph.setdefault(destination, set())
    return graph


def _topological_order(graph: dict[str, set[str]]) -> list[str]:
    predecessors: dict[str, set[str]] = {node: set() for node in graph}
    for source, destinations in graph.items():
        for destination in destinations:
            predecessors[destination].add(source)
    sorter = TopologicalSorter(predecessors)
    try:
        sorter.prepare()
    except CycleError as exc:
        raise GraphCycle("Dependency graph contains a cycle") from exc
    ready: list[str] = []
    result: list[str] = []
    while sorter.is_active():
        for node in sorter.get_ready():
            heappush(ready, node)
        node = heappop(ready)
        result.append(node)
        sorter.done(node)
    return result


class DependencyGraph:
    def __init__(self, engine: Engine, *, release_id: str, runner: str = "state") -> None:
        self.engine = engine
        self.release_id = identifier.validate_python(release_id)
        self.runner = identifier.validate_python(runner)

    def add_edge(self, source: str, destination: str, *, scope: TenantScope) -> None:
        source = identifier.validate_python(source)
        destination = identifier.validate_python(destination)
        with self.engine.begin() as connection:
            lock_append(connection, scope, ("graph",))
            graph = _adjacency(connection, scope)
            if destination in graph.get(source, set()):
                return
            graph.setdefault(source, set()).add(destination)
            graph.setdefault(destination, set())
            _topological_order(graph)
            connection.execute(
                edges.insert().values(
                    user_id=scope.user_id,
                    firm_id=scope.firm_id,
                    src_id=source,
                    dst_id=destination,
                )
            )

    def mark_stale(
        self, record_id: str, *, task_id: str, scope: TenantScope, cause_id: str | None = None
    ) -> list[str]:
        record_id = identifier.validate_python(record_id)
        task_id = identifier.validate_python(task_id)
        with self.engine.begin() as connection:
            lock_append(connection, scope, ("graph",))
            graph = _adjacency(connection, scope)
            pending = list(graph.get(record_id, set()))
            descendants: set[str] = set()
            while pending:
                node = pending.pop()
                if node not in descendants:
                    descendants.add(node)
                    pending.extend(graph.get(node, set()))
            ordered = [node for node in _topological_order(graph) if node in descendants]
            if connection.dialect.name == "postgresql":
                lock_append(connection, scope, ("events", task_id))
            for node in ordered:
                timestamp = datetime.now(UTC)
                event = AgentEvent(
                    event_id=_new_event_id(timestamp),
                    task_id=task_id,
                    seq=None,
                    origin=None,
                    ts=timestamp,
                    source="system",
                    kind="stale",
                    cause_id=cause_id,
                    release_id=self.release_id,
                    runner=self.runner,
                    payload={"item_id": node, "changed_id": record_id},
                )
                _append_locked(connection, event, scope)
            return ordered

    def stale_items(self, task_id: str, *, scope: TenantScope) -> list[str]:
        task_id = identifier.validate_python(task_id)
        with self.engine.connect() as connection:
            query = (
                select(events.c.payload)
                .where(
                    tenant_filter(events, scope),
                    events.c.task_id == task_id,
                )
                .order_by(events.c.seq)
            )
            stale: set[str] = set()
            for payload in connection.execute(query).scalars():
                event = AgentEvent.model_validate(payload)
                if event.kind == "stale":
                    stale.add(identifier.validate_python(event.payload["item_id"]))
            graph = _adjacency(connection, scope)
            for node in stale:
                graph.setdefault(node, set())
            return [node for node in _topological_order(graph) if node in stale]
