"""add explicit active workspace selection

Revision ID: 81a001
Revises: 7e1c9a4d2b60
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "81a001"
down_revision: Union[str, Sequence[str], None] = "7e1c9a4d2b60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FOREIGN_KEY = "fk_chat_sessions_active_workspace_id_workspaces"
_INDEX = "ix_chat_sessions_active_workspace_id"


def upgrade() -> None:
    op.add_column(
        "chat_sessions",
        sa.Column("active_workspace_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        _FOREIGN_KEY,
        "chat_sessions",
        "workspaces",
        ["active_workspace_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        _INDEX,
        "chat_sessions",
        ["active_workspace_id"],
        unique=False,
    )
    op.execute(
        sa.text(
            """
            UPDATE chat_sessions
            SET active_workspace_id = (
                SELECT workspaces.id
                FROM workspaces
                WHERE workspaces.session_id = chat_sessions.id
                  AND workspaces.status = 'ready'
                ORDER BY workspaces.created_at DESC
                LIMIT 1
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_index(_INDEX, table_name="chat_sessions")
    op.drop_constraint(_FOREIGN_KEY, "chat_sessions", type_="foreignkey")
    op.drop_column("chat_sessions", "active_workspace_id")
