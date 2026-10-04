"""Initial append-only state store.

Revision ID: 0001_state_store
"""

from alembic import op

from cre_brain.state.schema import metadata

revision = "0001_state_store"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    metadata.create_all(op.get_bind(), checkfirst=False)


def downgrade() -> None:
    bind = op.get_bind()
    metadata.drop_all(bind, checkfirst=False)
    if bind.dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS cre_state_reject_mutation()")
