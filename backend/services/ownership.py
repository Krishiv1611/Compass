"""Canonical ownership queries and workspace path boundaries."""

from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.models.patch import WorkspacePatch
from backend.models.session import ChatSession
from backend.models.workspace import Workspace


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def owned_session(db: Session, session_id: str, user_id: str) -> ChatSession:
    """Return one active session owned by the user, or hide it as not found."""
    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
            ChatSession.is_deleted.is_(False),
        )
        .first()
    )
    if not session:
        raise _not_found("Session not found")
    return session


def owned_workspace(db: Session, workspace_id: str, user_id: str) -> Workspace:
    """Return a workspace whose record and parent session belong to the user."""
    workspace = (
        db.query(Workspace)
        .join(ChatSession, ChatSession.id == Workspace.session_id)
        .filter(
            Workspace.id == workspace_id,
            Workspace.user_id == user_id,
            ChatSession.user_id == user_id,
            ChatSession.is_deleted.is_(False),
        )
        .first()
    )
    if not workspace:
        raise _not_found("Workspace not found")
    return workspace


def owned_patch(
    db: Session,
    workspace_id: str,
    patch_id: str,
    user_id: str,
) -> WorkspacePatch:
    """Return a patch only through its requested, user-owned workspace."""
    patch = (
        db.query(WorkspacePatch)
        .join(Workspace, Workspace.id == WorkspacePatch.workspace_id)
        .join(ChatSession, ChatSession.id == Workspace.session_id)
        .filter(
            WorkspacePatch.id == patch_id,
            WorkspacePatch.workspace_id == workspace_id,
            Workspace.user_id == user_id,
            ChatSession.user_id == user_id,
            ChatSession.is_deleted.is_(False),
        )
        .first()
    )
    if not patch:
        raise _not_found("Patch not found")
    return patch


def safe_workspace_target(
    root: Path,
    relative: str,
    *,
    allow_root: bool = False,
) -> Path:
    """Resolve a child path without allowing traversal or implicit root access."""
    if not relative.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A file or folder path is required",
        )

    base = root.resolve()
    target = (base / relative).resolve()
    if target != base and base not in target.parents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace path",
        )
    if target == base and not allow_root:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workspace root cannot be targeted",
        )
    return target
