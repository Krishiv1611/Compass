"""Latency-first LangGraph workflow for Compass.

Short chat uses one direct node. Coding, planning, goal validation, skills,
subagents, tools, recovery, and approval are entered only when the request needs
them. Durable thread state uses a checkpointer and long-term memory uses a Store.
"""


import asyncio
import os

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END, START

from agent.persistence import close_postgres_pool, get_checkpointer
from agent.tools.memory_tool import MEMORY_STORE as memory_store
from agent.graph.tool_node import CompassToolNode
from agent.graph.tools_registry import ALL_TOOLS, TOOL_REGISTRY
from agent.graph.routing import needs_compaction, route_after_executor

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
    goal_limit_node,
    loop_limit_node,
    summary_node,
    verification_hooks_node,
    verification_hooks_finalize_node,
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

async def _route_after_linter(state: AgentState) -> str:
    """Continue Goal validation after deterministic checks."""
    if state.get("pending_tool_calls"):
        return "check_safety"
    if state.get("syntax_check_failed", False):
        return "executor"
    return "evaluator"


async def _route_after_evaluator(state: AgentState) -> str:
    """Route after evaluator node."""
    if needs_compaction(state):
        return "summary_node"
    if not state.get("is_done", True):
        return "executor"
    if not state.get("verification_hooks_scheduled"):
        from agent.hooks import changed_files_from_messages

        if changed_files_from_messages(state.get("messages", [])):
            return "verification_hooks"
    return END


async def _route_after_summary(state: AgentState) -> str:
    """Continue unfinished work after compaction; otherwise finish the turn."""

    return END if state.get("is_done", True) else "executor"


async def _route_after_safety(state: AgentState) -> str:
    """Route after check_safety node. Denied and skipped go back to executor."""
    if state.get("approval_status") in ("denied", "skipped"):
        messages = state.get("messages", [])
        if messages and str(getattr(messages[-1], "tool_call_id", "")).startswith("hook-"):
            return "verification_hooks_finalize"
        return "executor"
    return "tools"


async def _route_after_verification_hooks(state: AgentState) -> str:
    return "check_safety" if state.get("pending_tool_calls") else END


async def _route_after_tools(state: AgentState) -> str:
    messages = state.get("messages", [])
    trailing = []
    for message in reversed(messages):
        if getattr(message, "type", "") != "tool":
            break
        trailing.append(message)
    if trailing and all(
        str(getattr(message, "tool_call_id", "")).startswith("hook-")
        for message in trailing
    ):
        return "verification_hooks_finalize"
    return "executor"


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


async def _route_after_skill_manager(state: AgentState) -> str:
    """Invalid skill requests fall back to the main executor."""

    result = state.get("skill_result") or {}
    return "executor" if result.get("status") == "error" else END


def _needs_planning(text: str) -> bool:
    """Compatibility wrapper around the shared route diagnostic."""
    from agent.runtime.diagnostics import _needs_planning as needs_planning

    return needs_planning(text)


def _route_start(state: AgentState) -> str:
    """Route directly to the smallest branch needed for this turn."""
    from agent.runtime.diagnostics import route_report

    return str(route_report(state)["entry_node"])




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
builder.add_node("goal_limit", goal_limit_node)
builder.add_node("loop_limit", loop_limit_node)
builder.add_node("evaluator", evaluator_node)
builder.add_node("linter_node", linter_node)
builder.add_node("summary_node", summary_node)
builder.add_node("verification_hooks", verification_hooks_node)
builder.add_node("verification_hooks_finalize", verification_hooks_finalize_node)

builder.add_conditional_edges(START, _route_start)
builder.add_conditional_edges("planner", _route_after_planner)
builder.add_conditional_edges("plan_approval", _route_after_plan_approval)
builder.add_conditional_edges("skill_manager", _route_after_skill_manager)
builder.add_conditional_edges(
    "executor",
    route_after_executor,
    {
        "check_safety": "check_safety",
        "goal_limit": "goal_limit",
        "loop_recovery": "loop_recovery",
        "loop_limit": "loop_limit",
        "context_injector": "context_injector",
        "linter_node": "linter_node",
        "summary_node": "summary_node",
        "verification_hooks": "verification_hooks",
        "executor": "executor",
        "end": END,
    },
)
builder.add_conditional_edges("check_safety", _route_after_safety)
builder.add_conditional_edges("tools", _route_after_tools)
builder.add_conditional_edges("verification_hooks", _route_after_verification_hooks)
builder.add_edge("verification_hooks_finalize", END)
builder.add_conditional_edges("linter_node", _route_after_linter)
builder.add_edge("clarifier", "executor")
builder.add_edge("context_injector", "planner")
builder.add_edge("loop_recovery", "executor")
builder.add_edge("goal_limit", END)
builder.add_edge("loop_limit", END)
builder.add_conditional_edges("evaluator", _route_after_evaluator)
builder.add_conditional_edges("summary_node", _route_after_summary)
builder.add_edge("direct_chat", END)

# â”€â”€â”€ Async Workflow Factory â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# AsyncPostgresSaver requires async initialization, so we expose an async factory
# function instead of a module-level `workflow` object.

_workflow = None  # cached after first call
_workflow_durable = False
_workflow_lock = asyncio.Lock()


async def get_workflow(*, require_durable: bool = False):
    """
    Build and return the compiled workflow (cached after first call).

    Local calls may use process memory. Web calls require PostgreSQL durability.
    """
    global _workflow, _workflow_durable
    if _workflow is not None and (not require_durable or _workflow_durable):
        return _workflow

    async with _workflow_lock:
        if _workflow is not None and (
            not require_durable or _workflow_durable
        ):
            return _workflow

        db_uri = os.environ.get("DB_URI")
        try:
            checkpointer = await get_checkpointer(
                db_uri,
                require_durable=require_durable,
            )
        except Exception:
            # A failed durable initialization remains retryable on the next call.
            if require_durable:
                raise
            checkpointer = await get_checkpointer(None)

        compile_kwargs = {"checkpointer": checkpointer}
        if memory_store is not None:
            compile_kwargs["store"] = memory_store
        compiled = builder.compile(**compile_kwargs)
        durable = "postgres" in checkpointer.__class__.__module__

        # Do not cache a fallback caused by a configured-but-unavailable DB.
        if not db_uri or durable:
            _workflow = compiled
            _workflow_durable = durable
        return compiled


async def reset_workflow() -> None:
    """Clear cached workflow state and release PostgreSQL resources."""

    global _workflow, _workflow_durable
    async with _workflow_lock:
        _workflow = None
        _workflow_durable = False
        await close_postgres_pool()


