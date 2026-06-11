"""
Compass Agent Workflow — LangGraph StateGraph assembly.

Builds the agent graph:
    START → call_model → has tool calls? → YES → tools → call_model (loop)
                                         → NO  → END
"""

import os

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.postgres import PostgresSaver
from tools.memory_tool import _store as memory_store

from graph.state import AgentState
from graph.nodes import call_model, summary_node
from tools.file_tools import read_file, write_to_file, edit_file
from tools.directory_tools import list_dir, find_files
from tools.search_tools import grep_search
from tools.web_tools import web_search
from tools.shell_tool import shell_execute
from tools.memory_tool import memory
from tools.todo_tool import todo

# Load environment variables
load_dotenv()

# ─── All tools the agent can use ────────────────────────────────────────────────
# IMPORTANT: This list must match the tools bound in nodes.py call_model()
ALL_TOOLS = [
    read_file, write_to_file, edit_file,   # file tools
    list_dir, find_files,                   # directory tools
    grep_search,                            # search tools
    web_search,                             # web tools
    shell_execute,                          # shell tool
    memory,                                 # memory tool
    todo,                                   # todo tool
]

# ─── Threshold for context compaction ───────────────────────────────────────────
_SUMMARIZE_AFTER = 10  # number of messages before triggering compaction


def _route_after_model(state: AgentState) -> str:
    """Route after call_model: tools, summarize, or end."""
    last_message = state["messages"][-1]

    # If the model wants to call tools, go to tools node
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    # If conversation is getting long, compact it before ending
    if len(state["messages"]) > _SUMMARIZE_AFTER:
        return "summary_node"

    return END


# ─── Build the graph ────────────────────────────────────────────────────────────
builder = StateGraph(AgentState)  # type: ignore

builder.add_node("call_model", call_model)
builder.add_node("tools", ToolNode(ALL_TOOLS))
builder.add_node("summary_node", summary_node)

builder.add_edge(START, "call_model")
builder.add_conditional_edges("call_model", _route_after_model)
builder.add_edge("tools", "call_model")
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
        _checkpointer_ctx = PostgresSaver.from_conn_string(DB_URI)
        checkpointer = _checkpointer_ctx.__enter__()
        checkpointer.setup()
        workflow = builder.compile(checkpointer=checkpointer, **_compile_kwargs)
    except Exception:
        # Fall back to no checkpointer if DB is unavailable
        workflow = builder.compile(**_compile_kwargs)
else:
    # No DB configured — run without persistence
    workflow = builder.compile(**_compile_kwargs)
