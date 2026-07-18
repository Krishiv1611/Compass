import os
import uuid
import shutil
from pathlib import Path
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.models.workspace import Workspace

def create_workspace_record(db: Session, user_id: str, session_id: str, name: str) -> Workspace:
    """Create a new Workspace record and initialize its directory.

    Pre-generates UUID so storage_path can be set before the first commit,
    avoiding a two-commit sequence that leaves the record temporarily path-less.
    """
    workspace_id = str(uuid.uuid4())
    workspace_dir = Path.home() / ".compass" / "workspaces" / user_id / workspace_id
    workspace_dir.mkdir(parents=True, exist_ok=True)

    workspace = Workspace(
        id=workspace_id,
        user_id=user_id,
        session_id=session_id,
        name=name,
        source_type="upload",
        status="uploading",
        storage_path=str(workspace_dir),
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace

def get_workspace(db: Session, workspace_id: str, user_id: str) -> Workspace:
    """Get a workspace by ID, ensuring the user owns it."""
    workspace = db.query(Workspace).filter(
        Workspace.id == workspace_id,
        Workspace.user_id == user_id
    ).first()
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or unauthorized"
        )
    return workspace

def get_workspace_by_session(db: Session, session_id: str, user_id: str) -> Workspace:
    """Legacy helper: Get the most recent workspace for a session."""
    workspace = db.query(Workspace).filter(
        Workspace.session_id == session_id,
        Workspace.user_id == user_id
    ).order_by(Workspace.created_at.desc()).first()
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found for this session"
        )
    return workspace

def update_workspace_stats(db: Session, workspace: Workspace):
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
            if ".git" in file_path.parts or "node_modules" in file_path.parts:
                continue
            count += 1
            try:
                size += file_path.stat().st_size
            except OSError:
                pass
                
    workspace.file_count = count
    workspace.size_bytes = size
    workspace.status = "ready"
    db.commit()
    db.refresh(workspace)
