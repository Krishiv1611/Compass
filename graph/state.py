"""
Compass Agent State — LangGraph state definition.

All fields used by the four-agent architecture:
  Planner → Executor → Loop Recovery → Summarizer
"""

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Shared state for all agent nodes in the graph."""

    # ── Core ─────────────────────────────────────────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages]
    turn_count: int
    summary: str

    # ── Planner ──────────────────────────────────────────────────────────────
    plan: str               # Step-by-step plan from the planner agent
    current_step: int       # Which plan step the executor is working on

    # ── Executor ─────────────────────────────────────────────────────────────
    is_done: bool                   # True when executor produces final answer (no tool calls)
    pending_tool_calls: list[dict]  # Current tool calls from model response
    approval_status: str | None     # "auto" for now — Phase 4 placeholder
    token_usage: dict               # Token counts from usage_metadata

    # ── Loop Recovery ────────────────────────────────────────────────────────
    loop_detected: bool     # Set by loop detector in call_model
    loop_count: int         # Consecutive loop detections (hard break at 3)
    recovery_guidance: str  # Guidance message from the loop recovery agent
