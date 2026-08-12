import os
from pathlib import Path
from langchain_core.tools import tool
from langchain_core.runnables.config import RunnableConfig
from agent.tools.utils import get_workspace_for_tool, resolve_workspace_path


@tool
def list_dir(path: str = ".", max_depth: int = 2, config: RunnableConfig = None) -> str:
    """List directory contents recursively. Hidden files excluded.

    Args:
        path: Directory path. Defaults to current directory.
        max_depth: Recursion depth limit. Defaults to 2.
    """
    try:
        workspace = get_workspace_for_tool(config)
        path = resolve_workspace_path(workspace, path)
    except PermissionError as e:
        return str(e)
        
    if not os.path.exists(path):
        return f"Error: Directory not found: {path}"
    if not os.path.isdir(path):
        return f"Error: Not a directory: {path}"

    results = []

    def _walk(dir_path, depth):
        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            return
        for entry in entries:
            if entry.startswith("."):
                continue
            full = os.path.join(dir_path, entry)
            indent = "  " * depth
            if os.path.isdir(full):
                results.append(f"{indent}{entry}/")
                if depth < max_depth:
                    _walk(full, depth + 1)
            else:
                size = os.path.getsize(full)
                results.append(f"{indent}{entry}  ({size}B)")

    _walk(path, 0)
    header = f"Directory: {os.path.abspath(path)}\n"
    return header + "\n".join(results)


@tool
def find_files(
    pattern: str,
    path: str = ".",
    config: RunnableConfig = None,
) -> dict:
    """Find files matching a glob pattern (e.g. '**/*.py').

    Args:
        pattern: Glob pattern to search for.
        path: Workspace-relative directory to search.
    """
    workspace = get_workspace_for_tool(config)
    search_root = Path(resolve_workspace_path(workspace, path))
    matches = [
        candidate.relative_to(search_root).as_posix()
        for candidate in sorted(search_root.glob(pattern))
        if candidate.is_file()
        and not any(
            part.startswith(".")
            for part in candidate.relative_to(search_root).parts
        )
    ]
    return {
        "matches": matches[:100],
        "total": len(matches),
        "truncated": len(matches) > 100,
    }
