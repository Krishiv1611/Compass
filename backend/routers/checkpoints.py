"""Owned web endpoints for previewing and restoring workspace checkpoints."""

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agent.checkpoints import (
    CheckpointConflictError,
    get_checkpoint,
    list_checkpoints,
    preview_restore,
    restore_checkpoint,
)
from agent.runtime.events import StreamEvent, StreamEventType
from backend.auth.dependencies import get_current_user
from backend.db import get_db
from backend.models.user import User
from backend.services.ownership import owned_workspace
from backend.services.workspace import update_workspace_stats
from backend.ws.hub import manager


router = APIRouter(
    prefix="/workspaces/{workspace_id}/checkpoints", tags=["checkpoints"]
)


class RestoreCheckpointRequest(BaseModel):
    force: bool = False


def _owned_checkpoint(workspace, checkpoint_id: str):
    try:
        checkpoint = get_checkpoint(workspace.storage_path, checkpoint_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    if checkpoint.workspace_id != workspace.id:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    return checkpoint


@router.get("")
def get_workspace_checkpoints(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = owned_workspace(db, workspace_id, str(current_user.id))
    return [
        item.model_dump(mode="json")
        for item in list_checkpoints(
            workspace.storage_path, workspace_id=workspace.id
        )
    ]


@router.get("/{checkpoint_id}/preview")
def get_checkpoint_restore_preview(
    workspace_id: str,
    checkpoint_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = owned_workspace(db, workspace_id, str(current_user.id))
    _owned_checkpoint(workspace, checkpoint_id)
    return preview_restore(workspace.storage_path, checkpoint_id).model_dump(mode="json")


@router.post("/{checkpoint_id}/restore")
def restore_workspace_checkpoint(
    workspace_id: str,
    checkpoint_id: str,
    body: RestoreCheckpointRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = owned_workspace(db, workspace_id, str(current_user.id))
    _owned_checkpoint(workspace, checkpoint_id)
    preview = preview_restore(workspace.storage_path, checkpoint_id)
    try:
        checkpoint = restore_checkpoint(
            workspace.storage_path, checkpoint_id, force=body.force
        )
    except CheckpointConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": "Checkpoint restore conflicts", "conflicts": exc.conflicts},
        )
    update_workspace_stats(db, workspace)
    event_data = {
        "checkpoint_id": checkpoint.id,
        "affected_files": preview.changes,
    }
    background_tasks.add_task(
        manager.broadcast,
        workspace.session_id,
        StreamEvent(type=StreamEventType.CHECKPOINT_RESTORED, data=event_data),
    )
    background_tasks.add_task(
        manager.broadcast,
        workspace.session_id,
        StreamEvent(type=StreamEventType.WORKSPACE_PATCH, data=event_data),
    )
    return event_data
