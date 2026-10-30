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

SAFE_COMMAND_PREFIXES = (
    "npm test",
    "pnpm test",
    "yarn test",
    "bun test",
    "vitest",
    "jest",
    "npm run test",
    "npm run build",
    "pnpm run build",
    "npm run lint",
    "pnpm run lint",
    "pytest",
    "python -m unittest",
    "python -m pytest",
    "git status",
    "git diff",
    "git log",
    "git branch",
    "npm install",
    "pnpm install",
    "yarn install",
    "tsc --noEmit",
    "cargo check",
    "cargo test",
    "go test",
    "echo ",
)


def is_safe_shell_command(command: str) -> bool:
    """Return True if command is recognized as safe build, test, lint, or inspection."""
    if not command or not isinstance(command, str):
        return False
    normalized = command.strip().lower()
    for prefix in SAFE_COMMAND_PREFIXES:
        p_lower = prefix.lower().strip()
        if normalized == p_lower or normalized.startswith(p_lower):
            # Guard against chained destructive commands
            if any(op in normalized for op in [";", "&&", "||", "|", "`", "$("]):
                return False
            return True
    return False


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

    if tool_name in ("execute_command", "shell_execute"):
        cmd = tool_args.get("command", "")
        if is_safe_shell_command(cmd):
            return not settings.get("hitl.auto_approve_safe", True)

    risk = "safe" if tool_name in _SAFE_TOOL_NAMES else "approval"

    if risk == "safe":
        return not settings.get("hitl.auto_approve_safe", True)

    # 2. Check Cache
    call_pattern = get_call_pattern(tool_name, tool_args)
    if call_pattern in approved_operations:
        return False

    # Default: risky tool, not cached, not yolo -> requires approval
    return True
