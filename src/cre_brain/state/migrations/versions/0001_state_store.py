"""Frozen initial append-only state store.

Revision ID: 0001_state_store

Historical DDL and mutation guards must not depend on application metadata.
"""

from alembic import op
from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)

revision = "0001_state_store"
down_revision = None
branch_labels = None
depends_on = None

metadata = MetaData()
VERSIONED = ("facts", "assumptions", "calcs", "questions", "deliverables")
IMMUTABLE = (*VERSIONED, "events", "corrections")


def tenant_columns() -> list[Column[str]]:
    return [
        Column("user_id", String(128), primary_key=True),
        Column("firm_id", String(128), primary_key=True),
    ]


for name in VERSIONED:
    Table(
        name,
        metadata,
        *tenant_columns(),
        Column("record_id", String(128), primary_key=True),
        Column("version", Integer, primary_key=True),
        Column("payload", JSON, nullable=False),
        CheckConstraint("version >= 1", name=f"{name}_positive_version"),
    )

Table(
    "edges",
    metadata,
    *tenant_columns(),
    Column("src_id", String(128), primary_key=True),
    Column("dst_id", String(128), primary_key=True),
)
Table(
    "events",
    metadata,
    *tenant_columns(),
    Column("event_id", String(128), primary_key=True),
    Column("task_id", String(128), nullable=False),
    Column("seq", Integer, nullable=False),
    Column("origin_box", String(128)),
    Column("origin_segment", Integer),
    Column("origin_local_seq", Integer),
    Column("payload", JSON, nullable=False),
    UniqueConstraint("user_id", "firm_id", "task_id", "seq", name="events_task_seq"),
    UniqueConstraint(
        "user_id",
        "firm_id",
        "task_id",
        "origin_box",
        "origin_segment",
        "origin_local_seq",
        name="events_task_origin",
    ),
    CheckConstraint("seq >= 1", name="events_positive_seq"),
    CheckConstraint(
        "(origin_box IS NULL AND origin_segment IS NULL AND origin_local_seq IS NULL) OR "
        "(origin_box IS NOT NULL AND origin_segment IS NOT NULL AND "
        "origin_local_seq IS NOT NULL AND origin_segment >= 0 AND origin_local_seq >= 0)",
        name="events_complete_origin",
    ),
)
Table(
    "jobs",
    metadata,
    *tenant_columns(),
    Column("task_id", String(128), primary_key=True),
    Column("segment_no", Integer, primary_key=True),
    Column("status", String(32), nullable=False),
    Column("payload", JSON, nullable=False),
    CheckConstraint("segment_no >= 0", name="jobs_nonnegative_segment"),
)
Table(
    "corrections",
    metadata,
    *tenant_columns(),
    Column("correction_id", String(128), primary_key=True),
    Column("task_id", String(128), nullable=False),
    Column("payload", JSON, nullable=False),
)


def install_guards(dialect: str) -> None:
    if dialect == "postgresql":
        op.execute(
            "CREATE OR REPLACE FUNCTION cre_state_reject_mutation() RETURNS trigger "
            "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'append-only state'; END; $$"
        )
    for name in IMMUTABLE:
        if dialect == "sqlite":
            for action in ("UPDATE", "DELETE"):
                op.execute(
                    f"CREATE TRIGGER {name}_no_{action.lower()} BEFORE {action} "
                    f"ON {name} BEGIN SELECT RAISE(ABORT, 'append-only state'); END"
                )
            table = metadata.tables[name]
            constraints = [table.primary_key] + sorted(
                (c for c in table.constraints if isinstance(c, UniqueConstraint)),
                key=lambda c: str(c.name),
            )
            conflicts = " OR ".join(
                "("
                + " AND ".join(f"{column.name} = NEW.{column.name}" for column in c.columns)
                + ")"
                for c in constraints
            )
            op.execute(
                f"CREATE TRIGGER {name}_no_replace BEFORE INSERT ON {name} "
                f"WHEN EXISTS (SELECT 1 FROM {name} WHERE {conflicts}) "
                "BEGIN SELECT RAISE(ABORT, 'append-only state'); END"
            )
        elif dialect == "postgresql":
            for actions, suffix, level in (
                ("UPDATE OR DELETE", "mutation", "ROW"),
                ("TRUNCATE", "truncate", "STATEMENT"),
            ):
                op.execute(
                    f"CREATE TRIGGER {name}_no_{suffix} BEFORE {actions} ON {name} "
                    f"FOR EACH {level} EXECUTE FUNCTION cre_state_reject_mutation()"
                )


def upgrade() -> None:
    metadata.create_all(op.get_bind(), checkfirst=False)
    install_guards(op.get_bind().dialect.name)


def downgrade() -> None:
    bind = op.get_bind()
    metadata.drop_all(bind, checkfirst=False)
    if bind.dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS cre_state_reject_mutation()")
