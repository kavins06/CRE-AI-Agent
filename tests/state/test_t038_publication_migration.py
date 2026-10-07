"""Publication columns preserve historical schemas and inherited immutable guards."""

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from cre_brain.state.migrate import migration_config, upgrade_database
from cre_brain.state.schema import metadata

TABLES = {
    "facts",
    "assumptions",
    "calcs",
    "questions",
    "deliverables",
    "edges",
    "events",
    "jobs",
    "corrections",
}


def test_t038_ac2_screen_publication_migration_preserves_tables_history_and_guards():
    engine = create_engine("sqlite:///:memory:")
    config = migration_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0001_state_store")
        connection.execute(
            text(
                "INSERT INTO deliverables (user_id, firm_id, record_id, version, payload) "
                "VALUES ('u', 'f', 'old', 1, '{}')"
            )
        )
    assert [c["name"] for c in inspect(engine).get_columns("deliverables")] == [
        "user_id",
        "firm_id",
        "record_id",
        "version",
        "payload",
    ]
    upgrade_database(engine)
    assert set(metadata.tables) == TABLES
    assert set(inspect(engine).get_table_names()) == TABLES | {"alembic_version"}
    columns = {c["name"]: c for c in inspect(engine).get_columns("deliverables")}
    assert columns["publication"]["nullable"] is True
    with engine.begin() as connection:
        assert connection.execute(text("SELECT publication FROM deliverables")).scalar() is None
        connection.execute(
            text(
                "INSERT INTO deliverables "
                "(user_id, firm_id, record_id, version, payload, publication) "
                "VALUES ('u', 'f', 'final', 2, '{}', :body)"
            ),
            {"body": b"protected"},
        )
    for statement in [
        "UPDATE deliverables SET publication = NULL",
        "DELETE FROM deliverables",
        "INSERT OR REPLACE INTO deliverables "
        "(user_id, firm_id, record_id, version, payload, publication) "
        "VALUES ('u', 'f', 'final', 2, '{}', NULL)",
    ]:
        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(text(statement))
    with engine.begin() as connection:
        assert (
            connection.execute(
                text("SELECT publication FROM deliverables WHERE record_id = 'final'")
            ).scalar()
            == b"protected"
        )
        config.attributes["connection"] = connection
        command.downgrade(config, "0001_state_store")
    assert "publication" not in {c["name"] for c in inspect(engine).get_columns("deliverables")}
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(text("DELETE FROM deliverables"))


def test_t038_ac2_screen_publication_column_has_database_size_bound():
    engine = create_engine("sqlite:///:memory:")
    upgrade_database(engine)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO deliverables "
                "(user_id, firm_id, record_id, version, payload, publication) "
                "VALUES ('u', 'f', 'oversized', 2, '{}', zeroblob(33685509))"
            )
        )
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM deliverables")).scalar() == 0
