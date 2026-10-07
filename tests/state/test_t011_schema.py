import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from cre_brain.state.schema import metadata


def test_t011_ac1_sqlite_contains_all_state_tables() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)
    assert set(inspect(engine).get_table_names()) == {
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
    for name in metadata.tables:
        columns = {column["name"] for column in inspect(engine).get_columns(name)}
        assert {"user_id", "firm_id"} <= columns


@pytest.mark.parametrize("table", ["facts", "deliverables"])
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE", "REPLACE"])
def test_t011_ac2_database_rejects_history_mutation(table, operation) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)
    insert = (
        f"INTO {table} (user_id, firm_id, record_id, version, payload) "
        "VALUES ('u','f','id',1,'{}')"
    )
    with engine.begin() as connection:
        connection.execute(text(f"INSERT {insert}"))
    sql = {
        "UPDATE": f"UPDATE {table} SET payload = '{{\"changed\": true}}'",
        "DELETE": f"DELETE FROM {table}",
        "REPLACE": f"INSERT OR REPLACE {insert}",
    }[operation]
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(text(sql))
    with engine.connect() as connection:
        assert connection.execute(text(f"SELECT payload FROM {table}")).scalar_one() == "{}"
