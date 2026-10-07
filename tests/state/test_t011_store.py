from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select

from cre_brain.domain import ClaimType, Deliverable, DeliverableKind, Fact, Provenance
from cre_brain.domain.base import TenantScope
from cre_brain.state.schema import metadata
from cre_brain.state.store import SqlVersionedStore, StateConflict

SCOPE = TenantScope(user_id="user-a", firm_id="firm-a")


def fact(version: int = 1) -> Fact:
    return Fact(
        fact_id="noi",
        deal_id="deal-a",
        key="noi",
        value=Decimal("1000") * version,
        claim_type=ClaimType.VERIFIED_FACT,
        provenance=[],
        known_at=datetime(2026, 10, 4, tzinfo=UTC),
        version=version,
    )


@pytest.fixture
def facts() -> SqlVersionedStore[Fact]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)
    return SqlVersionedStore(engine, Fact)


def test_t011_ac2_current_returns_latest_without_changing_history(facts) -> None:
    v1, v2 = fact(), fact(2)
    assert facts.append(v1, scope=SCOPE) == v1
    assert facts.append(v2, scope=SCOPE) == v2
    assert facts.current("noi", scope=SCOPE) == v2
    assert facts.get("noi", scope=SCOPE, version=1) == v1
    with pytest.raises(StateConflict):
        facts.append(v2, scope=SCOPE)
    assert facts.current("noi", scope=SCOPE) == v2


@pytest.mark.parametrize("version", [2, 10])
def test_t011_ac2_version_gaps_are_rejected(facts, version) -> None:
    with pytest.raises(StateConflict):
        facts.append(fact(version), scope=SCOPE)
    assert facts.current("noi", scope=SCOPE) is None


@pytest.mark.parametrize(
    "other",
    [
        TenantScope(user_id="user-b", firm_id="firm-a"),
        TenantScope(user_id="user-a", firm_id="firm-b"),
    ],
)
def test_t011_ac2_every_read_and_write_is_tenant_scoped(facts, other) -> None:
    facts.append(fact(), scope=SCOPE)
    assert facts.get("noi", scope=other) is None
    assert facts.get("noi", scope=other, version=1) is None
    facts.append(fact().model_copy(update={"value": "other tenant"}), scope=other)
    assert facts.current("noi", scope=SCOPE).value == Decimal("1000")
    assert facts.current("noi", scope=other).value == "other tenant"


@pytest.mark.parametrize("value", [date(2026, 1, 2), "00123", Decimal("1.20"), True])
def test_t011_ac2_storage_preserves_fact_value_types(facts, value) -> None:
    original = fact().model_copy(update={"value": value})
    facts.append(original, scope=SCOPE)
    restored = facts.current("noi", scope=SCOPE)
    assert restored == original
    assert type(restored.value) is type(value)
    original.provenance.append(Provenance(doc_id="changed-after-write"))
    assert facts.current("noi", scope=SCOPE) == restored


def test_t011_ac2_deliverables_are_append_only_versions() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)
    store = SqlVersionedStore(engine, Deliverable)
    first = Deliverable(
        d_id="uw",
        deal_ids=["deal-a"],
        kind=DeliverableKind.UW_MODEL,
        version=1,
        status="draft",
        path="model-v1.xlsx",
        gate_results=[],
        depends_on=["noi"],
    )
    second = first.model_copy(update={"version": 2, "status": "stale", "parent_version": 1})
    store.append(first, scope=SCOPE)
    store.append(second, scope=SCOPE)
    assert store.get("uw", scope=SCOPE, version=1) == first
    assert store.current("uw", scope=SCOPE) == second


@pytest.mark.parametrize("kind", list(DeliverableKind))
def test_t011_ac2_legacy_deliverable_reads_preserve_history_and_canonical_writes(kind) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)
    store = SqlVersionedStore(engine, Deliverable)
    first = Deliverable(
        d_id="uw",
        deal_ids=["deal-a"],
        kind=kind,
        version=1,
        status="draft",
        path="model-v1.xlsx",
        gate_results=[],
        depends_on=["noi"],
    )
    second = first.model_copy(update={"version": 2, "parent_version": 1})
    historical = []
    with engine.begin() as connection:
        for record in (first, second):
            payload = {**record.model_dump(mode="json"), "kind": kind.value.lower()}
            historical.append(payload)
            connection.execute(
                store.table.insert().values(
                    user_id=SCOPE.user_id,
                    firm_id=SCOPE.firm_id,
                    record_id=record.d_id,
                    version=record.version,
                    payload=payload,
                )
            )
    assert store.get("uw", scope=SCOPE, version=1) == first
    restored = store.current("uw", scope=SCOPE)
    assert restored == second
    for other in (
        TenantScope(user_id="user-b", firm_id=SCOPE.firm_id),
        TenantScope(user_id=SCOPE.user_id, firm_id="firm-b"),
    ):
        assert store.get("uw", scope=other, version=1) is None
        assert store.current("uw", scope=other) is None
    third = restored.model_copy(update={"version": 3, "parent_version": 2})
    assert store.append(third, scope=SCOPE) == third
    assert store.current("uw", scope=SCOPE) == third
    with engine.connect() as connection:
        payloads = list(
            connection.execute(
                select(store.table.c.payload).order_by(store.table.c.version)
            ).scalars()
        )
    assert payloads == [*historical, third.model_dump(mode="json")]
    assert payloads[-1]["kind"] == kind.value


@pytest.mark.parametrize("kind", ["uw_Model", " uw_model", "unknown", "", None, 3])
def test_t011_ac2_stored_unknown_deliverable_kind_remains_invalid(kind) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)
    store = SqlVersionedStore(engine, Deliverable)
    with engine.begin() as connection:
        connection.execute(
            store.table.insert().values(
                user_id=SCOPE.user_id,
                firm_id=SCOPE.firm_id,
                record_id="uw",
                version=1,
                payload={
                    "d_id": "uw",
                    "deal_ids": ["deal-a"],
                    "kind": kind,
                    "version": 1,
                    "status": "draft",
                    "path": "model.xlsx",
                    "gate_results": [],
                    "depends_on": [],
                },
            )
        )
    with pytest.raises(ValidationError):
        store.current("uw", scope=SCOPE)
