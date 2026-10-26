"""Compatibility exports and per-run custom-tool resolution."""

from __future__ import annotations

import os
from agent.tools.registry import ToolRegistry, build_builtin_registry


TOOL_REGISTRY: ToolRegistry = build_builtin_registry()
BUILTIN_TOOLS = TOOL_REGISTRY.tools_for("tui")

# Preserve cloud-mode defense in depth for legacy callers that still consume the
# compatibility list directly. The policy-aware graph selects the web target.
if os.environ.get("COMPASS_CLOUD_MODE", "false").lower() == "true":
    BUILTIN_TOOLS = TOOL_REGISTRY.tools_for("web")

ALL_TOOLS = list(BUILTIN_TOOLS)
