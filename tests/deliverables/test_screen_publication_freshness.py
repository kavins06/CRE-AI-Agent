"""Offline synthetic current/publication regressions; no runtime-quality evidence."""

from decimal import Decimal
from pathlib import Path

import pytest
from tests.deliverables import test_screen as screen_fixtures
from tests.deliverables.test_screen_publication import questions, release

from cre_brain.domain import Deliverable
from cre_brain.gates.models import GatePlan, MemoPair
from cre_brain.runner.policy import Refusal
from cre_brain.runner.tools.contracts import FactAnchor

screen_env = screen_fixtures.screen_env


def dependent_questions(env, dependency, *, graph_edge=True):
    registry, original = questions(env)
    draft = original.deliverable.model_copy(
        update={"d_id": "dependent-questions", "depends_on": [dependency]}
    )
    anchor = original.model_copy(update={"deliverable": draft})
    registry.inputs.register(registry.context, anchor)
    env[3].put_plan(
        registry.context.scope,
        draft,
        GatePlan(
            memo_pair=MemoPair(
                markdown=Path(draft.path),
                markdown_sha256=anchor.sha256,
                json_path=anchor.companions[0].path,
                json_sha256=anchor.companions[0].sha256,
            )
        ),
    )
    with registry.transaction() as state:
        state.append(draft)
        if graph_edge:
            state.edge(dependency, draft.d_id)
    return registry, anchor


def change_source(env):
    registry, inputs = env[1:3]
    inputs.facts["occupancy"] = FactAnchor(
        fact=inputs.facts["occupancy"].fact.model_copy(
            update={"version": 2, "value": Decimal("0.95")}
        ),
        authority="quarantine",
    )
    result = registry.call("facts_put", {"anchor_id": "occupancy"}, request_id="new-source")
    assert result["status"] == "ok", result


@pytest.mark.parametrize("invalidation", ["source", "transitive", "dependency-only"])
def test_t038_ac2_screen_current_retrieval_refuses_canonical_invalidation(screen_env, invalidation):
    registry = screen_env[1]
    dependency = "occupancy"
    if invalidation != "source":
        result = registry.call(
            "finance_run",
            {
                "fn": "risk_score",
                "args": {
                    key: screen_env[5][key].model_dump(mode="json") for key in ("occupancy", "dscr")
                },
            },
        )
        assert result["status"] == "ok", result
        dependency = result["data"]["calc_id"]
    registry, anchor = dependent_questions(
        screen_env, dependency, graph_edge=invalidation != "dependency-only"
    )
    event = release(registry, anchor)
    bodies = {
        ref["publication_id"]: Path(ref["path"]).read_bytes()
        for ref in event.payload["publication"]
    }
    change_source(screen_env)
    with registry.transaction() as state:
        assert state.current(Deliverable, anchor.deliverable.d_id).status == "final"
        assert state.fresh(anchor.deliverable.d_id) is (invalidation == "dependency-only")
        if invalidation != "source":
            assert not state.fresh(dependency)
    # Explicit archival reads remain authenticated and retain the exact immutable pair.
    for ref, body in bodies.items():
        assert registry.published_artifact(anchor.deliverable.d_id, ref, version=2) == body
    replay = registry.call("finalize_deliverable", {"deliverable_id": anchor.deliverable.d_id})
    assert replay["status"] == "refused", replay
    assert replay["category"] == "stale_evidence"
    for ref in bodies:
        with pytest.raises(Refusal) as failure:
            registry.published_artifact(anchor.deliverable.d_id, ref)
        assert failure.value.category == "stale_evidence"
        assert "swordfish" not in str(failure.value)


@pytest.mark.parametrize("version", [None, 2])
@pytest.mark.parametrize("invalidated", [False, True])
@pytest.mark.parametrize("mismatch", ["task_id", "deal_id", "release_id", "user_id", "firm_id"])
def test_t038_ac2_screen_current_and_archival_retrieval_authenticate_context(
    screen_env, version, invalidated, mismatch
):
    registry, anchor = dependent_questions(screen_env, "occupancy")
    event = release(registry, anchor)
    if invalidated:
        change_source(screen_env)
    context = registry.context
    if mismatch in {"user_id", "firm_id"}:
        context = context.model_copy(
            update={"scope": context.scope.model_copy(update={mismatch: "foreign"})}
        )
    else:
        context = context.model_copy(update={mismatch: "foreign"})
    other = registry.clone(context=context)
    for reference in event.payload["publication"]:
        with pytest.raises(ValueError) as failure:
            other.published_artifact(
                anchor.deliverable.d_id, reference["publication_id"], version=version
            )
        assert "swordfish" not in str(failure.value)


def test_t038_ac2_screen_fresh_current_release_checks_same_authenticated_transaction(
    screen_env, monkeypatch
):
    from cre_brain.runner.tools.state import ToolState
    from cre_brain.state import publications

    registry, anchor = dependent_questions(screen_env, "occupancy")
    event = release(registry, anchor)
    expected = {
        ref["publication_id"]: Path(ref["path"]).read_bytes()
        for ref in event.payload["publication"]
    }
    # Retrieval authenticates committed SQL bytes independently of mutable mirrors.
    for ref in event.payload["publication"]:
        Path(ref["path"]).write_bytes(b"changed mirror")
    connections = []
    fresh_connections = []
    load = publications.load_release
    fresh = ToolState.fresh

    def load_release(connection, *args, **kwargs):
        assert connection.in_transaction()
        connections.append(connection)
        return load(connection, *args, **kwargs)

    def check_fresh(state, identity):
        assert state.connection.in_transaction()
        fresh_connections.append((state.connection, identity))
        return fresh(state, identity)

    monkeypatch.setattr(publications, "load_release", load_release)
    monkeypatch.setattr(ToolState, "fresh", check_fresh)
    for ref, body in expected.items():
        connections.clear()
        fresh_connections.clear()
        assert registry.published_artifact(anchor.deliverable.d_id, ref) == body
        assert {identity for _, identity in fresh_connections} == {
            anchor.deliverable.d_id,
            "occupancy",
        }
        assert all(connection is connections[0] for connection, _ in fresh_connections)
        assert all(connection is connections[0] for connection in connections)


def test_t038_ac2_screen_omitted_version_cannot_fall_back_to_historical_release(screen_env):
    registry, anchor = dependent_questions(screen_env, "occupancy")
    event = release(registry, anchor)
    with registry.transaction() as state:
        state.append(anchor.deliverable.model_copy(update={"version": 3, "parent_version": 2}))
    for reference in event.payload["publication"]:
        ref = reference["publication_id"]
        assert (
            registry.published_artifact(anchor.deliverable.d_id, ref, version=2)
            == Path(reference["path"]).read_bytes()
        )
        with pytest.raises(ValueError):
            registry.published_artifact(anchor.deliverable.d_id, ref)
