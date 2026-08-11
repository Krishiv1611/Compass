"""Latency-first LangGraph workflow for Compass.

Short chat uses one direct node. Coding, planning, goal validation, skills,
subagents, tools, recovery, and approval are entered only when the request needs
them. Durable thread state uses a checkpointer and long-term memory uses a Store.
"""


import os

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from agent.tools.memory_tool import MEMORY_STORE as memory_store
from agent.graph.tool_node import CompassToolNode
from agent.graph.tools_registry import ALL_TOOLS, TOOL_REGISTRY

from agent.graph.state import AgentState
from agent.graph.nodes import (
    planner_node,
    plan_approval_node,
    call_model,
    loop_recovery_node,
    check_safety_node,
    direct_chat_node,
    evaluator_node,
    clarifier_node,
    context_injector_node,
    linter_node,
)

# Tools are now managed in agent.graph.tools_registry

# â”€â”€â”€ Load Skills â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

from agent.skills import skill_registry, SubAgentFactory, SkillManagerAgent

skill_count = skill_registry.load_all()
if skill_count:
    print(f"[skills] Loaded {skill_count} skill(s).")

_skill_factory = SubAgentFactory(ALL_TOOLS)
_skill_manager = SkillManagerAgent(_skill_factory, skill_registry)


# â”€â”€â”€ Threshold for context compaction â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_SUMMARIZE_AFTER = 10  # number of messages before triggering compaction


def _normalise_mode(state: AgentState) -> str:
    mode = state.get("mode", "edit")
    return {"normal": "edit", "fast": "ask"}.get(mode, mode)


def _turn_modified_files(state: AgentState) -> bool:
    for message in reversed(state.get("messages", [])):
        if getattr(message, "type", "") == "human":
            return False
        if (
            getattr(message, "type", "") == "tool"
            and getattr(message, "name", "") in ("write_to_file", "edit_file")
        ):
            return True
    return False


def _executor_scope_expanded(state: AgentState) -> bool:
    """Escalate an unplanned edit when proposed mutations become cross-cutting."""
    if _normalise_mode(state) != "edit" or state.get("plan"):
        return False
    messages = state.get("messages", [])
    if not messages:
        return False
    tool_calls = getattr(messages[-1], "tool_calls", []) or []
    if len(tool_calls) >= 4:
        return True

    mutating_tools = {"write_to_file", "edit_file", "delete_file", "move_file"}
    paths = {
        str(call.get("args", {}).get("path") or call.get("args", {}).get("file_path"))
        for call in tool_calls
        if call.get("name") in mutating_tools
        and (call.get("args", {}).get("path") or call.get("args", {}).get("file_path"))
    }
    return len(paths) >= 3

async def _route_after_executor(state: AgentState) -> str:
    """
    Route after the executor node.

    Priority order:
      1. Loop detected (and under recovery limit) â†’ loop_recovery
      2. Has tool calls (normal flow)              â†’ check_safety
      3. Done + long conversation                  â†’ summary_node
      4. Done                                      â†’ guardrails_output
    """

    # ── 1. Loop recovery & Hard Loop Escalation ────────────────────────────────
    mode = _normalise_mode(state)
    if mode == "goal" and state.get("loop_detected", False):
        loop_count = state.get("loop_count", 0)
        if loop_count >= 2:
            return "clarifier"
        return "loop_recovery"

    # ── 2. Normal tool execution ───────────────────────────────────────────────
    if _executor_scope_expanded(state):
        return "context_injector"

    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        if not state.get("loop_detected", False):
            return "check_safety"

    # ── 3. Done — route to evaluator before ending ──────────────────────────────
    if mode == "goal":
        if _turn_modified_files(state) and not state.get("syntax_checked", False):
            return "linter_node"
        return "evaluator"
    return END


async def _route_after_linter(state: AgentState) -> str:
    """Continue Goal validation after deterministic checks."""
    if state.get("syntax_check_failed", False):
        return "executor"
    return "evaluator"


async def _route_after_evaluator(state: AgentState) -> str:
    """Route after evaluator node."""
    if not state.get("is_done", True):
        return "executor"
    return END


async def _route_after_safety(state: AgentState) -> str:
    """Route after check_safety node. Denied and skipped go back to executor."""
    if state.get("approval_status") in ("denied", "skipped"):
        return "executor"
    return "tools"


async def _route_after_planner(state: AgentState) -> str:
    """Route after planner: skill_manager if a skill is active, plan_approval if mode is plan, else executor."""
    if state.get("active_skill"):
        return "skill_manager"
    if _normalise_mode(state) == "plan":
        return "plan_approval"
    return "executor"

async def _route_after_plan_approval(state: AgentState) -> str:
    """Route after plan approval based on the outcome."""
    if state.get("is_done"):
        return END
    
    # If the user rejected the plan, we injected an AIMessage into state["messages"]
    last_msg = state.get("messages", [])[-1].content
    if isinstance(last_msg, str) and last_msg.startswith("User rejected plan"):
        return "planner"
        
    return "executor"


def _needs_planning(text: str) -> bool:
    """Conservatively identify edits where planning protects result quality."""
    request = " ".join(text.lower().split())
    complex_markers = (
        "across the codebase",
        "across the project",
        "whole codebase",
        "entire project",
        "multiple services",
        "multi-file",
        "end-to-end",
        "architecture",
        "architectural",
        "database migration",
        "schema migration",
        "authentication system",
        "authorization system",
        "redesign",
        "restructure",
        "productionize",
        "breaking change",
        "backward compatibility",
    )
    if any(marker in request for marker in complex_markers):
        return True

    nonempty_lines = [line.strip() for line in text.splitlines() if line.strip()]
    listed_steps = sum(
        line.startswith(("- ", "* "))
        or (len(line) > 2 and line[0].isdigit() and line[1] in ".)")
        for line in nonempty_lines
    )
    if listed_steps >= 3:
        return True
    if len(request) >= 600:
        return True
    if len(request) >= 250 and request.count(" and ") >= 3:
        return True
    return False

def _route_start(state: AgentState) -> str:
    """Route directly to the smallest branch needed for this turn."""
    messages = state.get("messages", [])

    # ── Safe: route by mode and intent (merged from _route_start) ────────────
    mode = _normalise_mode(state)
    if mode in ("plan", "goal"):
        return "context_injector"

    if not messages:
        return "executor"

    last_msg = str(messages[-1].content).lower()

    chat_keywords = [
        "hi", "hello", "hey", "who are you", "what can you do",
        "thanks", "thank you", "goodbye", "bye",
    ]
    if (
        any(last_msg.strip().startswith(kw) for kw in chat_keywords)
        and len(last_msg) < 50
    ):
        return "direct_chat"

    if mode == "edit" and _needs_planning(last_msg):
        return "context_injector"

    return "executor"




# â”€â”€â”€ Build the graph â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
builder = StateGraph(AgentState)  # type: ignore

builder.add_node("context_injector", context_injector_node)
builder.add_node("planner", planner_node)
builder.add_node("plan_approval", plan_approval_node)
builder.add_node("clarifier", clarifier_node)
builder.add_node("skill_manager", _skill_manager)
builder.add_node("executor", call_model)
builder.add_node("direct_chat", direct_chat_node)
builder.add_node("check_safety", check_safety_node)
builder.add_node("tools", CompassToolNode(TOOL_REGISTRY))
builder.add_node("loop_recovery", loop_recovery_node)
builder.add_node("evaluator", evaluator_node)
builder.add_node("linter_node", linter_node)

builder.add_conditional_edges(START, _route_start)
builder.add_conditional_edges("planner", _route_after_planner)
builder.add_conditional_edges("plan_approval", _route_after_plan_approval)
builder.add_edge("skill_manager", END)
builder.add_conditional_edges("executor", _route_after_executor)
builder.add_conditional_edges("check_safety", _route_after_safety)
builder.add_edge("tools", "executor")
builder.add_conditional_edges("linter_node", _route_after_linter)
builder.add_edge("clarifier", "executor")
builder.add_edge("context_injector", "planner")
builder.add_edge("loop_recovery", "executor")
builder.add_conditional_edges("evaluator", _route_after_evaluator)
builder.add_edge("direct_chat", END)

# â”€â”€â”€ Async Workflow Factory â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# AsyncPostgresSaver requires async initialization, so we expose an async factory
# function instead of a module-level `workflow` object.

DB_URI = os.environ.get("DB_URI")

_workflow = None  # cached after first call
_checkpointer_pool = None  # keep pool alive to prevent closure


async def get_workflow():
    """
    Build and return the compiled workflow (cached after first call).

    Uses AsyncPostgresSaver for persistence when DB_URI is configured.
    Falls back to no checkpointer if DB is unavailable.
    """
    global _workflow, _checkpointer_pool
    if _workflow is not None:
        return _workflow

    _compile_kwargs = {}
    if memory_store is not None:
        _compile_kwargs["store"] = memory_store

    if DB_URI:
        try:
            from psycopg_pool import AsyncConnectionPool
            
            connection_kwargs = {
                "autocommit": True,
                "prepare_threshold": 0,
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 5,
            }
            
            _checkpointer_pool = AsyncConnectionPool(
                conninfo=DB_URI,
                min_size=1,
                max_size=20,
                kwargs=connection_kwargs,
                open=False,
                timeout=3,
                reconnect_timeout=3,
            )
            await _checkpointer_pool.open(wait=True, timeout=3)
            
            pg_checkpointer = AsyncPostgresSaver(_checkpointer_pool)
            await pg_checkpointer.setup()
            
            _workflow = builder.compile(checkpointer=pg_checkpointer, **_compile_kwargs)
        except Exception as exc:
            if _checkpointer_pool is not None:
                try:
                    await _checkpointer_pool.close(timeout=1)
                except Exception:
                    pass
                _checkpointer_pool = None
            # Fall back to no checkpointer if DB is unavailable
            print(f"[workflow] Warning: Persistence setup failed: {exc}")
            _workflow = builder.compile(**_compile_kwargs)
    else:
        # No DB configured â€” run without persistence
        _workflow = builder.compile(**_compile_kwargs)

    return _workflow


