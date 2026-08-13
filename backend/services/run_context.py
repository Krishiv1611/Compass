"""Detached values needed to execute one agent turn."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from fastapi import HTTPException, status

from backend.db import SessionLocal
from backend.models.user import User
from backend.services.ownership import owned_session
from backend.services.workspace import get_workspace_by_session


@dataclass(frozen=True, slots=True)
class RunContextSnapshot:
    """Plain values copied from the database before an agent run starts."""

    user_id: str
    session_id: str
    thread_id: str
    workspace_id: str
    workspace_path: str
    project_id: str
    context_version: str | None
    session_context_version: str | None
    preferences: dict
    source_type: str | None = None
    git_remote: str | None = None
    git_branch: str | None = None
    git_head: str | None = None


def load_run_context(session_id: str, user_id: str) -> RunContextSnapshot:
    """Load one run's values in a short session and return no ORM objects."""
    with SessionLocal() as db:
        chat_session = owned_session(db, session_id, user_id)
        workspace = get_workspace_by_session(db, session_id, user_id)
        user = (
            db.query(User)
            .filter(User.id == user_id, User.is_active.is_(True))
            .first()
        )
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        return RunContextSnapshot(
            user_id=user.id,
            session_id=chat_session.id,
            thread_id=chat_session.thread_id,
            workspace_id=workspace.id,
            workspace_path=workspace.storage_path,
            project_id=workspace.project_id or f"workspace:{workspace.id}",
            context_version=workspace.context_version,
            session_context_version=chat_session.context_version,
            preferences=deepcopy(user.preferences or {}),
            source_type=workspace.source_type,
            git_remote=workspace.git_remote,
            git_branch=workspace.git_branch,
            git_head=workspace.git_head,
        )
