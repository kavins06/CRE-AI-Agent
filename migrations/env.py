from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine


def run_migrations_online() -> None:
    connection = context.config.attributes.get("connection")
    engine = None
    if connection is None:
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL is required for migration CLI use")
        engine = create_engine(url)
        connection = engine.connect()
    try:
        context.configure(connection=connection, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()
    finally:
        if engine is not None:
            connection.close()
            engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("State migrations require an online database connection")
run_migrations_online()
