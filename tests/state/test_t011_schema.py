from sqlalchemy import create_engine, inspect

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
