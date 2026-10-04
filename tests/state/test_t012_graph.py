from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError

from cre_brain.domain.base import TenantScope
from cre_brain.state.events import EventStore
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


def test_t012_ac2_graph_rent_change_invalidates_only_dependent_outputs(graph) -> None:
    for source, destination in (
        ("rent-unit-1", "noi"),
        ("noi", "uw"),
        ("uw", "ic-memo"),
        ("ic-memo", "loi"),
        ("rent-unit-2", "noi"),
        ("other-fact", "other-report"),
    ):
        graph.add_edge(source, destination, scope=SCOPE)
    assert graph.mark_stale("rent-unit-1", task_id="task-a", scope=SCOPE) == [
        "noi",
        "uw",
        "ic-memo",
        "loi",
    ]
    assert graph.stale_items("task-a", scope=SCOPE) == ["noi", "uw", "ic-memo", "loi"]
    assert graph.stale_items("task-b", scope=SCOPE) == []
    assert (
        graph.stale_items("task-a", scope=TenantScope(user_id="other-user", firm_id="firm")) == []
    )
    assert (
        graph.stale_items("task-a", scope=TenantScope(user_id="analyst", firm_id="other-firm"))
        == []
    )
    persisted = EventStore(graph.engine).list("task-a", scope=SCOPE)
    assert [event.seq for event in persisted] == [1, 2, 3, 4]
    assert all(event.kind == "stale" and event.source == "system" for event in persisted)
    assert [event.payload["item_id"] for event in persisted] == ["noi", "uw", "ic-memo", "loi"]
    assert all(event.payload["changed_id"] == "rent-unit-1" for event in persisted)


def test_t012_ac1_graph_diamond_is_topological_deduplicated_and_survives_restart(graph) -> None:
    for source, destination in [("a", "c"), ("a", "b"), ("b", "d"), ("c", "d")]:
        graph.add_edge(source, destination, scope=SCOPE)
    assert graph.mark_stale("a", task_id="task", scope=SCOPE) == ["b", "c", "d"]
    restarted = DependencyGraph(graph.engine, release_id="next-release")
    assert restarted.stale_items("task", scope=SCOPE) == ["b", "c", "d"]
    assert restarted.mark_stale("isolated", task_id="task", scope=SCOPE) == []
    assert len(EventStore(graph.engine).list("task", scope=SCOPE)) == 3


def test_t012_ac1_graph_stale_event_failure_rolls_back_entire_invalidation(graph) -> None:
    graph.add_edge("rent", "noi", scope=SCOPE)
    graph.add_edge("noi", "uw", scope=SCOPE)
    with graph.engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TRIGGER fail_uw BEFORE INSERT ON events "
                "WHEN json_extract(NEW.payload, '$.payload.item_id') = 'uw' "
                "BEGIN SELECT RAISE(ABORT, 'injected write failure'); END"
            )
        )
    with pytest.raises(DBAPIError):
        graph.mark_stale("rent", task_id="task", scope=SCOPE)
    assert EventStore(graph.engine).list("task", scope=SCOPE) == []
    assert graph.stale_items("task", scope=SCOPE) == []
