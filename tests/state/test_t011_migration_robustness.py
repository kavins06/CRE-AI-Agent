import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from types import ModuleType
from uuid import uuid4
from zipfile import ZipFile

import pytest
from alembic import command
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from cre_brain.domain import AgentEvent
from cre_brain.domain.base import TenantScope
from cre_brain.state.events import EventStore
from cre_brain.state.migrate import downgrade_database, migration_config
from cre_brain.state.schema import metadata

ROOT = Path(__file__).resolve().parents[2]
BASELINE_TABLES = {
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


def upgrade_initial(engine):
    config = migration_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0001_state_store")


def test_t011_ac1_initial_revision_does_not_follow_future_application_tables() -> None:
    future = Table("future_application_table", metadata, Column("id", Integer, primary_key=True))
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        upgrade_initial(engine)
        assert "future_application_table" not in inspect(engine).get_table_names()
        future.create(engine)
        downgrade_database(engine)
        assert inspect(engine).get_table_names() == ["alembic_version", "future_application_table"]
    finally:
        metadata.remove(future)
        engine.dispose()


def test_t011_ac1_initial_revision_does_not_import_application_schema(monkeypatch) -> None:
    future_module = ModuleType("cre_brain.state.schema")
    future_module.metadata = MetaData()
    monkeypatch.setitem(sys.modules, "cre_brain.state.schema", future_module)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    upgrade_initial(engine)
    assert set(inspect(engine).get_table_names()) == BASELINE_TABLES | {"alembic_version"}
    assert [column["name"] for column in inspect(engine).get_columns("facts")] == [
        "user_id",
        "firm_id",
        "record_id",
        "version",
        "payload",
    ]
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO facts VALUES ('u', 'f', 'id', 1, '{}')"))
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(text("DELETE FROM facts"))
    downgrade_database(engine)
    engine.dispose()


def test_t011_ac1_frozen_schema_and_guards_match_initial_application_contract() -> None:
    migrated = create_engine("sqlite+pysqlite:///:memory:")
    upgrade_initial(migrated)
    inspector = inspect(migrated)
    tenant = [("user_id", "VARCHAR(128)", False), ("firm_id", "VARCHAR(128)", False)]
    versioned = [
        ("record_id", "VARCHAR(128)", False),
        ("version", "INTEGER", False),
        ("payload", "JSON", False),
    ]
    schemas = {
        name: tenant + versioned
        for name in ["facts", "assumptions", "calcs", "questions", "deliverables"]
    }
    schemas["edges"] = tenant + [
        ("src_id", "VARCHAR(128)", False),
        ("dst_id", "VARCHAR(128)", False),
    ]
    schemas["events"] = tenant + [
        ("event_id", "VARCHAR(128)", False),
        ("task_id", "VARCHAR(128)", False),
        ("seq", "INTEGER", False),
        ("origin_box", "VARCHAR(128)", True),
        ("origin_segment", "INTEGER", True),
        ("origin_local_seq", "INTEGER", True),
        ("payload", "JSON", False),
    ]
    schemas["jobs"] = tenant + [
        ("task_id", "VARCHAR(128)", False),
        ("segment_no", "INTEGER", False),
        ("status", "VARCHAR(32)", False),
        ("payload", "JSON", False),
    ]
    schemas["corrections"] = tenant + [
        ("correction_id", "VARCHAR(128)", False),
        ("task_id", "VARCHAR(128)", False),
        ("payload", "JSON", False),
    ]
    keys = {
        name: ["user_id", "firm_id", "record_id", "version"]
        for name in schemas
        if name in ["facts", "assumptions", "calcs", "questions", "deliverables"]
    }
    keys.update(
        edges=["user_id", "firm_id", "src_id", "dst_id"],
        events=["user_id", "firm_id", "event_id"],
        jobs=["user_id", "firm_id", "task_id", "segment_no"],
        corrections=["user_id", "firm_id", "correction_id"],
    )
    uniques = [
        dict(
            name="events_task_origin",
            column_names=[
                "user_id",
                "firm_id",
                "task_id",
                "origin_box",
                "origin_segment",
                "origin_local_seq",
            ],
        ),
        dict(name="events_task_seq", column_names=["user_id", "firm_id", "task_id", "seq"]),
    ]
    checks = {
        name: [dict(name=f"{name}_positive_version", sqltext="version >= 1")]
        for name in ["facts", "assumptions", "calcs", "questions", "deliverables"]
    }
    checks["events"] = [
        dict(
            name="events_complete_origin",
            sqltext="(origin_box IS NULL AND origin_segment IS NULL "
            "AND origin_local_seq IS NULL) OR "
            "(origin_box IS NOT NULL AND origin_segment IS NOT NULL AND "
            "origin_local_seq IS NOT NULL AND origin_segment >= 0 AND origin_local_seq >= 0)",
        ),
        dict(name="events_positive_seq", sqltext="seq >= 1"),
    ]
    checks["jobs"] = [dict(name="jobs_nonnegative_segment", sqltext="segment_no >= 0")]
    for name, columns in schemas.items():
        assert [
            (c["name"], str(c["type"]), c["nullable"]) for c in inspector.get_columns(name)
        ] == columns
        assert inspector.get_pk_constraint(name)["constrained_columns"] == keys[name]
        assert sorted(inspector.get_unique_constraints(name), key=lambda c: c["name"]) == (
            uniques if name == "events" else []
        )
        assert inspector.get_check_constraints(name) == checks.get(name, [])
    trigger_query = text("SELECT name, sql FROM sqlite_master WHERE type='trigger' ORDER BY name")

    def normalize(row):
        name, ddl = row
        if name.endswith("_no_replace"):
            prefix, expression = ddl.split(" WHERE ", 1)
            conditions, suffix = expression.split(" BEGIN ", 1)
            ddl = prefix + " WHERE " + " OR ".join(sorted(conditions[:-1].split(" OR ")))
            ddl += ") BEGIN " + suffix
        return name, ddl

    expected = []
    for name in [
        "facts",
        "assumptions",
        "calcs",
        "questions",
        "deliverables",
        "events",
        "corrections",
    ]:
        for action in ["DELETE", "UPDATE"]:
            trigger = f"{name}_no_{action.lower()}"
            expected.append(
                (
                    trigger,
                    f"CREATE TRIGGER {trigger} BEFORE {action} ON {name} "
                    "BEGIN SELECT RAISE(ABORT, 'append-only state'); END",
                )
            )
        constraints = [keys[name]] + (
            [c["column_names"] for c in uniques] if name == "events" else []
        )
        conditions = " OR ".join(
            "(" + " AND ".join(f"{column} = NEW.{column}" for column in key) + ")"
            for key in constraints
        )
        expected.append(
            (
                f"{name}_no_replace",
                f"CREATE TRIGGER {name}_no_replace BEFORE INSERT ON {name} "
                f"WHEN EXISTS (SELECT 1 FROM {name} WHERE {conditions}) "
                "BEGIN SELECT RAISE(ABORT, 'append-only state'); END",
            )
        )
    with migrated.connect() as connection:
        assert [normalize(row) for row in connection.execute(trigger_query)] == sorted(
            normalize(row) for row in expected
        )
    migrated.dispose()


def test_t011_ac1_repository_alembic_cli_still_migrates(tmp_path) -> None:
    database = f"sqlite+pysqlite:///{tmp_path / 'cli.sqlite'}"
    for direction, revision in [("upgrade", "head"), ("downgrade", "base")]:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "migrations/alembic.ini", direction, revision],
            cwd=ROOT,
            env={**os.environ, "DATABASE_URL": database},
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        engine = create_engine(database)
        tables = inspect(engine).get_table_names()
        assert ("facts" in tables) == (direction == "upgrade")
        engine.dispose()


@pytest.fixture(scope="module")
def fresh_wheel(tmp_path_factory):
    destination = tmp_path_factory.mktemp("migration-wheel")
    result = subprocess.run(
        ["uv", "build", "--offline", "--wheel", "--out-dir", str(destination)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    wheels = list(destination.glob("*.whl"))
    assert len(wheels) == 1
    return wheels[0]


def test_t011_ac1_fresh_wheel_contains_alembic_assets(fresh_wheel) -> None:
    with ZipFile(fresh_wheel) as archive:
        assert {
            "cre_brain/state/migrations/alembic.ini",
            "cre_brain/state/migrations/env.py",
            "cre_brain/state/migrations/versions/0001_state_store.py",
        } <= set(archive.namelist())


def test_t011_ac1_installed_wheel_migrates_without_a_checkout(fresh_wheel) -> None:
    with tempfile.TemporaryDirectory(prefix="cre-installed-wheel-") as directory:
        external = Path(directory)
        assert not external.is_relative_to(ROOT)
        target = external / "installed"
        result = subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--no-deps",
                "--no-index",
                "--target",
                str(target),
                str(fresh_wheel),
            ],
            cwd=external,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        code = """
import sys
from pathlib import Path
sys.path = [str(Path(sys.argv[1]).resolve())] + [
    path for path in sys.path if not Path(path).resolve().is_relative_to(Path(sys.argv[2]))
]
import cre_brain.state.migrate as migrate
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError
assert Path(migrate.__file__).is_relative_to(Path(sys.argv[1]))
config = migrate.migration_config()
assert Path(config.config_file_name).is_relative_to(Path(sys.argv[1]))
engine = create_engine("sqlite+pysqlite:///wheel.sqlite")
migrate.upgrade_database(engine)
assert "facts" in inspect(engine).get_table_names()
with engine.begin() as connection:
    connection.execute(text(
        "INSERT INTO facts VALUES ('u', 'f', 'id', 1, '{}')"
    ))
for statement in ["UPDATE facts SET payload = '{}'", "DELETE FROM facts",
                  "INSERT OR REPLACE INTO facts VALUES ('u', 'f', 'id', 1, '{}')"]:
    try:
        with engine.begin() as connection:
            connection.execute(text(statement))
    except DBAPIError:
        pass
    else:
        raise AssertionError("Wheel migration did not enforce append-only state")
migrate.downgrade_database(engine)
assert inspect(engine).get_table_names() == ["alembic_version"]
"""
        result = subprocess.run(
            [sys.executable, "-I", "-c", code, str(target), str(ROOT / "src")],
            cwd=external,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture(
    params=[
        "sqlite",
        pytest.param(
            "postgresql",
            marks=[pytest.mark.integration, pytest.mark.requires_key("CRE_TEST_DATABASE_URL")],
        ),
    ]
)
def reordered_engine(request, tmp_path):
    if request.param == "sqlite":
        engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'reordered.sqlite'}")
        try:
            yield engine
        finally:
            engine.dispose()
        return
    url = os.environ["CRE_TEST_DATABASE_URL"]
    admin = create_engine(url, connect_args={"client_encoding": "utf8"})
    assert admin.dialect.name == "postgresql"
    schema = "cre_reordered_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(
        url, connect_args={"client_encoding": "utf8", "options": f"-csearch_path={schema}"}
    )
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def test_t011_ac3_reordered_writer_replay_keeps_its_original_assigned_sequence(
    reordered_engine,
) -> None:
    engine = reordered_engine
    metadata.create_all(engine)
    store = EventStore(engine)
    scope = TenantScope(user_id="synthetic-user", firm_id="synthetic-firm")
    first_committed = Event()

    def insert(number):
        if number == 0:
            assert first_committed.wait(timeout=10)
        item = AgentEvent(
            event_id=f"event-{number}",
            task_id="task",
            seq=None,
            origin=("box", 1, number),
            ts=datetime(2026, 10, 4, tzinfo=UTC),
            source="tool",
            kind="tool_result",
            cause_id=None,
            release_id="synthetic",
            runner="fixture",
            payload={"number": number},
        )
        stored = store.append(item, scope=scope)
        if number == 1:
            first_committed.set()
        return stored

    with ThreadPoolExecutor(max_workers=2) as executor:
        stored = list(executor.map(insert, [0, 1]))
    assert sorted(event.seq for event in stored) == [1, 2]
    assert stored[0].seq == 2
    assert stored[1].seq == 1
    before_replay = store.list("task", scope=scope)
    assert len(before_replay) == 2
    assert (
        store.append(stored[0].model_copy(update={"event_id": "replay", "seq": 999}), scope=scope)
        == stored[0]
    )
    assert store.list("task", scope=scope) == before_replay
