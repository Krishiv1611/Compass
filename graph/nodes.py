"""
Compass Agent Nodes — LangGraph node functions.

Contains the call_model node that invokes the LLM with bound tools.
"""

from graph.state import AgentState
from tools.file_tools import read_file, write_to_file, edit_file
from model.get_llm import llm

# ─── Initialize model once at import time ───────────────────────────────────────
_model = llm()
_model_with_tools = _model.bind_tools([read_file, write_to_file, edit_file])


def call_model(state: AgentState):
    """Invoke the LLM with the current message history and bound tools."""
    response = _model_with_tools.invoke(state["messages"])
    return {
        "messages": [response],
        "turn_count": state.get("turn_count", 0) + 1,
    }
