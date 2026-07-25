"""add project context metadata

Revision ID: 7e1c9a4d2b60
Revises: 0b51d18d8c5a
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7e1c9a4d2b60"
down_revision: Union[str, Sequence[str], None] = "0b51d18d8c5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("oauth_token_encrypted", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("oauth_scopes", sa.Text(), nullable=True))
    for table in ("workspaces", "chat_sessions"):
        op.add_column(table, sa.Column("project_id", sa.String(512), nullable=True))
        op.add_column(table, sa.Column("git_remote", sa.String(1024), nullable=True))
        op.add_column(table, sa.Column("git_branch", sa.String(255), nullable=True))
        op.add_column(table, sa.Column("git_head", sa.String(64), nullable=True))
        op.add_column(table, sa.Column("context_version", sa.String(255), nullable=True))
        op.create_index(f"ix_{table}_project_id", table, ["project_id"])

    for table in ("agent_runs", "workspace_patches"):
        op.add_column(table, sa.Column("project_id", sa.String(512), nullable=True))
        op.add_column(table, sa.Column("context_version", sa.String(255), nullable=True))
        op.create_index(f"ix_{table}_project_id", table, ["project_id"])


def downgrade() -> None:
    for table in ("agent_runs", "workspace_patches"):
        op.drop_index(f"ix_{table}_project_id", table_name=table)
        op.drop_column(table, "context_version")
        op.drop_column(table, "project_id")

    op.drop_column("users", "oauth_scopes")
    op.drop_column("users", "oauth_token_encrypted")

    for table in ("workspaces", "chat_sessions"):
        op.drop_index(f"ix_{table}_project_id", table_name=table)
        op.drop_column(table, "context_version")
        op.drop_column(table, "git_head")
        op.drop_column(table, "git_branch")
        op.drop_column(table, "git_remote")
        op.drop_column(table, "project_id")
