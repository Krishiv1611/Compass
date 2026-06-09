"""
Compass Agent Workflow — LangGraph StateGraph assembly.

Builds the agent graph:
    START → call_model → has tool calls? → YES → tools → call_model (loop)
                                         → NO  → END
"""

import os

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.postgres import PostgresSaver

from graph.state import AgentState
from graph.nodes import call_model
from tools.file_tools import read_file, write_to_file, edit_file

# Load environment variables
load_dotenv()

# ─── All tools the agent can use ────────────────────────────────────────────────
# IMPORTANT: This list must match the tools bound in nodes.py call_model()
ALL_TOOLS = [read_file, write_to_file, edit_file]

# ─── Build the graph ────────────────────────────────────────────────────────────
builder = StateGraph(AgentState)  # type: ignore

builder.add_node("call_model", call_model)
builder.add_node("tools", ToolNode(ALL_TOOLS))

builder.add_edge(START, "call_model")
builder.add_conditional_edges("call_model", tools_condition)
builder.add_edge("tools", "call_model")

# ─── Checkpointer ──────────────────────────────────────────────────────────────
# Keep the connection alive for the lifetime of the process
DB_URI = os.environ.get("DB_URI")

if DB_URI:
    try:
        # from_conn_string() is a context manager — enter it manually
        # and keep the connection alive for the process lifetime
        _checkpointer_ctx = PostgresSaver.from_conn_string(DB_URI)
        checkpointer = _checkpointer_ctx.__enter__()
        checkpointer.setup()
        workflow = builder.compile(checkpointer=checkpointer)
    except Exception:
        # Fall back to no checkpointer if DB is unavailable
        workflow = builder.compile()
else:
    # No DB configured — run without persistence
    workflow = builder.compile()
