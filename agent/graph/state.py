"""
Compass Agent State — LangGraph state definition.

All fields used by the four-agent architecture:
  Planner → Executor → Loop Recovery → Summarizer
"""

from typing import Annotated, TypedDict, Literal

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Shared state for all agent nodes in the graph."""

    # ── Core ─────────────────────────────────────────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages]
    turn_count: int
    summary: str
    mode: Literal["normal", "plan", "fast", "goal"]

    # ── Planner ──────────────────────────────────────────────────────────────
    plan: str  # Step-by-step plan from the planner agent
    current_step: int  # Which plan step the executor is working on

    # ── Executor ─────────────────────────────────────────────────────────────
    is_done: bool  # True when executor produces final answer (no tool calls)
    pending_tool_calls: list[dict]  # Current tool calls from model response
    approval_status: str | None  # "approved" or "denied"
    approved_operations: list[str]  # Cache of auto-approved commands/edits
    token_usage: dict  # Token counts from usage_metadata

    # ── Loop Recovery ────────────────────────────────────────────────────────
    loop_detected: bool  # Set by loop detector in call_model
    loop_count: int  # Consecutive loop detections (hard break at 3)
    recovery_guidance: str  # Guidance message from the loop recovery agent

    # ── Skills ───────────────────────────────────────────────────────────────
    active_skill: dict | None  # {"name": "code-review", "arguments": "src/"} or None
    skill_result: dict | None  # Result from sub-agent execution, or None

    # ── Guardrails ────────────────────────────────────────────────────────
    guardrails_input_result: dict | None  # {safe: bool, reason: str | None}
    guardrails_output_result: dict | None  # {safe: bool, sanitized: str | None}

    # ── HITL (Human-in-the-Loop) ─────────────────────────────────────────
    hitl_session_approvals: list[str]  # Patterns auto-approved via "Always Yes"
    hitl_skip_count: int  # Number of skipped actions this session
