"""
Compass Agent Workflow — LangGraph StateGraph assembly.

Four-agent graph:
    START → planner → executor → route:
                                   → tools → executor (loop)
                                   → loop_recovery → executor (retry)
                                   → summary_node → END
                                   → END
"""

import os

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from tools.memory_tool import _store as memory_store

from graph.state import AgentState
from graph.nodes import planner_node, call_model, loop_recovery_node, summary_node, check_safety_node
from tools.file_tools import read_file, write_to_file, edit_file
from tools.directory_tools import list_dir, find_files
from tools.search_tools import grep_search
from tools.web_tools import web_search
from tools.shell_tool import shell_execute
from tools.memory_tool import memory
from tools.todo_tool import todo
from rag.retriever import codebase_search

# Load environment variables
load_dotenv()

# ─── All tools the agent can use ────────────────────────────────────────────────
# IMPORTANT: This list must match the tools bound in nodes.py _executor_with_tools
ALL_TOOLS = [
    read_file, write_to_file, edit_file,   # file tools
    list_dir, find_files,                   # directory tools
    grep_search,                            # search tools
    codebase_search,                        # RAG semantic search
    web_search,                             # web tools
    shell_execute,                          # shell tool
    memory,                                 # memory tool
    todo,                                   # todo tool
]

# ─── Threshold for context compaction ───────────────────────────────────────────
_SUMMARIZE_AFTER = 10  # number of messages before triggering compaction


async def _route_after_executor(state: AgentState) -> str:
    """
    Route after the executor node.

    Priority order:
      1. Loop detected (and under recovery limit) → loop_recovery
      2. Has tool calls (normal flow)              → check_safety
      3. Done + long conversation                  → summary_node
      4. Done                                      → END
    """
    # ── 1. Loop recovery ─────────────────────────────────────────────────────
    if state.get("loop_detected", False):
        loop_count = state.get("loop_count", 0)
        if loop_count < 3:
            return "loop_recovery"
        # loop_count >= 3: fall through to END (hard break)

    # ── 2. Normal tool execution ─────────────────────────────────────────────
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        if not state.get("loop_detected", False):
            return "check_safety"

    # ── 3. Context compaction ────────────────────────────────────────────────
    if len(state["messages"]) > _SUMMARIZE_AFTER:
        return "summary_node"

    # ── 4. Done ──────────────────────────────────────────────────────────────
    return END

async def _route_after_safety(state: AgentState) -> str:
    """Route after check_safety node."""
    if state.get("approval_status") == "denied":
        return "executor"
    return "tools"

# ─── Build the graph ────────────────────────────────────────────────────────────
builder = StateGraph(AgentState)  # type: ignore

builder.add_node("planner", planner_node)
builder.add_node("executor", call_model)
builder.add_node("check_safety", check_safety_node)
builder.add_node("tools", ToolNode(ALL_TOOLS))
builder.add_node("loop_recovery", loop_recovery_node)
builder.add_node("summary_node", summary_node)

builder.add_edge(START, "planner")
builder.add_edge("planner", "executor")
builder.add_conditional_edges("executor", _route_after_executor)
builder.add_conditional_edges("check_safety", _route_after_safety)
builder.add_edge("tools", "executor")
builder.add_edge("loop_recovery", "executor")
builder.add_edge("summary_node", END)

# ─── Checkpointer + Store ──────────────────────────────────────────────────────
# Keep the connection alive for the lifetime of the process
DB_URI = os.environ.get("DB_URI")

# Build compile kwargs — include memory store if available
_compile_kwargs = {}
if memory_store is not None:
    _compile_kwargs["store"] = memory_store

if DB_URI:
    try:
        # from_conn_string() is a context manager — enter it manually
        # and keep the connection alive for the process lifetime
        _checkpointer_ctx = AsyncPostgresSaver.from_conn_string(DB_URI)
        checkpointer = _checkpointer_ctx.__enter__()
        checkpointer.setup()
        workflow = builder.compile(checkpointer=checkpointer, **_compile_kwargs)
    except Exception:
        # Fall back to no checkpointer if DB is unavailable
        workflow = builder.compile(**_compile_kwargs)
else:
    # No DB configured — run without persistence
    workflow = builder.compile(**_compile_kwargs)
