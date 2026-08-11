"""Compatibility exports and per-run custom-tool resolution."""

from __future__ import annotations

import os
from pathlib import Path

from agent.tools.discovery import (
    load_approved_custom_tools,
    scan_custom_tool_files,
)
from agent.tools.registry import ToolRegistry, build_builtin_registry


TOOL_REGISTRY: ToolRegistry = build_builtin_registry()
BUILTIN_TOOLS = TOOL_REGISTRY.tools_for("tui")

# Preserve cloud-mode defense in depth for legacy callers that still consume the
# compatibility list directly. The policy-aware graph selects the web target.
if os.environ.get("COMPASS_CLOUD_MODE", "false").lower() == "true":
    BUILTIN_TOOLS = TOOL_REGISTRY.tools_for("web")

ALL_TOOLS = list(BUILTIN_TOOLS)


def tools_for_run(
    workspace_root: Path,
    approved_custom_tool_paths: set[str],
) -> list:
    """Return built-ins plus custom tools approved for this specific run."""

    candidates = scan_custom_tool_files(workspace_root)
    custom_tools = load_approved_custom_tools(
        candidates,
        approved_custom_tool_paths,
        reserved_names={tool.name for tool in BUILTIN_TOOLS},
    )
    return [*BUILTIN_TOOLS, *custom_tools]
