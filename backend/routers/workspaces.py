import os
import shutil
import zipfile
from io import BytesIO
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.auth.dependencies import get_current_user
from backend.db import get_db
from backend.models.user import User
from backend.services.workspace import (
    attach_active_workspace,
    create_workspace_record,
    get_workspace,
    update_workspace_stats,
)
from backend.services.ownership import (
    owned_patch,
    owned_session,
    safe_workspace_target,
)
from backend.ws.hub import manager
from backend.schemas.chat import StreamEvent, StreamEventType
from backend.models.workspace import Workspace
from backend.models.patch import WorkspacePatch
from backend.services.patch_manager import (
    accept_all_patches,
    apply_patch,
    reject_all_patches,
    reject_patch,
    resolve_patch_file,
    undo_patch,
)

def _notify_patch_event(db: Session, workspace_id: str, background_tasks: BackgroundTasks):
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if ws and ws.session_id:
        event = StreamEvent(type=StreamEventType.WORKSPACE_PATCH)
        background_tasks.add_task(manager.broadcast, ws.session_id, event)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

# --- Legacy session-based endpoints (temporary compatibility) ---


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
    owned_session(db, session_id, current_user.id)
    # Create a new workspace record instead of wiping the old one
    workspace = create_workspace_record(db, current_user.id, session_id, "Uploaded Project")
    workspace_dir = Path(workspace.storage_path)
    
    saved_files = []
    
    for file in files:
        if not file.filename:
            continue
            
        clean_path = os.path.normpath(file.filename).replace("\\", "/")
        try:
            dest_path = safe_workspace_target(workspace_dir, clean_path)
        except HTTPException:
            continue

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        content = await file.read()
        with open(dest_path, "wb") as f:
            f.write(content)
            
        saved_files.append(clean_path)
        
    update_workspace_stats(db, workspace)
        
    return {
        "message": f"Successfully uploaded {len(saved_files)} files to workspace.", 
        "workspace_id": workspace.id,
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
        
    return {"tree": build_tree(workspace_dir)}

@router.get("/{workspace_id}/file")
def get_workspace_file(
    workspace_id: str,
    file_path: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Read a specific file from the workspace."""
    workspace_dir = _get_active_workspace_path(db, current_user.id, workspace_id)
    
    target_file = safe_workspace_target(workspace_dir, file_path)
    
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
    workspace = get_workspace(db, workspace_id, current_user.id)
    workspace_dir = Path(workspace.storage_path)
    target_path = safe_workspace_target(workspace_dir, body.path)
    if target_path.exists():
        raise HTTPException(status_code=400, detail="Path already exists")
        
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if body.type == "folder":
        target_path.mkdir(parents=True, exist_ok=True)
    else:
        target_path.write_text(body.content or "", encoding="utf-8")
        
    update_workspace_stats(db, workspace, sync_session=False)
    return {"message": "Created successfully"}

@router.put("/{workspace_id}/file")
def update_workspace_file(
    workspace_id: str,
    body: FileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = get_workspace(db, workspace_id, current_user.id)
    workspace_dir = Path(workspace.storage_path)
    target_path = safe_workspace_target(workspace_dir, body.path)
    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
        
    target_path.write_text(body.content, encoding="utf-8")
    update_workspace_stats(db, workspace, sync_session=False)
    return {"message": "Updated successfully"}

@router.delete("/{workspace_id}/file")
def delete_workspace_file(
    workspace_id: str,
    path: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = get_workspace(db, workspace_id, current_user.id)
    workspace_dir = Path(workspace.storage_path)
    target_path = safe_workspace_target(workspace_dir, path)
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Path not found")
        
    if target_path.is_dir():
        shutil.rmtree(target_path)
    else:
        target_path.unlink()
        
    update_workspace_stats(db, workspace, sync_session=False)
    return {"message": "Deleted successfully"}

@router.post("/{workspace_id}/rename")
def rename_workspace_file(
    workspace_id: str,
    body: FileRenameRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = get_workspace(db, workspace_id, current_user.id)
    workspace_dir = Path(workspace.storage_path)
    old_target = safe_workspace_target(workspace_dir, body.old_path)
    new_target = safe_workspace_target(workspace_dir, body.new_path)
    
    if not old_target.exists():
        raise HTTPException(status_code=404, detail="Old path not found")
    if new_target.exists():
        raise HTTPException(status_code=400, detail="New path already exists")
        
    new_target.parent.mkdir(parents=True, exist_ok=True)
    old_target.rename(new_target)
    
    update_workspace_stats(db, workspace, sync_session=False)
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
    resolve_patch_file,
)
from backend.models.patch import WorkspacePatch


class WorkspaceCreateRequest(BaseModel):
    session_id: str
    name: str = "New Project"


class WorkspaceAttachRequest(BaseModel):
    session_id: str


class PatchFileAction(BaseModel):
    path: str


@router.get("/{workspace_id}/context")
def get_workspace_context(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = get_workspace(db, workspace_id, current_user.id)
    session = owned_session(db, workspace.session_id, current_user.id)
    return {
        "project_id": workspace.project_id,
        "git_remote": workspace.git_remote,
        "git_branch": workspace.git_branch,
        "git_head": workspace.git_head,
        "context_version": workspace.context_version,
        "session_context_version": session.context_version,
        "mismatch": bool(
            session.context_version
            and workspace.context_version
            and session.context_version != workspace.context_version
        ),
    }


@router.post("/{workspace_id}/context/refresh")
def refresh_workspace_context(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = get_workspace(db, workspace_id, current_user.id)
    session = owned_session(db, workspace.session_id, current_user.id)
    session.project_id = workspace.project_id
    session.git_remote = workspace.git_remote
    session.git_branch = workspace.git_branch
    session.git_head = workspace.git_head
    session.context_version = workspace.context_version
    db.commit()
    return {"message": "Project context refreshed", "context_version": session.context_version}


@router.get("/{workspace_id}/search")
def search_workspace_files(
    workspace_id: str,
    q: str = "",
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = get_workspace(db, workspace_id, current_user.id)
    root = Path(workspace.storage_path)
    query = q.strip().lower()
    limit = max(1, min(limit, 100))
    ignored = {".git", "node_modules", ".venv", "__pycache__", "dist", "build"}
    matches = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part in ignored for part in path.parts):
            continue
        relative = path.relative_to(root).as_posix()
        if not query or query in relative.lower():
            matches.append({"path": relative, "name": path.name})
        if len(matches) >= limit:
            break
    return {"files": matches}


@router.post("/create")
def create_workspace(
    body: WorkspaceCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create an empty workspace for a session."""
    owned_session(db, body.session_id, current_user.id)
    workspace = create_workspace_record(
        db, current_user.id, body.session_id, body.name
    )
    update_workspace_stats(db, workspace)
    return workspace


@router.post("/{workspace_id}/attach")
def attach_workspace(
    workspace_id: str,
    body: WorkspaceAttachRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Select one ready workspace as the session's active project."""
    return attach_active_workspace(
        db,
        body.session_id,
        workspace_id,
        current_user.id,
    )


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
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owned_patch(db, workspace_id, patch_id, current_user.id)
    patch = apply_patch(db, patch_id, current_user.id)
    _notify_patch_event(db, workspace_id, background_tasks)
    return {"message": "Patch applied successfully", "patch": patch}


@router.post("/{workspace_id}/patches/{patch_id}/reject")
def reject_workspace_patch(
    workspace_id: str,
    patch_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owned_patch(db, workspace_id, patch_id, current_user.id)
    patch = reject_patch(db, patch_id, current_user.id)
    _notify_patch_event(db, workspace_id, background_tasks)
    return {"message": "Patch rejected successfully", "patch": patch}


@router.post("/{workspace_id}/patches/{patch_id}/files/{action}")
def resolve_workspace_patch_file(
    workspace_id: str,
    patch_id: str,
    action: str,
    body: PatchFileAction,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if action not in {"apply", "reject", "undo"}:
        raise HTTPException(status_code=400, detail="Unsupported patch action")
    owned_patch(db, workspace_id, patch_id, current_user.id)
    patch = resolve_patch_file(db, patch_id, current_user.id, body.path, action)
    _notify_patch_event(db, workspace_id, background_tasks)
    return {"message": f"File change {action}ed", "patch": patch}


@router.post("/{workspace_id}/patches/accept-all")
def accept_all_workspace_patches(
    workspace_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Accept all pending patches for a workspace."""
    _get_active_workspace_path(db, current_user.id, workspace_id)
    count = accept_all_patches(db, workspace_id, current_user.id)
    if count > 0:
        _notify_patch_event(db, workspace_id, background_tasks)
    return {"message": f"Accepted {count} patches"}


@router.post("/{workspace_id}/patches/reject-all")
def reject_all_workspace_patches(
    workspace_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reject all pending patches for a workspace."""
    _get_active_workspace_path(db, current_user.id, workspace_id)
    count = reject_all_patches(db, workspace_id, current_user.id)
    if count > 0:
        _notify_patch_event(db, workspace_id, background_tasks)
    return {"message": f"Rejected {count} patches"}


@router.post("/{workspace_id}/patches/{patch_id}/undo")
def undo_workspace_patch(
    workspace_id: str,
    patch_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owned_patch(db, workspace_id, patch_id, current_user.id)
    patch = undo_patch(db, patch_id, current_user.id)
    _notify_patch_event(db, workspace_id, background_tasks)
    return {"message": "Patch undone successfully", "patch": patch}


