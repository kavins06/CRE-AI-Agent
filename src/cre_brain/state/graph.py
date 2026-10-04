"""Tenant-scoped dependency DAG and durable, event-sourced invalidation."""

from graphlib import CycleError, TopologicalSorter
from heapq import heappop, heappush

from pydantic import TypeAdapter
from sqlalchemy import Connection, Engine, select

from cre_brain.domain.base import Identifier, TenantScope
from cre_brain.state.schema import edges
from cre_brain.state.store import lock_append, tenant_filter

identifier = TypeAdapter(Identifier)


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
