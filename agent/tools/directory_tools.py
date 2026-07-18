import os
from langchain_core.tools import tool
from glob import glob
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
def find_files(pattern: str, config: RunnableConfig = None) -> str:
    """Find files matching a glob pattern (e.g. '**/*.py').

    Args:
        pattern: Glob pattern to search for.
    """
    workspace = get_workspace_for_tool(config)
    original_cwd = os.getcwd()
    os.chdir(workspace)
    try:
        matches = glob(pattern, recursive=True)
        matches = [
            f for f in matches if not any(p.startswith(".") for p in f.split(os.sep))
        ]

        if not matches:
            return "No files found."
        if len(matches) > 100:
            return f"Found {len(matches)} files (showing first 100):\n" + "\n".join(
                matches[:100]
            )
        return f"Found {len(matches)} files:\n" + "\n".join(matches)
    finally:
        os.chdir(original_cwd)

