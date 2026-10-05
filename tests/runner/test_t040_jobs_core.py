"""Offline helper contracts; these do not claim T040 run acceptance."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect
from tests.state import test_t011_postgres

from cre_brain.control.jobs import HostReceipt, JobIdentity, JobStore
from cre_brain.domain.base import TenantScope
from cre_brain.state.schema import metadata
from cre_brain.state.store import StateConflict

postgres_engine = test_t011_postgres.postgres_engine

NOW = datetime(2026, 10, 5, tzinfo=UTC)
SCOPE = TenantScope(user_id="fixture-user", firm_id="fixture-firm")


def identity(**updates):
    return JobIdentity.model_validate(
        dict(
            scope=SCOPE,
            task_id="task",
            deal_id="deal",
            release_id="release",
            box_id="box",
            runtime="codex",
            request_id="request",
            request_sha256="a" * 64,
            segment_no=0,
        )
        | updates
    )


def receipt(job, outcome="running", **updates):
    return HostReceipt.model_validate(
        dict(
            identity=job.identity,
            receipt_id="receipt",
            claim_revision=job.claim_revision,
            owner_id=job.owner_id,
            observed_at=NOW,
            outcome=outcome,
            session_id="session" if outcome != "not_started" else None,
            lease_until=NOW + timedelta(minutes=5) if outcome == "running" else None,
        )
        | updates
    )


@pytest.fixture
def store(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'jobs.db'}")
    metadata.create_all(engine)
    yield JobStore(engine)
    engine.dispose()


def test_jobs_durable_claim_and_simultaneous_race(store):
    def claim(n):
        return store.claim(identity(), owner_id=f"worker-{n}", now=NOW)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(claim, range(24)))
    assert sum(r.acquired for r in results) == 1
    assert {r.job.owner_id for r in results} == {results[0].job.owner_id}
    assert {r.job.status for r in results} == {"creation_unknown"}
    reopened = JobStore(create_engine(str(store.engine.url)))
    assert reopened.get(identity()) == results[0].job
    assert set(inspect(store.engine).get_table_names()) == set(metadata.tables)
    reopened.engine.dispose()


@pytest.mark.parametrize(
    "field,value",
    [
        ("deal_id", "other"),
        ("release_id", "other"),
        ("box_id", "other"),
        ("runtime", "other"),
        ("request_id", "other"),
        ("request_sha256", "b" * 64),
    ],
)
def test_jobs_immutable_identity_conflicts(store, field, value):
    original = store.claim(identity(), owner_id="worker", now=NOW).job
    with pytest.raises(StateConflict):
        store.claim(identity(**{field: value}), owner_id="worker", now=NOW)
    assert store.get(identity()) == original


def test_jobs_task_tenant_segment_separation_and_release_conflict(store):
    identities = [
        identity(),
        identity(task_id="other"),
        identity(segment_no=1),
        identity(scope=TenantScope(user_id="other", firm_id=SCOPE.firm_id)),
        identity(scope=TenantScope(user_id=SCOPE.user_id, firm_id="other")),
    ]
    for item in identities:
        assert store.claim(item, owner_id="worker", now=NOW).acquired
    for item in identities:
        assert store.get(item).identity == item
    with pytest.raises(StateConflict):
        store.get(identity(release_id="different"))


@pytest.mark.parametrize("phase", ["creation_unknown", "start_unknown", "worker_unknown"])
def test_jobs_unknown_outcomes_never_relaunch_without_trusted_recovery(store, phase):
    job = store.claim(identity(), owner_id="worker", now=NOW).job
    if phase != "creation_unknown":
        job = store.mark_unknown(identity(), owner_id="worker", revision=job.revision, phase=phase)
    retry = store.claim(identity(), owner_id="other-worker", now=NOW + timedelta(days=1))
    assert not retry.acquired
    assert retry.signal.actions == ("recover",)
    assert retry.job == job
    recovered = store.reconcile(receipt(job, "not_started"), revision=job.revision)
    assert recovered.status == "ready"
    assert store.claim(identity(), owner_id="other-worker", now=NOW).acquired


def test_jobs_verified_running_receipt_expiry_and_recovery(store):
    job = store.claim(identity(), owner_id="worker", now=NOW).job
    running = store.reconcile(receipt(job), revision=job.revision)
    assert running.status == "running"
    assert not store.claim(identity(), owner_id="other", now=NOW).acquired
    expired = store.claim(identity(), owner_id="other", now=NOW + timedelta(minutes=6))
    assert expired.job.status == "worker_unknown"
    assert expired.signal.actions == ("recover",)
    with pytest.raises(StateConflict):
        store.reconcile(receipt(job), revision=job.revision)
    with pytest.raises(StateConflict):
        store.reconcile(receipt(expired.job, "not_started"), revision=expired.job.revision)
    recovered = store.reconcile(
        receipt(
            expired.job,
            receipt_id="recovery",
            observed_at=NOW + timedelta(minutes=6),
            lease_until=NOW + timedelta(minutes=10),
            owner_id="verified-worker",
        ),
        revision=expired.job.revision,
    )
    assert recovered.owner_id == "verified-worker"
    assert recovered.session_id == "session"


@pytest.mark.parametrize("final", ["completed", "stopped", "failed"])
def test_jobs_terminal_status_is_monotonic_and_receipts_idempotent(store, final):
    job = store.claim(identity(), owner_id="worker", now=NOW).job
    evidence = receipt(job, final)
    finished = store.reconcile(evidence, revision=job.revision)
    assert store.reconcile(evidence, revision=job.revision) == finished
    assert not store.claim(identity(), owner_id="other", now=NOW).acquired
    with pytest.raises(StateConflict):
        store.mark_unknown(
            identity(), owner_id="worker", revision=finished.revision, phase="worker_unknown"
        )
    with pytest.raises(StateConflict):
        store.reconcile(receipt(finished, receipt_id="new"), revision=finished.revision)
    assert store.get(identity()) == finished


def test_jobs_receipt_identity_cas_session_and_payload_conflicts(store):
    job = store.claim(identity(), owner_id="worker", now=NOW).job
    with pytest.raises(StateConflict):
        store.mark_unknown(
            identity(), owner_id="wrong", revision=job.revision, phase="start_unknown"
        )
    with pytest.raises(StateConflict):
        store.reconcile(receipt(job, identity=identity(release_id="other")), revision=job.revision)
    running = store.reconcile(receipt(job), revision=job.revision)
    for changed in [dict(session_id="other"), dict(owner_id="other")]:
        with pytest.raises(StateConflict):
            store.reconcile(receipt(running, **changed), revision=running.revision)
    with pytest.raises(StateConflict):
        store.reconcile(
            receipt(running, receipt_id="new", session_id="other"), revision=running.revision
        )
    assert store.get(identity()) == running


@pytest.mark.parametrize("bad", [True, -1, 1.5, "1", 2**31])
def test_jobs_strict_segment_bounds(bad):
    with pytest.raises(ValidationError):
        identity(segment_no=bad)


def test_jobs_receipts_require_aware_time_and_complete_session_binding(store):
    job = store.claim(identity(), owner_id="worker", now=NOW).job
    for updates in [
        dict(observed_at=NOW.replace(tzinfo=None)),
        dict(session_id=None),
        dict(lease_until=NOW),
        dict(lease_until=None),
    ]:
        with pytest.raises(ValidationError):
            receipt(job, **updates)


def test_jobs_old_no_launch_receipt_cannot_clear_a_new_unknown_claim(store):
    first = store.claim(identity(), owner_id="worker", now=NOW).job
    evidence = receipt(first, "not_started")
    store.reconcile(evidence, revision=first.revision)
    second = store.claim(identity(), owner_id="other", now=NOW).job
    with pytest.raises(StateConflict):
        store.reconcile(evidence, revision=second.revision)
    assert not store.claim(identity(), owner_id="third", now=NOW).acquired


def test_jobs_unknown_phase_input_cannot_set_terminal_or_healthy_status(store):
    job = store.claim(identity(), owner_id="worker", now=NOW).job
    with pytest.raises(ValidationError):
        store.mark_unknown(identity(), owner_id="worker", revision=job.revision, phase="completed")
    assert store.get(identity()) == job


@pytest.mark.integration
@pytest.mark.requires_key("CRE_TEST_DATABASE_URL")
def test_jobs_postgresql_isolated_schema_claim_race_and_recovery(postgres_engine):
    """Coordinator-run only: reuse the canonical fresh-schema fixture."""
    metadata.create_all(postgres_engine)
    store = JobStore(postgres_engine)
    with ThreadPoolExecutor(max_workers=8) as pool:
        claims = list(
            pool.map(
                lambda n: store.claim(identity(), owner_id=f"worker-{n}", now=NOW),
                range(24),
            )
        )
    assert sum(c.acquired for c in claims) == 1
    job = next(c.job for c in claims if c.acquired)
    running = store.reconcile(receipt(job), revision=job.revision)
    expired = store.claim(identity(), owner_id="other", now=NOW + timedelta(days=1))
    assert not expired.acquired and expired.job.status == "worker_unknown"
    assert expired.signal.actions == ("recover",)
    completed = store.reconcile(
        receipt(running, "completed", receipt_id="completion", observed_at=NOW + timedelta(days=1)),
        revision=expired.job.revision,
    )
    assert store.get(identity()) == completed
    assert not store.claim(identity(), owner_id="other", now=NOW + timedelta(days=1)).acquired


@pytest.mark.parametrize("bad", [True, -1, 0, 1.5, "1", 2147483648])
def test_jobs_revision_inputs_are_strict_even_for_receipt_replay(store, bad):
    job = store.claim(identity(), owner_id="worker", now=NOW).job
    evidence = receipt(job, "completed")
    store.reconcile(evidence, revision=job.revision)
    with pytest.raises(ValidationError):
        store.reconcile(evidence, revision=bad)


def test_jobs_delayed_distinct_absence_receipt_cannot_clear_same_owner_new_claim(store):
    w1 = store.claim(identity(), owner_id="same-owner", now=NOW).job
    r1 = receipt(w1, "not_started", receipt_id="R1", observed_at=NOW + timedelta(seconds=1))
    r2 = receipt(w1, "not_started", receipt_id="R2", observed_at=NOW + timedelta(seconds=2))
    store.reconcile(r1, revision=w1.revision)
    w2 = store.claim(identity(), owner_id="same-owner", now=NOW + timedelta(seconds=3)).job
    with pytest.raises(StateConflict):
        store.reconcile(r2, revision=w2.revision)
    assert store.get(identity()) == w2
    assert w2.status == "creation_unknown"
    assert not store.claim(identity(), owner_id="same-owner", now=NOW + timedelta(days=1)).acquired


def test_jobs_claim_generation_survives_created_running_unknown_and_final_json(store):
    claimed = store.claim(identity(), owner_id="worker", now=NOW).job
    generation = claimed.claim_revision
    created = store.reconcile(
        receipt(
            claimed,
            "created",
            receipt_id="created",
            observed_at=NOW + timedelta(seconds=1),
            session_id=None,
        ),
        revision=claimed.revision,
    )
    running = store.reconcile(
        receipt(created, receipt_id="running", observed_at=NOW + timedelta(seconds=2)),
        revision=created.revision,
    )
    expired = store.claim(identity(), owner_id="worker", now=NOW + timedelta(minutes=6)).job
    finished = store.reconcile(
        receipt(
            expired, "completed", receipt_id="completed", observed_at=NOW + timedelta(minutes=6)
        ),
        revision=expired.revision,
    )
    for job in [claimed, created, running, expired, finished]:
        assert job.claim_revision == generation
        assert job.claim_revision <= job.revision
        restored = type(job).model_validate_json(job.model_dump_json())
        assert restored == job
        if restored.receipt is not None:
            assert restored.receipt.claim_revision == generation
    assert finished.revision > expired.revision > running.revision > created.revision > generation


@pytest.mark.parametrize("bad", [True, False, -1, 0, 1.5, "1", 2147483648, None])
def test_jobs_claim_generation_has_strict_python_and_json_bounds(store, bad):
    import json

    job = store.claim(identity(), owner_id="worker", now=NOW).job
    evidence = receipt(job, "not_started")
    for model in [evidence, job]:
        payload = model.model_dump(mode="json") | {"claim_revision": bad}
        with pytest.raises(ValidationError):
            type(model).model_validate(payload)
        with pytest.raises(ValidationError):
            type(model).model_validate_json(json.dumps(payload))


def test_jobs_missing_or_conflicting_claim_generation_fails_closed(store):
    job = store.claim(identity(), owner_id="worker", now=NOW).job
    evidence = receipt(job, "not_started")
    for model in [evidence, job]:
        payload = model.model_dump(mode="json")
        del payload["claim_revision"]
        with pytest.raises(ValidationError):
            type(model).model_validate(payload)
    with pytest.raises(ValidationError):
        type(job).model_validate(job.model_dump() | {"claim_revision": job.revision + 1})
    wrong_generation = receipt(job, "not_started", claim_revision=job.claim_revision + 1)
    with pytest.raises(StateConflict):
        store.reconcile(wrong_generation, revision=job.revision)
    assert store.get(identity()) == job


def test_jobs_new_claim_generation_is_required_for_current_receipts(store):
    first = store.claim(identity(), owner_id="worker", now=NOW).job
    store.reconcile(receipt(first, "not_started"), revision=first.revision)
    second = store.claim(identity(), owner_id="worker", now=NOW + timedelta(seconds=1)).job
    assert second.claim_revision == second.revision > first.claim_revision
    assert second.receipt is None
    verified = receipt(
        second, "not_started", receipt_id="new-generation", observed_at=NOW + timedelta(seconds=2)
    )
    ready = store.reconcile(verified, revision=second.revision)
    assert ready.claim_revision == second.claim_revision
    assert ready.status == "ready"
