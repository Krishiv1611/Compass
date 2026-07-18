import os
from pathlib import Path
from langchain_core.runnables.config import RunnableConfig

def get_workspace_for_tool(config: RunnableConfig) -> Path:
    """Retrieve the isolated workspace directory based on the LangGraph config."""
    if not config or "configurable" not in config:
        return Path.cwd()
    
    workspace_dir = config["configurable"].get("workspace_dir")
    
    if workspace_dir:
        return Path(workspace_dir)
        
    return Path.cwd()

def resolve_workspace_path(workspace: Path, target_path: str) -> str:
    """Resolve a path relative to the workspace, ensuring it doesn't escape."""
    target_path = str(target_path).strip()
    
    base = workspace.resolve()
    
    # If the target path is already an absolute path and starts with the workspace path, use it directly
    try:
        if os.path.isabs(target_path) and Path(target_path).resolve().is_relative_to(base):
            return str(Path(target_path).resolve())
    except Exception:
        pass

    if os.path.isabs(target_path) and os.name == 'nt':
        # On windows, drop the drive letter if present and strip leading slashes
        drive, tail = os.path.splitdrive(target_path)
        target_path = tail.lstrip("\\/")
    elif os.path.isabs(target_path):
        target_path = target_path.lstrip(os.sep)
        
    target = (base / target_path).resolve()
    
    try:
        target.relative_to(base)
    except ValueError:
        raise PermissionError(f"Access denied: path '{target_path}' escapes the workspace directory.")
        
    return str(target)
