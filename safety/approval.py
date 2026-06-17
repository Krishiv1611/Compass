"""
Decision engine for tool safety and approval.
"""
import json
from config.settings import settings

SAFE_TOOLS = {
    "read_file", "list_dir", "find_files", "grep_search",
    "codebase_search", "web_search", "memory", "todo"
}

RISKY_TOOLS = {
    "shell_execute", "write_to_file", "edit_file"
}

def get_call_pattern(tool_name: str, tool_args: dict) -> str:
    """Serialize a tool call to a string for caching."""
    # Ensure stable sorting for the cache key
    return f"{tool_name}:{json.dumps(tool_args, sort_keys=True)}"

def requires_approval(tool_name: str, tool_args: dict, approved_operations: list[str]) -> bool:
    """
    Determines if a tool call requires human approval based on policies and cache.
    """
    # 1. Check Policy
    safety_mode = settings.get("safety_mode", "auto")
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
