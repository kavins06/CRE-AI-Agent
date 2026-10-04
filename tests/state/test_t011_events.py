from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine

from cre_brain.domain import AgentEvent
from cre_brain.domain.base import TenantScope
from cre_brain.state.events import EventStore
from cre_brain.state.schema import metadata
from cre_brain.state.store import StateConflict

SCOPE = TenantScope(user_id="u", firm_id="f")


def event(number: int, *, task_id: str = "task-a", origin=True) -> AgentEvent:
    return AgentEvent(
        event_id=f"event-{number}",
        task_id=task_id,
        seq=None,
        origin=("box-a", 1, number) if origin else None,
        ts=datetime(2026, 10, 4, tzinfo=UTC),
        source="tool",
        kind="tool_result",
        cause_id=None,
        release_id="r1",
        runner="fixture",
        payload={"result": number},
    )


@pytest.fixture
def events(tmp_path) -> EventStore:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'events.sqlite'}")
    metadata.create_all(engine)
    return EventStore(engine)


def test_t011_ac3_assigns_sequence_and_deduplicates_origin(events) -> None:
    first = events.append(event(1), scope=SCOPE)
    assert first.seq == 1
    replay = event(1).model_copy(update={"event_id": "regenerated-id", "seq": 999})
    assert events.append(replay, scope=SCOPE) == first
    assert events.append(event(2).model_copy(update={"seq": 999}), scope=SCOPE).seq == 2
    assert [e.seq for e in events.list("task-a", scope=SCOPE)] == [1, 2]
    assert events.list("task-a", scope=SCOPE, after_seq=1) == [
        events.list("task-a", scope=SCOPE)[1]
    ]


def test_t011_ac3_conflicting_replay_does_not_change_history(events) -> None:
    first = events.append(event(1), scope=SCOPE)
    with pytest.raises(StateConflict):
        events.append(event(1).model_copy(update={"payload": {"changed": True}}), scope=SCOPE)
    assert events.list("task-a", scope=SCOPE) == [first]
    assert events.append(event(2), scope=SCOPE).seq == 2


def test_t011_ac3_sequences_and_origins_are_task_and_tenant_scoped(events) -> None:
    events.append(event(1), scope=SCOPE)
    other_task = event(1, task_id="task-b").model_copy(update={"event_id": "other-task-id"})
    assert events.append(other_task, scope=SCOPE).seq == 1
    for other in (
        TenantScope(user_id="other-u", firm_id="f"),
        TenantScope(user_id="u", firm_id="other-f"),
    ):
        assert events.list("task-a", scope=other) == []
        assert events.append(event(1), scope=other).seq == 1
    with pytest.raises(StateConflict):
        events.append(event(1, task_id="task-c"), scope=SCOPE)
    assert events.list("task-c", scope=SCOPE) == []


def test_t011_ac3_events_without_origin_are_not_collapsed(events) -> None:
    first, second = event(1, origin=False), event(2, origin=False)
    assert events.append(first, scope=SCOPE).seq == 1
    assert events.append(second, scope=SCOPE).seq == 2
    assert events.append(first, scope=SCOPE).seq == 1


def test_t011_ac3_concurrent_writers_receive_unique_ordered_sequences(events) -> None:
    with ThreadPoolExecutor(max_workers=8) as executor:
        written = list(executor.map(lambda n: events.append(event(n), scope=SCOPE), range(1, 33)))
    assert sorted(e.seq for e in written) == list(range(1, 33))
    with ThreadPoolExecutor(max_workers=8) as executor:
        duplicates = list(executor.map(lambda _: events.append(event(1), scope=SCOPE), range(16)))
    assert len({e.seq for e in duplicates}) == 1
    assert len(events.list("task-a", scope=SCOPE)) == 32
