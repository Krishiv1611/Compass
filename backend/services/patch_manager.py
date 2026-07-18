import os
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.models.patch import WorkspacePatch
from backend.services.workspace import get_workspace


def create_patch(db: Session, workspace_id: str, run_id: str | None, changes: list) -> WorkspacePatch:
    """Create a new WorkspacePatch with proposed changes.

    Each change dict should have: {type, path, content}.
    This function enriches each change with 'before' (existing content)
    and 'after' (new content) so the diff viewer has real data.
    """
    from backend.models.workspace import Workspace

    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    workspace_dir = Path(workspace.storage_path) if workspace else None

    enriched_changes = []
    for change in changes:
        change_type = change.get("type", "edit")
        path = change.get("path", "")
        new_content = change.get("content", "")

        before = ""
        if workspace_dir and path:
            clean = os.path.normpath(path)
            target = workspace_dir / clean
            if target.exists() and target.is_file():
                try:
                    before = target.read_text(encoding="utf-8")
                except Exception:
                    before = ""

        enriched_changes.append(
            {
                "type": change_type,
                "path": path,
                "before": before,
                "after": new_content,
                # keep legacy 'content' key for apply_patch compatibility
                "content": new_content,
            }
        )

    patch = WorkspacePatch(
        workspace_id=workspace_id,
        run_id=run_id,
        status="pending",
        changes=enriched_changes,
    )
    db.add(patch)
    db.commit()
    db.refresh(patch)
    return patch


def get_patch(db: Session, patch_id: str, user_id: str) -> WorkspacePatch:
    patch = db.query(WorkspacePatch).filter(WorkspacePatch.id == patch_id).first()
    if not patch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patch not found")

    workspace = get_workspace(db, patch.workspace_id, user_id)
    return patch


def apply_patch(db: Session, patch_id: str, user_id: str) -> WorkspacePatch:
    """Apply a pending patch to the filesystem."""
    patch = get_patch(db, patch_id, user_id)
    if patch.status != "pending":
        raise HTTPException(status_code=400, detail=f"Patch is already {patch.status}")

    workspace = get_workspace(db, patch.workspace_id, user_id)
    workspace_dir = Path(workspace.storage_path)

    for change in patch.changes:
        change_type = change.get("type")
        path = change.get("path")
        # prefer 'after' key, fall back to legacy 'content'
        content = change.get("after") or change.get("content", "")

        if not path:
            continue

        clean_path = os.path.normpath(path)
        if clean_path.startswith("..") or os.path.isabs(clean_path):
            continue

        target_path = workspace_dir / clean_path

        if change_type in ("edit", "create"):
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")
        elif change_type == "delete":
            if target_path.exists():
                if target_path.is_file():
                    target_path.unlink()

    patch.status = "applied"
    patch.applied_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(patch)
    return patch


def reject_patch(db: Session, patch_id: str, user_id: str) -> WorkspacePatch:
    """Reject a pending patch."""
    patch = get_patch(db, patch_id, user_id)
    if patch.status != "pending":
        raise HTTPException(status_code=400, detail=f"Patch is already {patch.status}")

    patch.status = "rejected"
    db.commit()
    db.refresh(patch)
    return patch


def accept_all_patches(db: Session, workspace_id: str, user_id: str) -> int:
    """Accept all pending patches for a workspace. Returns count applied."""
    from backend.models.workspace import Workspace

    patches = (
        db.query(WorkspacePatch)
        .filter(
            WorkspacePatch.workspace_id == workspace_id,
            WorkspacePatch.status == "pending",
        )
        .all()
    )
    count = 0
    for patch in patches:
        apply_patch(db, patch.id, user_id)
        count += 1
    return count


def reject_all_patches(db: Session, workspace_id: str, user_id: str) -> int:
    """Reject all pending patches for a workspace. Returns count rejected."""
    patches = (
        db.query(WorkspacePatch)
        .filter(
            WorkspacePatch.workspace_id == workspace_id,
            WorkspacePatch.status == "pending",
        )
        .all()
    )
    count = 0
    for patch in patches:
        reject_patch(db, patch.id, user_id)
        count += 1
    return count
