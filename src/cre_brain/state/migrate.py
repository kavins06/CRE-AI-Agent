"""Programmatic Alembic entry points for controlled setup and tests."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine


def migration_config() -> Config:
    return Config(Path(__file__).resolve().with_name("migrations") / "alembic.ini")


def upgrade_database(engine: Engine) -> None:
    config = migration_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def downgrade_database(engine: Engine) -> None:
    config = migration_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
