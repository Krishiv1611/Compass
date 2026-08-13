"""Separate GitHub repository connections from login identity.

Revision ID: 81a003
Revises: 81a002
"""

from alembic import op
import sqlalchemy as sa

revision = "81a003"
down_revision = "81a002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "github_connections",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("provider_user_id", sa.String(length=255), nullable=False),
        sa.Column("login", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("token_encrypted", sa.Text(), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=True),
        sa.Column("method", sa.String(length=20), nullable=False, server_default="oauth"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.execute(
        """
        INSERT INTO github_connections (
            user_id, provider_user_id, login, avatar_url, token_encrypted,
            scopes, method, created_at, updated_at
        )
        SELECT id, oauth_provider_id, display_name, avatar_url,
               oauth_token_encrypted, oauth_scopes, 'oauth', created_at, updated_at
        FROM users
        WHERE oauth_provider = 'github' AND oauth_token_encrypted IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE users
        SET oauth_token_encrypted = NULL, oauth_scopes = NULL
        WHERE oauth_provider = 'github'
        """
    )


def downgrade() -> None:
    op.drop_table("github_connections")
