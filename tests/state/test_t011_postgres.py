import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from cre_brain.domain import AgentEvent, ClaimType, Fact
from cre_brain.domain.base import TenantScope
from cre_brain.state.events import EventStore
from cre_brain.state.migrate import downgrade_database, upgrade_database
from cre_brain.state.schema import metadata
from cre_brain.state.store import SqlVersionedStore

pytestmark = [pytest.mark.integration, pytest.mark.requires_key("CRE_TEST_DATABASE_URL")]
SCOPE = TenantScope(user_id="integration-user", firm_id="integration-firm")


@pytest.fixture
def postgres_engine():
    admin = create_engine(
        os.environ["CRE_TEST_DATABASE_URL"], connect_args={"client_encoding": "utf8"}
    )
    assert admin.dialect.name == "postgresql"
    schema = f"cre_t011_{uuid4().hex}"
    with admin.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(
        os.environ["CRE_TEST_DATABASE_URL"],
        connect_args={"client_encoding": "utf8", "options": f"-csearch_path={schema}"},
    )
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def test_t011_ac1_postgresql_migration_and_state_semantics(postgres_engine) -> None:
    upgrade_database(postgres_engine)
    assert set(metadata.tables) <= set(inspect(postgres_engine).get_table_names())

    facts = SqlVersionedStore(postgres_engine, Fact)
    first = Fact(
        fact_id="noi",
        deal_id="deal",
        key="noi",
        value=Decimal("1.20"),
        claim_type=ClaimType.VERIFIED_FACT,
        provenance=[],
        known_at=datetime(2026, 10, 4, tzinfo=UTC),
        version=1,
    )
    facts.append(first, scope=SCOPE)
    facts.append(first.model_copy(update={"version": 2, "value": Decimal("1.30")}), scope=SCOPE)
    assert facts.current("noi", scope=SCOPE).value == Decimal("1.30")
    with pytest.raises(DBAPIError), postgres_engine.begin() as connection:
        connection.execute(text("UPDATE facts SET payload = '{}'"))

    events = EventStore(postgres_engine)

    def insert(number: int) -> AgentEvent:
        item = AgentEvent(
            event_id=f"e-{number}",
            task_id="task",
            seq=None,
            origin=("box", 1, number),
            ts=datetime(2026, 10, 4, tzinfo=UTC),
            source="tool",
            kind="tool_result",
            cause_id=None,
            release_id="r",
            runner="integration",
            payload={"n": number},
        )
        return events.append(item, scope=SCOPE)

    with ThreadPoolExecutor(max_workers=8) as executor:
        written = list(executor.map(insert, range(32)))
    assert sorted(event.seq for event in written) == list(range(1, 33))
    assert events.append(insert(0), scope=SCOPE).seq == 1

    downgrade_database(postgres_engine)
    assert not (set(metadata.tables) & set(inspect(postgres_engine).get_table_names()))
