from sqlalchemy import create_engine, inspect

from cre_brain.state.migrate import downgrade_database, upgrade_database
from cre_brain.state.schema import metadata


def test_t011_ac1_alembic_upgrade_and_downgrade_match_schema() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    upgrade_database(engine)
    inspector = inspect(engine)
    assert set(metadata.tables) <= set(inspector.get_table_names())
    assert inspector.get_pk_constraint("facts")["constrained_columns"] == [
        "user_id",
        "firm_id",
        "record_id",
        "version",
    ]
    downgrade_database(engine)
    assert not (set(metadata.tables) & set(inspect(engine).get_table_names()))
