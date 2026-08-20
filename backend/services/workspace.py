import os
import uuid
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from agent.workspace import discover_local_workspace
from backend.config import settings
from backend.models.session import ChatSession
from backend.models.workspace import Workspace
from backend.services.ownership import owned_session, owned_workspace


def create_workspace_record(db: Session, user_id: str, session_id: str, name: str) -> Workspace:
    """Create a new Workspace record and initialize its directory.

    Pre-generates UUID so storage_path can be set before the first commit,
    avoiding a two-commit sequence that leaves the record temporarily path-less.
    """
    workspace_id = str(uuid.uuid4())
    workspace_dir = Path(settings.workspace_root) / user_id / workspace_id
    workspace_dir.mkdir(parents=True, exist_ok=True)

    workspace = Workspace(
        id=workspace_id,
        user_id=user_id,
        session_id=session_id,
        name=name,
        source_type="upload",
        status="uploading",
        storage_path=str(workspace_dir),
        project_id=f"workspace:{workspace_id}",
        context_version="content:empty",
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


def get_workspace(db: Session, workspace_id: str, user_id: str) -> Workspace:
    """Get a workspace by ID, ensuring the user owns it."""
    return owned_workspace(db, workspace_id, user_id)


def get_workspace_by_session(db: Session, session_id: str, user_id: str) -> Workspace:
    """Return only the ready workspace explicitly selected for the session."""
    workspace = (
        db.query(Workspace)
        .join(ChatSession, ChatSession.active_workspace_id == Workspace.id)
        .filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
            ChatSession.is_deleted.is_(False),
            Workspace.user_id == user_id,
            Workspace.session_id == session_id,
            Workspace.status == "ready",
        )
        .first()
    )
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No ready active workspace is attached to this session",
        )
    return workspace


def _sync_session_context(session: ChatSession, workspace: Workspace) -> None:
    session.active_workspace_id = workspace.id
    session.project_id = workspace.project_id
    session.git_remote = workspace.git_remote
    session.git_branch = workspace.git_branch
    session.git_head = workspace.git_head
    session.context_version = workspace.context_version


def attach_active_workspace(
    db: Session,
    session_id: str,
    workspace_id: str,
    user_id: str,
) -> Workspace:
    """Attach one ready, owned workspace to its owned session."""
    session = owned_session(db, session_id, user_id)
    workspace = owned_workspace(db, workspace_id, user_id)
    if workspace.session_id != session.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found for this session",
        )
    if workspace.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workspace is not ready",
        )

    _sync_session_context(session, workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


def update_workspace_stats(db: Session, workspace: Workspace, sync_session: bool = True):
    """Update file count and size stats based on current directory contents."""
    path = Path(workspace.storage_path)
    if not path.exists():
        workspace.status = "error"
        db.commit()
        return

    count = 0
    size = 0
    for root, _, files in os.walk(path):
        for file in files:
            file_path = Path(root) / file
            relative_parts = file_path.relative_to(path).parts
            if (
                ".git" in relative_parts
                or "node_modules" in relative_parts
                or relative_parts[:2] == (".compass", "checkpoints")
            ):
                continue
            count += 1
            try:
                size += file_path.stat().st_size
            except OSError:
                pass
                
    workspace.file_count = count
    workspace.size_bytes = size
    identity = discover_local_workspace(path)
    if identity.git_head:
        workspace.git_head = identity.git_head
    workspace.context_version = identity.context_version
    if sync_session and workspace.session is not None:
        _sync_session_context(workspace.session, workspace)
    workspace.status = "ready"
    db.commit()
    db.refresh(workspace)
