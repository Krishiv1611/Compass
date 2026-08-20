"""Revoke refresh tokens by version and uniquely bind OAuth identities.

Revision ID: 81a004
Revises: 81a003
"""

from alembic import op
import sqlalchemy as sa

revision = "81a004"
down_revision = "81a003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("refresh_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_unique_constraint(
        "uq_users_oauth_provider_identity",
        "users",
        ["oauth_provider", "oauth_provider_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_users_oauth_provider_identity", "users", type_="unique")
    op.drop_column("users", "refresh_version")
