"""Add optimistic version to workspace patches.

Revision ID: 81a002
Revises: 81a001
"""

from alembic import op
import sqlalchemy as sa

revision = "81a002"
down_revision = "81a001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspace_patches",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("workspace_patches", "version", server_default=None)


def downgrade() -> None:
    op.drop_column("workspace_patches", "version")
