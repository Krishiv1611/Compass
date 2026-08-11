"""Central list of built-in tools available to the Compass agent."""

from __future__ import annotations

import os
from pathlib import Path

from agent.rag.retriever import codebase_search
from agent.tools.create_skill_tool import create_skill
from agent.tools.directory_tools import find_files, list_dir
from agent.tools.discovery import (
    load_approved_custom_tools,
    scan_custom_tool_files,
)
from agent.tools.file_tools import edit_file, read_file, write_to_file
from agent.tools.memory_tool import memory
from agent.tools.search_tools import grep_search
from agent.tools.shell_tool import shell_execute
from agent.tools.todo_tool import todo
from agent.tools.web_tools import web_search


BUILTIN_TOOLS = [
    read_file,
    write_to_file,
    edit_file,
    list_dir,
    find_files,
    grep_search,
    codebase_search,
    web_search,
    shell_execute,
    memory,
    todo,
    create_skill,
]

# Internet deployments must never expose direct shell execution.
if os.environ.get("COMPASS_CLOUD_MODE", "false").lower() == "true":
    BUILTIN_TOOLS = [tool for tool in BUILTIN_TOOLS if tool is not shell_execute]

# Compatibility for existing graph callers. Importing this module loads built-ins
# only; custom repository Python is loaded per run through tools_for_run().
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
