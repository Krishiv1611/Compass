"""
Compass File Tools — Read, write, and edit files.

Includes change tracking hooks so the TUI can display diffs and support undo.
"""

import os
from langchain_core.tools import tool


# ─── Global Change Tracker Hook ────────────────────────────────────────────────
# Set by the TUI at startup to enable file change tracking.
# When None, tracking is disabled (e.g., in tests or single-shot mode).
_change_tracker = None


def set_change_tracker(tracker):
    """Set the global change tracker (called by TUI at startup)."""
    global _change_tracker
    _change_tracker = tracker


from langchain_core.runnables.config import RunnableConfig
from agent.tools.utils import get_workspace_for_tool, resolve_workspace_path

def _append_to_patch(workspace_id: str, run_id: str | None, change: dict):
    from backend.db import SessionLocal
    from backend.models.patch import WorkspacePatch
    from backend.services.patch_manager import create_patch
    
    db = SessionLocal()
    try:
        if run_id:
            patch = db.query(WorkspacePatch).filter(
                WorkspacePatch.run_id == run_id, 
                WorkspacePatch.status == "pending"
            ).first()
        else:
            patch = None
            
        if patch:
            patch.changes = patch.changes + [change]
            db.commit()
        else:
            create_patch(db, workspace_id, run_id, [change])
    finally:
        db.close()

@tool
def read_file(path: str, offset: int = 1, limit: int | None = None, config: RunnableConfig = None) -> str:
    """Read file contents with line numbers. Binary files rejected.

    Args:
        path: Path to the file to read.
        offset: The line number to start reading from (1-indexed). Defaults to 1.
        limit: The maximum number of lines to read. Defaults to reading the whole file.
    """
    try:
        workspace = get_workspace_for_tool(config)
        path = resolve_workspace_path(workspace, path)
    except PermissionError as e:
        return str(e)
        
    if not os.path.exists(path):
        return f"Error: File not found: {path}"
    if not os.path.isfile(path):
        return f"Error: Path is not a file: {path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        return f"Error: Binary file or unknown encoding. Not reading: {path}"
    except Exception as e:
        return f"Error reading file: {e}"
    start_idx = max(0, offset - 1)
    end_idx = len(lines) if limit is None else min(len(lines), start_idx + limit)
    if start_idx >= len(lines) and len(lines) > 0:
        return f"Error: Offset {offset} is beyond file length {len(lines)}"
    result_lines = [
        f"Showing lines {start_idx + 1} to {end_idx} of {len(lines)} in {path}:\n"
    ]
    for i in range(start_idx, end_idx):
        line_num = i + 1
        result_lines.append(f"{line_num:4d}| {lines[i].strip('\\n')}")
    return "\n".join(result_lines)


@tool
def write_to_file(path: str, content: str, config: RunnableConfig = None):
    """Write content to a file. Overwrite existing file
    Args:
        path: Path to the file to write to.
        content: The content to write to the file.
    """
    try:
        workspace = get_workspace_for_tool(config)
        path = resolve_workspace_path(workspace, path)
    except PermissionError as e:
        return str(e)

    # Snapshot before write for change tracking
    old_content = None
    if _change_tracker is not None:
        old_content = _change_tracker.snapshot_before_write(path)

    cloud_mode = os.environ.get("COMPASS_CLOUD_MODE", "false").lower() == "true"
    safe_mode = config.get("configurable", {}).get("safe_mode", False)
    
    if cloud_mode or safe_mode:
        _append_to_patch(
            workspace_id=workspace.id,
            run_id=config.get("configurable", {}).get("run_id"),
            change={
                "type": "create" if not os.path.exists(path) else "edit",
                "path": os.path.relpath(path, workspace.storage_path),
                "content": content
            }
        )
        return f"Proposed write to {path} (pending review in Safe Mode)"

    try:
        # Create parent directories if they don't exist
        parent_dir = os.path.dirname(os.path.abspath(path))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        if os.path.exists(path) and not os.path.isfile(path):
            return f"Error: Path exists but is not a file: {path}"

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        return f"Error writing to file: {e}"

    # Record change after successful write
    if _change_tracker is not None and old_content is not None:
        _change_tracker.record_change(path, old_content, content, "write_to_file")

    return f"Successfully wrote {len(content)} characters to {path}"


@tool
def edit_file(path: str, old_content: str, new_content: str, config: RunnableConfig = None) -> str:
    """Replace a specific block of text in a file.

    The old_content must appear EXACTLY once in the file (including whitespace
    and indentation). It will be replaced with new_content.

    To insert new lines, include surrounding context in old_content and add
    the new lines in new_content. To delete lines, set new_content to "".

    Args:
        path: Path to the file to edit.
        old_content: The exact existing text to find (must be unique in the file).
        new_content: The text to replace it with.
    """
    try:
        workspace = get_workspace_for_tool(config)
        path = resolve_workspace_path(workspace, path)
    except PermissionError as e:
        return str(e)
        
    if not os.path.exists(path):
        return f"Error: File not found: {path}"
    if not os.path.isfile(path):
        return f"Error: Path is not a file: {path}"

    try:
        with open(path, "r", encoding="utf-8") as f:
            file_content = f.read()
    except UnicodeDecodeError:
        return f"Error: Binary file or unknown encoding: {path}"
    except Exception as e:
        return f"Error reading file: {e}"

    count = file_content.count(old_content)
    if count == 0:
        return (
            f"Error: old_content not found in {path}. "
            "Make sure it matches the file exactly, including whitespace."
        )
    if count > 1:
        return (
            f"Error: old_content appears {count} times in {path}. "
            "Include more surrounding context to make it unique."
        )

    # Snapshot before edit for change tracking
    if _change_tracker is not None:
        _change_tracker.snapshot_before_write(path)

    updated_content = file_content.replace(old_content, new_content, 1)

    cloud_mode = os.environ.get("COMPASS_CLOUD_MODE", "false").lower() == "true"
    safe_mode = config.get("configurable", {}).get("safe_mode", False)
    
    if cloud_mode or safe_mode:
        _append_to_patch(
            workspace_id=workspace.id,
            run_id=config.get("configurable", {}).get("run_id"),
            change={
                "type": "edit",
                "path": os.path.relpath(path, workspace.storage_path),
                "content": updated_content
            }
        )
        return f"Proposed edit to {path} (pending review in Safe Mode)"

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(updated_content)
    except Exception as e:
        return f"Error writing file: {e}"

    # Record change after successful edit
    if _change_tracker is not None:
        _change_tracker.record_change(path, file_content, updated_content, "edit_file")

    old_lines = old_content.count("\n") + 1
    new_lines = new_content.count("\n") + 1
    return (
        f"Successfully edited {path}: "
        f"replaced {old_lines} lines with {new_lines} lines."
    )
