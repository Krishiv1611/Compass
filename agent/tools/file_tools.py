"""
Compass File Tools — Read, write, and edit files.

Includes change tracking hooks so the TUI can display diffs and support undo.
"""

import ast
import os
from pathlib import Path
from langchain_core.tools import tool


def _format_relative_path(workspace, path: str | Path) -> str:
    try:
        return Path(path).resolve().relative_to(Path(workspace.root).resolve()).as_posix()
    except Exception:
        return str(path).replace("\\", "/")


def _check_python_syntax(path: str, content: str) -> str:
    if str(path).lower().endswith(".py"):
        try:
            ast.parse(content.encode("utf-8-sig").decode("utf-8-sig"), filename=str(path))
        except SyntaxError as e:
            return f"\nWarning: Python SyntaxError at line {e.lineno}: {e.msg}"
        except Exception:
            pass
    return ""


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


def _review_mode(config: RunnableConfig | None) -> bool:
    configurable = (config or {}).get("configurable", {})
    return (
        os.environ.get("COMPASS_CLOUD_MODE", "false").lower() == "true"
        or bool(configurable.get("safe_mode", False))
    )


def _pending_overlay(workspace, path: str, config: RunnableConfig | None):
    if not _review_mode(config) or not workspace.workspace_id:
        return None
    from backend.db import SessionLocal
    from backend.services.patch_manager import get_pending_file_overlay

    relative_path = os.path.relpath(path, workspace.root)
    run_id = (config or {}).get("configurable", {}).get("run_id")
    db = SessionLocal()
    try:
        return get_pending_file_overlay(
            db,
            workspace.workspace_id,
            run_id,
            relative_path,
        )
    finally:
        db.close()


def _append_to_patch(workspace_id: str, run_id: str | None, change: dict):
    from backend.db import SessionLocal
    from backend.services.patch_manager import append_patch_change
    
    db = SessionLocal()
    try:
        return append_patch_change(db, workspace_id, run_id, change)
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
        
    overlay = _pending_overlay(workspace, path, config)
    if overlay is not None:
        exists, content = overlay
        if not exists:
            return f"Error: File not found: {path}"
        lines = content.splitlines(keepends=True)
    else:
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
    rel_display = _format_relative_path(workspace, path)
    result_lines = [
        f"Showing lines {start_idx + 1} to {end_idx} of {len(lines)} in {rel_display}:\n"
    ]
    for i in range(start_idx, end_idx):
        line_num = i + 1
        line_text = lines[i].rstrip("\r\n")
        result_lines.append(f"{line_num:4d}| {line_text}")
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

    if _review_mode(config):
        if not workspace.workspace_id:
            return "Error: Safe Mode requires a persisted workspace."
        overlay = _pending_overlay(workspace, path, config)
        exists = overlay[0] if overlay is not None else os.path.exists(path)
        patch = _append_to_patch(
            workspace_id=workspace.workspace_id,
            run_id=(config or {}).get("configurable", {}).get("run_id"),
            change={
                "type": "edit" if exists else "create",
                "path": os.path.relpath(path, workspace.root),
                "content": content
            }
        )
        rel_display = _format_relative_path(workspace, path)
        return (
            f"Proposed write to {rel_display} (pending review in Safe Mode, "
            f"patch {patch.id})"
        )

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

    rel_display = _format_relative_path(workspace, path)
    syntax_warning = _check_python_syntax(path, content)
    return f"Successfully wrote {len(content)} characters to {rel_display}{syntax_warning}"


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
        
    overlay = _pending_overlay(workspace, path, config)
    if overlay is not None:
        exists, file_content = overlay
        if not exists:
            return f"Error: File not found: {path}"
    else:
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

    if _review_mode(config):
        if not workspace.workspace_id:
            return "Error: Safe Mode requires a persisted workspace."
        patch = _append_to_patch(
            workspace_id=workspace.workspace_id,
            run_id=(config or {}).get("configurable", {}).get("run_id"),
            change={
                "type": "edit",
                "path": os.path.relpath(path, workspace.root),
                "content": updated_content
            }
        )
        rel_display = _format_relative_path(workspace, path)
        return (
            f"Proposed edit to {rel_display} (pending review in Safe Mode, "
            f"patch {patch.id})"
        )

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
    rel_display = _format_relative_path(workspace, path)
    syntax_warning = _check_python_syntax(path, updated_content)
    return (
        f"Successfully edited {rel_display}: "
        f"replaced {old_lines} lines with {new_lines} lines.{syntax_warning}"
    )
