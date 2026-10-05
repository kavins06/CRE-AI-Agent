"""Second-review regressions: protected lossless publications and delivery revocation."""

import base64
import json
from pathlib import Path

import pytest
from sqlalchemy import select
from tests.deliverables import test_screen as screen_fixtures

from cre_brain.domain import Deliverable, DeliverableKind
from cre_brain.gates.models import GatePlan, MemoPair
from cre_brain.runner.normalizer import Sanitizer
from cre_brain.runner.tools import files
from cre_brain.runner.tools.contracts import Artifact, ArtifactCompanion, SendExternal
from cre_brain.runner.tools.json_io import MAX_BYTES, canonical
from cre_brain.state.schema import metadata

screen_env = screen_fixtures.screen_env


def questions(env, body="Broker questions\npassword: swordfish\n", *, companions=1):
    _, registry, _, authority, _, _ = env
    root = registry.workspace / "deals" / registry.context.deal_id / "deliverables"
    root.mkdir(parents=True)
    path = root / "questions.md"
    path.write_text(body)
    pair = []
    for index in range(companions):
        companion = root / f"questions-{index}.json"
        companion.write_text(json.dumps({"markdown": body}))
        pair.append(ArtifactCompanion(path=companion, sha256=files.digest(companion.read_bytes())))
    draft = Deliverable(
        d_id="questions",
        deal_ids=[registry.context.deal_id],
        kind=DeliverableKind.BROKER_QUESTIONS,
        version=1,
        status="draft",
        path=str(path),
        gate_results=[],
        depends_on=[],
    )
    anchor = Artifact(
        deliverable=draft, sha256=files.digest(path.read_bytes()), companions=tuple(pair)
    )
    registry.inputs.register(registry.context, anchor)
    authority.put_plan(
        registry.context.scope,
        draft,
        GatePlan(
            memo_pair=MemoPair(
                markdown=path,
                markdown_sha256=anchor.sha256,
                json_path=pair[0].path,
                json_sha256=pair[0].sha256,
            )
        ),
    )
    with registry.transaction() as state:
        state.append(draft)
    return registry, anchor


def release(registry, anchor):
    result = registry.call("finalize_deliverable", {"deliverable_id": anchor.deliverable.d_id})
    assert result["status"] == "ok", result
    with registry.transaction() as state:
        return next(e for e in state.history() if e.kind == "deliverable")


def test_t038_ac2_screen_secret_body_absent_from_all_ordinary_events(screen_env, tmp_path_factory):
    # Avoid sanitizer-sensitive words in the pytest directory used as a mapping key.
    screen_env[1].workspace = tmp_path_factory.mktemp("publication-workspace")
    registry, anchor = questions(screen_env)
    event = release(registry, anchor)
    with registry.transaction() as state:
        payload = [e.model_dump(mode="json") for e in state.history()]
    ordinary = json.dumps(payload)
    assert "swordfish" not in ordinary
    assert base64.b64encode(Path(anchor.deliverable.path).read_bytes()).decode() not in ordinary
    assert all(
        set(item) == {"publication_id", "path", "sha256"} for item in event.payload["publication"]
    )
    assert Sanitizer(secrets=("swordfish",)).scrub(payload) == payload


def test_t038_ac2_screen_protected_retrieval_survives_mirror_change_and_restart(screen_env):
    registry, anchor = questions(screen_env)
    event = release(registry, anchor)
    expected = Path(anchor.deliverable.path).read_bytes()
    Path(anchor.deliverable.path).write_bytes(b"changed mirror")
    recovered = registry.clone()
    reference = event.payload["publication"][0]
    assert (
        recovered.published_artifact(anchor.deliverable.d_id, reference["publication_id"])
        == expected
    )
    for field, value in (("task_id", "foreign"), ("deal_id", "foreign"), ("release_id", "foreign")):
        other = recovered.clone(context=recovered.context.model_copy(update={field: value}))
        with pytest.raises(ValueError):
            other.published_artifact(anchor.deliverable.d_id, reference["publication_id"])
    other_scope = recovered.context.scope.model_copy(update={"user_id": "foreign"})
    other = recovered.clone(context=recovered.context.model_copy(update={"scope": other_scope}))
    with pytest.raises(ValueError):
        other.published_artifact(anchor.deliverable.d_id, reference["publication_id"])
    assert (
        "published_artifact"
        not in __import__("cre_brain.runner.tools.registry", fromlist=["CORE_TOOLS"]).CORE_TOOLS
    )


def test_t038_ac2_screen_large_bodies_have_bounded_prepared_metadata(screen_env, monkeypatch):
    registry, anchor = questions(screen_env, "Broker questions\n" + "x" * 100000)
    original = registry.deadline
    calls = 0

    def deadline(state):
        nonlocal calls
        calls += 1
        original(state)

    monkeypatch.setattr(registry, "deadline", deadline)
    event = release(registry, anchor)
    assert len(canonical(event.model_dump(mode="json")).encode()) < MAX_BYTES
    assert len(canonical(event.payload).encode()) < 4096
    assert calls >= 2
    assert (
        registry.published_artifact(
            anchor.deliverable.d_id, event.payload["publication"][0]["publication_id"]
        )
        == Path(anchor.deliverable.path).read_bytes()
    )


def test_t038_ac2_screen_publication_aggregate_bound_rolls_back(screen_env, monkeypatch):
    from cre_brain.state import publications

    registry, anchor = questions(screen_env, "Broker questions\n" + "x" * 1000, companions=4)
    monkeypatch.setattr(publications, "MAX_PUBLICATION_BYTES", 4000)
    result = registry.call("finalize_deliverable", {"deliverable_id": anchor.deliverable.d_id})
    assert result["status"] == "refused", result
    with registry.transaction() as state:
        assert state.current(Deliverable, anchor.deliverable.d_id).status == "draft"
        assert not any(e.kind == "deliverable" for e in state.history())
        assert not state.connection.execute(
            select(metadata.tables["deliverables"].c.publication).where(
                metadata.tables["deliverables"].c.publication.is_not(None)
            )
        ).all()


@pytest.mark.parametrize("revocation", ["off", "ask", "scope", "recipient", "connector"])
def test_t038_ac2_screen_reserved_send_rechecks_current_authorization(screen_env, revocation):
    registry, anchor = questions(screen_env, "Broker questions")
    release(registry, anchor)

    class Connector:
        scope = registry.context.scope
        allowed_recipients = frozenset({"host-recipient"})

        def __init__(self):
            self.calls = []

        def send(self, **kwargs):
            self.calls.append(kwargs)
            return "receipt"

    connector = Connector()
    registry.connectors["email_brokers"] = connector
    registry.set_host_toggles(email_brokers="on")
    draft = registry.call(
        "draft_external",
        {
            "kind": "email_brokers",
            "to": "host-recipient",
            "body": "Broker questions",
            "deliverable_id": anchor.deliverable.d_id,
        },
    )
    with registry.transaction() as state:
        intent = registry.prepare_send(state, SendExternal(draft_id=draft["data"]["draft_id"]))
    assert intent["status"] == "pending_delivery"
    if revocation in {"off", "ask"}:
        # A different task writes the durable tenant policy revision.
        registry.clone(
            context=registry.context.model_copy(update={"task_id": "host-policy-task"})
        ).set_host_toggles(email_brokers=revocation)
    elif revocation == "scope":
        connector.scope = connector.scope.model_copy(update={"firm_id": "foreign"})
    elif revocation == "recipient":
        connector.allowed_recipients = frozenset()
    else:
        registry.connectors.clear()
    result = registry.deliver(intent)
    assert result["status"] == "refused", result
    assert connector.calls == []
    # Reservation remains ambiguous, and restoring policy cannot silently resend.
    registry.connectors["email_brokers"] = Connector()
    registry.set_host_toggles(email_brokers="on")
    with registry.transaction() as state:
        from cre_brain.runner.policy import Refusal

        with pytest.raises(Refusal, match="reserved"):
            registry.prepare_send(state, SendExternal(draft_id=draft["data"]["draft_id"]))


def test_t038_ac2_screen_column_atomic_and_ordinary_domain_read_excludes_body(screen_env):
    from cre_brain.state.store import SqlVersionedStore

    registry, anchor = questions(screen_env)
    event = release(registry, anchor)
    table = metadata.tables["deliverables"]
    with registry.transaction() as state:
        row = state.connection.execute(select(table).where(table.c.version == 2)).mappings().one()
        assert row["publication"] is not None
        assert b"swordfish" in row["publication"]
        assert "swordfish" not in json.dumps(row["payload"])
        assert "publication" not in state.current(Deliverable, anchor.deliverable.d_id).model_dump()
    stored = SqlVersionedStore(registry.engine, Deliverable).get(
        anchor.deliverable.d_id, scope=registry.context.scope, version=2
    )
    assert "swordfish" not in stored.model_dump_json()
    for reference in event.payload["publication"]:
        assert (
            registry.published_artifact(
                anchor.deliverable.d_id, reference["publication_id"], version=2
            )
            == Path(reference["path"]).read_bytes()
        )
    with pytest.raises(ValueError):
        registry.published_artifact(anchor.deliverable.d_id, "publication-" + "0" * 64, version=2)
    with pytest.raises(ValueError):
        registry.published_artifact(
            anchor.deliverable.d_id, event.payload["publication"][0]["publication_id"], version=1
        )


def test_t038_ac2_screen_publication_prepared_before_final_deadline(screen_env, monkeypatch):
    from cre_brain.state import publications

    registry, anchor = questions(screen_env)
    original_prepare = publications.encode
    original_deadline = registry.deadline
    steps = []

    def encode(*args, **kwargs):
        result = original_prepare(*args, **kwargs)
        steps.append("prepared")
        return result

    def deadline(state):
        steps.append("deadline")
        original_deadline(state)
        if "prepared" in steps:
            raise ValueError("Expired after body preparation")

    monkeypatch.setattr(publications, "encode", encode)
    monkeypatch.setattr(registry, "deadline", deadline)
    result = registry.call("finalize_deliverable", {"deliverable_id": anchor.deliverable.d_id})
    assert result["status"] == "refused"
    assert steps[-2:] == ["prepared", "deadline"]
    with registry.transaction() as state:
        assert state.current(Deliverable, anchor.deliverable.d_id).status == "draft"
        assert not any(e.kind == "deliverable" for e in state.history())


def test_t038_ac2_screen_historical_retrieval_needs_no_workspace_or_new_anchor(
    screen_env, monkeypatch
):
    registry, anchor = questions(screen_env)
    event = release(registry, anchor)
    expected = {
        reference["publication_id"]: Path(reference["path"]).read_bytes()
        for reference in event.payload["publication"]
    }
    with registry.transaction() as state:
        newer = anchor.deliverable.model_copy(update={"version": 3, "parent_version": 2})
        state.append(newer)
    for reference in event.payload["publication"]:
        Path(reference["path"]).unlink()
    from cre_brain.deliverables.screen import ScreenInputs

    registry.inputs = ScreenInputs(screen_env[2])

    def no_mirror(*args, **kwargs):
        raise AssertionError("Protected retrieval must not read workspace mirrors")

    monkeypatch.setattr(files, "read", no_mirror)
    recovered = registry.clone()
    for publication_id, body in expected.items():
        assert (
            recovered.published_artifact(anchor.deliverable.d_id, publication_id, version=2) == body
        )
    for scope in (
        registry.context.scope.model_copy(update={"user_id": "foreign"}),
        registry.context.scope.model_copy(update={"firm_id": "foreign"}),
    ):
        foreign = recovered.clone(context=registry.context.model_copy(update={"scope": scope}))
        with pytest.raises(ValueError):
            foreign.published_artifact(anchor.deliverable.d_id, publication_id, version=2)
    extraction = recovered.clone(context=registry.context.model_copy(update={"role": "extraction"}))
    with pytest.raises(ValueError):
        extraction.published_artifact(anchor.deliverable.d_id, publication_id, version=2)


def test_t038_ac2_screen_last_mirror_validation_deadline_rolls_back(screen_env, monkeypatch):
    from cre_brain.runner.policy import Refusal

    registry, anchor = questions(screen_env)
    original_artifact = registry.artifact
    original_deadline = registry.deadline
    expired = False

    def artifact(*args, **kwargs):
        nonlocal expired
        result = original_artifact(*args, **kwargs)
        if kwargs.get("final_replay"):
            expired = True
        return result

    def deadline(state):
        original_deadline(state)
        if expired:
            raise Refusal("budget_exceeded", "Last mirror validation exceeded deadline")

    monkeypatch.setattr(registry, "artifact", artifact)
    monkeypatch.setattr(registry, "deadline", deadline)
    result = registry.call("finalize_deliverable", {"deliverable_id": anchor.deliverable.d_id})
    assert result["status"] == "refused", result
    assert result["category"] == "budget_exceeded"
    with registry.transaction() as state:
        assert state.current(Deliverable, anchor.deliverable.d_id).status == "draft"
        assert not any(e.kind == "deliverable" for e in state.history())


@pytest.mark.parametrize(
    "forgery",
    ["none", "source", "runner", "release", "sha256", "companions", "references", "gates"],
)
def test_t038_ac2_screen_host_retrieval_authenticates_event_and_protected_column(
    screen_env, forgery
):
    from cre_brain.gates.snapshot import ArtifactSnapshot, CompanionSnapshot
    from cre_brain.state import publications
    from cre_brain.state.events import _append_locked

    registry, anchor = questions(screen_env, "Broker questions")
    event = release(registry, anchor)
    # A different row with valid scoped protected bytes isolates event/gate
    # authentication from the separate missing-publication rejection.
    identity = "copied-release"
    draft = anchor.deliverable.model_copy(update={"d_id": identity})
    copied_anchor = anchor.model_copy(update={"deliverable": draft})
    snapshot = ArtifactSnapshot(
        Path(draft.path).read_bytes(),
        anchor.sha256,
        tuple(CompanionSnapshot(c.path, c.path.read_bytes(), c.sha256) for c in anchor.companions),
    )
    prepared = publications.prepare(registry.context, copied_anchor, snapshot)
    blob = publications.encode(registry.context, copied_anchor, prepared)
    payload = {**event.payload, "d_id": identity, "publication": publications.references(prepared)}
    update = {}
    if forgery in {"source", "runner", "release"}:
        update[{"source": "source", "runner": "runner", "release": "release_id"}[forgery]] = {
            "source": "agent",
            "runner": "codex",
            "release": "foreign-release",
        }[forgery]
    if forgery == "sha256":
        payload["sha256"] = "0" * 64
    if forgery == "companions":
        payload["companions"] = {}
    if forgery == "references":
        payload["publication"] = event.payload["publication"]
    with registry.transaction() as state:
        current = state.current(Deliverable, anchor.deliverable.d_id)
        state.append(draft)
        state.append(
            current.model_copy(
                update={
                    "d_id": identity,
                    "gate_results": [] if forgery == "gates" else current.gate_results,
                }
            ),
            publication=blob,
        )
        _append_locked(
            state.connection,
            event.model_copy(
                update={
                    **update,
                    "event_id": "copied-event",
                    "seq": None,
                    "payload": payload,
                }
            ),
            registry.context.scope,
        )
    if forgery == "none":
        assert (
            registry.published_artifact(identity, prepared[0].publication_id, version=2)
            == snapshot.data
        )
    else:
        with pytest.raises(ValueError):
            registry.published_artifact(identity, prepared[0].publication_id, version=2)


def test_t038_ac2_screen_protected_column_digest_detects_corruption(screen_env):
    from cre_brain.gates.snapshot import ArtifactSnapshot, CompanionSnapshot
    from cre_brain.state import publications

    registry, anchor = questions(screen_env, "Broker questions")
    release(registry, anchor)
    draft = anchor.deliverable.model_copy(update={"d_id": "corrupted"})
    copied_anchor = anchor.model_copy(update={"deliverable": draft})
    snapshot = ArtifactSnapshot(
        Path(draft.path).read_bytes(),
        anchor.sha256,
        tuple(CompanionSnapshot(c.path, c.path.read_bytes(), c.sha256) for c in anchor.companions),
    )
    prepared = publications.prepare(registry.context, copied_anchor, snapshot)
    blob = publications.encode(registry.context, copied_anchor, prepared)
    with registry.transaction() as state:
        current = state.current(Deliverable, anchor.deliverable.d_id)
        state.append(draft)
        state.append(current.model_copy(update={"d_id": "corrupted"}), publication=blob[:-1] + b"!")
    with pytest.raises(ValueError, match="digest"):
        registry.published_artifact("corrupted", prepared[0].publication_id, version=2)
