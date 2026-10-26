"""
Decision engine for tool safety and approval, and path validators.
"""

import json
from pathlib import Path
from agent.config import settings

_SAFE_TOOL_NAMES = {
    "read_file", "list_dir", "find_files", "grep_search", "codebase_search",
    "web_search",
}


def configured_blocked_patterns() -> list[str]:
    """Return non-empty command patterns configured by the user."""
    value = settings.get("safety.blocked_commands", "")
    if not isinstance(value, str):
        return []
    return [item.strip() for item in value.replace("\n", ",").split(",") if item.strip()]


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
    if not settings.get("hitl.enabled", True):
        return False

    safety_mode = settings.get("safety.mode", "auto")
    if safety_mode == "yolo" or settings.get("fast_mode", False):
        return False

    if safety_mode == "strict":
        return True

    risk = "safe" if tool_name in _SAFE_TOOL_NAMES else "approval"

    if risk == "safe":
        return not settings.get("hitl.auto_approve_safe", True)

    # 2. Check Cache
    call_pattern = get_call_pattern(tool_name, tool_args)
    if call_pattern in approved_operations:
        return False

    # Default: risky tool, not cached, not yolo -> requires approval
    return True
