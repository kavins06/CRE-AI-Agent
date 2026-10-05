"""Tenant-scoped SQL tables; payloads use the domain's lossless JSON contracts."""

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)

from cre_brain.state.immutability import register_append_only

metadata = MetaData()
VERSIONED = ("facts", "assumptions", "calcs", "questions", "deliverables")


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
        *(
            [
                Column(
                    "publication",
                    LargeBinary,
                    CheckConstraint(
                        "publication IS NULL OR length(publication) <= 33685508",
                        name="deliverables_bounded_publication",
                    ),
                    nullable=True,
                )
            ]
            if name == "deliverables"
            else []
        ),
        CheckConstraint("version >= 1", name=f"{name}_positive_version"),
    )

edges = Table(
    "edges",
    metadata,
    *tenant_columns(),
    Column("src_id", String(128), primary_key=True),
    Column("dst_id", String(128), primary_key=True),
)
events = Table(
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
jobs = Table(
    "jobs",
    metadata,
    *tenant_columns(),
    Column("task_id", String(128), primary_key=True),
    Column("segment_no", Integer, primary_key=True),
    Column("status", String(32), nullable=False),
    Column("payload", JSON, nullable=False),
    CheckConstraint("segment_no >= 0", name="jobs_nonnegative_segment"),
)
corrections = Table(
    "corrections",
    metadata,
    *tenant_columns(),
    Column("correction_id", String(128), primary_key=True),
    Column("task_id", String(128), nullable=False),
    Column("payload", JSON, nullable=False),
)

register_append_only(metadata, (*VERSIONED, "events", "corrections"))
