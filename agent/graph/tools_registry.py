"""
Central registry for all tools available to the Compass Agent.
"""

from agent.tools.file_tools import read_file, write_to_file, edit_file
from agent.tools.directory_tools import list_dir, find_files
from agent.tools.search_tools import grep_search
from agent.tools.web_tools import web_search
from agent.tools.shell_tool import shell_execute
from agent.tools.memory_tool import memory
from agent.tools.todo_tool import todo
from agent.rag.retriever import codebase_search
from agent.tools.discovery import get_custom_tools
from agent.tools.create_skill_tool import create_skill

# ─── All tools the agent can use ────────────────────────────────────────────────
# IMPORTANT: This list must match the tools bound in nodes.py _executor_with_tools
ALL_TOOLS = [
    read_file,
    write_to_file,
    edit_file,  # file tools
    list_dir,
    find_files,  # directory tools
    grep_search,  # search tools
    codebase_search,  # RAG semantic search
    web_search,  # web tools
    shell_execute,  # shell tool
    memory,  # memory tool
    todo,  # todo tool
    create_skill, # skill creation tool
]

# ─── Conditionally Load Custom Tools ─────────────────────────────────────────────
custom_tools = get_custom_tools()
if custom_tools:
    print(f"[tools] Loaded {len(custom_tools)} custom tool(s).")
    ALL_TOOLS.extend(custom_tools)

import os
# If deployed on the internet, disable the shell tool to prevent Remote Code Execution
if os.environ.get("COMPASS_CLOUD_MODE", "false").lower() == "true":
    if shell_execute in ALL_TOOLS:
        ALL_TOOLS.remove(shell_execute)
        print("[tools] COMPASS_CLOUD_MODE is enabled. Shell tool disabled for safety.")
