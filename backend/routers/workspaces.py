import os
import shutil
import zipfile
from io import BytesIO
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.auth.dependencies import get_current_user
from backend.db import get_db
from backend.models.user import User
from backend.models.session import ChatSession
from backend.services.workspace import (
    create_workspace_record,
    get_workspace,
    get_workspace_by_session,
    update_workspace_stats,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

# --- Legacy session-based endpoints (temporary compatibility) ---


def _validate_session_ownership(db: Session, user_id: str, session_id: str) -> ChatSession:
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id,
        ChatSession.is_deleted.is_(False),
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _validate_relative_path(path_value: str) -> str:
    clean_path = os.path.normpath(path_value).replace("\\", "/")
    parts = Path(clean_path).parts
    if os.path.isabs(path_value) or ".." in parts:
        raise HTTPException(status_code=400, detail="Invalid path")
    return clean_path


def _safe_workspace_path(workspace_dir: Path, path_value: str) -> Path:
    clean_path = _validate_relative_path(path_value)
    target = (workspace_dir / clean_path).resolve()
    base = workspace_dir.resolve()
    if base != target and base not in target.parents:
        raise HTTPException(status_code=400, detail="Invalid path")
    return target
def _get_active_workspace_path(db: Session, user_id: str, workspace_id: str) -> Path:
    """Helper to get a workspace path from DB."""
    workspace = get_workspace(db, workspace_id, user_id)
    return Path(workspace.storage_path)

@router.post("/{session_id}/upload")
async def upload_workspace(
    session_id: str,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a full directory into the server workspace (Legacy)."""
    # Create a new workspace record instead of wiping the old one
    workspace = create_workspace_record(db, current_user.id, session_id, "Uploaded Project")
    workspace_dir = Path(workspace.storage_path)
    
    saved_files = []
    
    for file in files:
        if not file.filename:
            continue
            
        clean_path = os.path.normpath(file.filename)
        if clean_path.startswith("..") or os.path.isabs(clean_path):
            continue
            
        dest_path = workspace_dir / clean_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        content = await file.read()
        with open(dest_path, "wb") as f:
            f.write(content)
            
        saved_files.append(clean_path)
        
    update_workspace_stats(db, workspace)
        
    return {
        "message": f"Successfully uploaded {len(saved_files)} files to workspace.", 
        "workspace_id": workspace.id,
        "workspace_dir": str(workspace_dir)
    }

@router.get("/{workspace_id}/tree")
def get_workspace_tree(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the file tree of the workspace."""
    workspace_dir = _get_active_workspace_path(db, current_user.id, workspace_id)
    
    def build_tree(dir_path: Path):
        nodes = []
        try:
            for item in sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                if item.name in (".git", "node_modules", "__pycache__"):
                    continue
                    
                node = {
                    "name": item.name,
                    "path": str(item.relative_to(workspace_dir)).replace("\\", "/"),
                    "type": "folder" if item.is_dir() else "file"
                }
                
                if item.is_dir():
                    node["children"] = build_tree(item)
                    
                nodes.append(node)
        except Exception:
            pass
        return nodes
        
    return {"tree": build_tree(workspace_dir), "workspace_dir": str(workspace_dir)}

@router.get("/{workspace_id}/file")
def get_workspace_file(
    workspace_id: str,
    file_path: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Read a specific file from the workspace."""
    workspace_dir = _get_active_workspace_path(db, current_user.id, workspace_id)
    
    target_file = _safe_workspace_path(workspace_dir, file_path)
    
    if not target_file.exists() or not target_file.is_file():
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        content = target_file.read_text(encoding="utf-8")
        return {"content": content}
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Cannot read binary file")

@router.get("/{workspace_id}/download")
def download_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download the entire workspace as a ZIP file."""
    workspace_dir = _get_active_workspace_path(db, current_user.id, workspace_id)
    
    if not workspace_dir.exists() or not any(workspace_dir.iterdir()):
        raise HTTPException(status_code=404, detail="Workspace is empty")
        
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(workspace_dir):
            for file in files:
                file_path = Path(root) / file
                if ".git" in file_path.parts or "node_modules" in file_path.parts:
                    continue
                rel_path = file_path.relative_to(workspace_dir)
                zf.write(file_path, arcname=rel_path)
                
    memory_file.seek(0)
    
    return StreamingResponse(
        memory_file,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=workspace_{workspace_id[:8]}.zip"
        }
    )

@router.get("/{workspace_id}/export-json")
def export_workspace_json(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export the entire workspace as a JSON FileSystemTree for WebContainers."""
    workspace_dir = _get_active_workspace_path(db, current_user.id, workspace_id)
    
    if not workspace_dir.exists():
        raise HTTPException(status_code=404, detail="Workspace not found")
        
    def build_fs_tree(dir_path: Path) -> dict:
        tree = {}
        try:
            for item in dir_path.iterdir():
                if item.name in (".git", "node_modules", "__pycache__"):
                    continue
                if item.is_dir():
                    tree[item.name] = {"directory": build_fs_tree(item)}
                else:
                    try:
                        content = item.read_text(encoding="utf-8")
                        tree[item.name] = {"file": {"contents": content}}
                    except UnicodeDecodeError:
                        # Skip binary files or read as base64 if needed, but WebContainer
                        # usually prefers Uint8Array for binary. For now, we skip binaries
                        # or provide empty string to avoid crash.
                        tree[item.name] = {"file": {"contents": ""}}
        except Exception:
            pass
        return tree
        
    return build_fs_tree(workspace_dir)

class FileCreateRequest(BaseModel):
    path: str
    type: str # 'file' or 'folder'
    content: Optional[str] = ''

class FileUpdateRequest(BaseModel):
    path: str
    content: str

class FileDeleteRequest(BaseModel):
    path: str

class FileRenameRequest(BaseModel):
    old_path: str
    new_path: str

@router.post("/{workspace_id}/file")
def create_workspace_file(
    workspace_id: str,
    body: FileCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace_dir = _get_active_workspace_path(db, current_user.id, workspace_id)
    target_path = _safe_workspace_path(workspace_dir, body.path)
    if target_path.exists():
        raise HTTPException(status_code=400, detail="Path already exists")
        
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if body.type == "folder":
        target_path.mkdir(parents=True, exist_ok=True)
    else:
        target_path.write_text(body.content or "", encoding="utf-8")
        
    return {"message": "Created successfully"}

@router.put("/{workspace_id}/file")
def update_workspace_file(
    workspace_id: str,
    body: FileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace_dir = _get_active_workspace_path(db, current_user.id, workspace_id)
    target_path = _safe_workspace_path(workspace_dir, body.path)
    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
        
    target_path.write_text(body.content, encoding="utf-8")
    return {"message": "Updated successfully"}

@router.delete("/{workspace_id}/file")
def delete_workspace_file(
    workspace_id: str,
    path: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace_dir = _get_active_workspace_path(db, current_user.id, workspace_id)
    target_path = _safe_workspace_path(workspace_dir, path)
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Path not found")
        
    if target_path.is_dir():
        shutil.rmtree(target_path)
    else:
        target_path.unlink()
        
    return {"message": "Deleted successfully"}

@router.post("/{workspace_id}/rename")
def rename_workspace_file(
    workspace_id: str,
    body: FileRenameRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace_dir = _get_active_workspace_path(db, current_user.id, workspace_id)
    old_target = _safe_workspace_path(workspace_dir, body.old_path)
    new_target = _safe_workspace_path(workspace_dir, body.new_path)
    
    if not old_target.exists():
        raise HTTPException(status_code=404, detail="Old path not found")
    if new_target.exists():
        raise HTTPException(status_code=400, detail="New path already exists")
        
    new_target.parent.mkdir(parents=True, exist_ok=True)
    old_target.rename(new_target)
    
    return {"message": "Renamed successfully"}

# --- New Workspace ID based endpoints ---

@router.get("/")
def list_workspaces(
    session_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.models.workspace import Workspace
    query = db.query(Workspace).filter(Workspace.user_id == current_user.id)
    if session_id:
        query = query.filter(Workspace.session_id == session_id)
        
    workspaces = query.order_by(Workspace.created_at.desc()).all()
    return workspaces

# --- Patch APIs ---

from backend.services.patch_manager import (
    apply_patch,
    reject_patch,
    accept_all_patches,
    reject_all_patches,
    undo_patch,
)
from backend.models.patch import WorkspacePatch


class WorkspaceCreateRequest(BaseModel):
    session_id: str
    name: str = "New Project"


@router.post("/create")
def create_workspace(
    body: WorkspaceCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create an empty workspace for a session."""
    workspace = create_workspace_record(
        db, current_user.id, body.session_id, body.name
    )
    update_workspace_stats(db, workspace)
    return workspace


@router.get("/{workspace_id}/patches")
def list_patches(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Auth check
    _get_active_workspace_path(db, current_user.id, workspace_id)

    patches = (
        db.query(WorkspacePatch)
        .filter(WorkspacePatch.workspace_id == workspace_id)
        .order_by(WorkspacePatch.created_at.desc())
        .all()
    )
    return patches


@router.post("/{workspace_id}/patches/{patch_id}/apply")
def apply_workspace_patch(
    workspace_id: str,
    patch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patch = apply_patch(db, patch_id, current_user.id)
    return {"message": "Patch applied successfully", "patch": patch}


@router.post("/{workspace_id}/patches/{patch_id}/reject")
def reject_workspace_patch(
    workspace_id: str,
    patch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patch = reject_patch(db, patch_id, current_user.id)
    return {"message": "Patch rejected successfully", "patch": patch}


@router.post("/{workspace_id}/patches/accept-all")
def accept_all_workspace_patches(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Accept all pending patches for a workspace."""
    _get_active_workspace_path(db, current_user.id, workspace_id)
    count = accept_all_patches(db, workspace_id, current_user.id)
    return {"message": f"Accepted {count} patches"}


@router.post("/{workspace_id}/patches/reject-all")
def reject_all_workspace_patches(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reject all pending patches for a workspace."""
    _get_active_workspace_path(db, current_user.id, workspace_id)
    count = reject_all_patches(db, workspace_id, current_user.id)
    return {"message": f"Rejected {count} patches"}


@router.post("/{workspace_id}/patches/{patch_id}/undo")
def undo_workspace_patch(
    workspace_id: str,
    patch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patch = undo_patch(db, patch_id, current_user.id)
    return {"message": "Patch undone successfully", "patch": patch}


