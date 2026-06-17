"""
Safety validators for path boundaries and sensitive file access.
"""
import os
from pathlib import Path

def validate_path(target_path: str, workspace_root: str = ".") -> bool:
    """
    Validates that a target path is within the workspace and is not a protected file.
    Raises ValueError if invalid, otherwise returns True.
    """
    root = Path(workspace_root).resolve()
    target = Path(target_path)
    
    # Resolve the target relative to the current working directory, then resolve it
    if not target.is_absolute():
        target = (Path.cwd() / target).resolve()
    else:
        target = target.resolve()
        
    try:
        # Check for traversal outside workspace
        target.relative_to(root)
    except ValueError:
        raise ValueError(f"Path traversal detected. Target path '{target_path}' is outside the workspace root.")

    # Block sensitive paths
    protected_dirs = {".git", ".env", ".compass"}
    # .env is a file, so we check parts exactly
    for part in target.parts:
        if part in protected_dirs:
            raise ValueError(f"Access to protected path '{part}' is restricted by safety policy.")
            
    return True
