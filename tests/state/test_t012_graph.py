from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, select

from cre_brain.domain.base import TenantScope
from cre_brain.state.graph import DependencyGraph, GraphCycle
from cre_brain.state.schema import edges, metadata

SCOPE = TenantScope(user_id="analyst", firm_id="firm")


@pytest.fixture
def graph(tmp_path) -> DependencyGraph:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'graph.sqlite'}")
    metadata.create_all(engine)
    return DependencyGraph(engine, release_id="test-release")


def test_t012_ac1_graph_duplicate_edge_is_idempotent_and_tenant_scoped(graph) -> None:
    graph.add_edge("rent", "noi", scope=SCOPE)
    graph.add_edge("rent", "noi", scope=SCOPE)
    with graph.engine.connect() as connection:
        assert len(connection.execute(select(edges)).all()) == 1
    other = TenantScope(user_id="other-user", firm_id="firm")
    graph.add_edge("noi", "rent", scope=other)
    with graph.engine.connect() as connection:
        assert len(connection.execute(select(edges)).all()) == 2


@pytest.mark.parametrize("cycle", [("c", "a"), ("b", "a"), ("a", "a")])
def test_t012_ac3_graph_rejects_cycle_before_any_write(graph, cycle) -> None:
    graph.add_edge("a", "b", scope=SCOPE)
    graph.add_edge("b", "c", scope=SCOPE)
    with pytest.raises(GraphCycle):
        graph.add_edge(*cycle, scope=SCOPE)
    with graph.engine.connect() as connection:
        assert len(connection.execute(select(edges)).all()) == 2


def test_t012_ac3_graph_concurrent_reciprocal_edges_cannot_create_cycle(graph) -> None:
    def add(pair):
        try:
            graph.add_edge(*pair, scope=SCOPE)
            return "added"
        except GraphCycle:
            return "cycle"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(add, [("a", "b"), ("b", "a")]))
    assert sorted(results) == ["added", "cycle"]
