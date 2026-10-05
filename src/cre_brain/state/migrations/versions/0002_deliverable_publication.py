"""Bounded protected publication on the existing immutable deliverables row.

Revision ID: 0002_deliverable_publication
The historical table/column schema and its whole-row mutation guards stay intact.
"""

from alembic import op
from sqlalchemy import CheckConstraint, Column, LargeBinary

revision = "0002_deliverable_publication"
down_revision = "0001_state_store"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "deliverables",
        Column(
            "publication",
            LargeBinary,
            CheckConstraint(
                "publication IS NULL OR length(publication) <= 33685508",
                name="deliverables_bounded_publication",
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # Native DROP COLUMN preserves UPDATE/DELETE/REPLACE/TRUNCATE guards;
    # rebuilding the table would discard SQLite triggers.
    op.drop_column("deliverables", "publication")
