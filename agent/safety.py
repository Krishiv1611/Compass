"""
Decision engine for tool safety and approval, and path validators.
"""

import json
from pathlib import Path
from agent.config import settings

SAFE_TOOLS = {
    "read_file",
    "list_dir",
    "find_files",
    "grep_search",
    "codebase_search",
    "web_search",
    "memory",
    "todo",
}

RISKY_TOOLS = {"shell_execute", "write_to_file", "edit_file"}
HITL_ACTIONS = ["yes", "no", "always", "skip"]  # ordered for frontend display


def build_interrupt_payload(
    reason: str,
    tool_calls: list[dict] = None,
    guardrails_result: dict = None,
    description: str = "",
) -> dict:
    """Build a rich interrupt payload for the frontend."""
    return {
        "reason": reason,
        "tool_calls": tool_calls or [],
        "guardrails_result": guardrails_result,
        "description": description,
        "options": list(HITL_ACTIONS),
    }


def get_call_pattern(tool_name: str, tool_args: dict) -> str:
    """Serialize a tool call to a string for caching."""
    # Ensure stable sorting for the cache key
    return f"{tool_name}:{json.dumps(tool_args, sort_keys=True)}"


def requires_approval(
    tool_name: str, tool_args: dict, approved_operations: list[str]
) -> bool:
    """
    Determines if a tool call requires human approval based on policies and cache.
    """
    # 1. Check Policy
    safety_mode = settings.get("safety.mode", "auto")
    if safety_mode == "yolo":
        return False

    if tool_name in SAFE_TOOLS:
        return False

    # 2. Check Cache
    call_pattern = get_call_pattern(tool_name, tool_args)
    if call_pattern in approved_operations:
        return False

    # Default: risky tool, not cached, not yolo -> requires approval
    return True


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
        raise ValueError(
            f"Path traversal detected. Target path '{target_path}' is outside the workspace root."
        )

    # Block sensitive paths
    protected_dirs = {".git", ".env", ".compass"}
    # .env is a file, so we check parts exactly
    for part in target.parts:
        if part in protected_dirs:
            raise ValueError(
                f"Access to protected path '{part}' is restricted by safety policy."
            )

    return True
