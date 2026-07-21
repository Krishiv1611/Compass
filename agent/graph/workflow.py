"""
Compass Agent Workflow â€” LangGraph StateGraph assembly.

Graph flow:
    START â†’ guardrails_input â†’ route:
        [blocked] â†’ END
        [safe]    â†’ planner / executor / direct_chat
                    â†’ executor â†’ check_safety (HITL) â†’ tools â†’ executor
                    â†’ loop_recovery â†’ executor
                    â†’ guardrails_output â†’ END
"""

import os

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END, START
from agent.graph.remote_tool_node import RemoteToolNode
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from agent.tools.memory_tool import _store as memory_store
from agent.graph.tools_registry import ALL_TOOLS

from agent.graph.state import AgentState
from agent.graph.nodes import (
    planner_node,
    plan_approval_node,
    call_model,
    loop_recovery_node,
    summary_node,
    check_safety_node,
    direct_chat_node,
    guardrails_input_node,
    guardrails_output_node,
    evaluator_node,
    clarifier_node,
    context_injector_node,
    title_generator_node,
    linter_node,
)
from agent.telemetry import configure_tracing

# Enable LangSmith tracing if configured
configure_tracing()
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


async def _route_after_executor(state: AgentState) -> str:
    """
    Route after the executor node.

    Priority order:
      1. Loop detected (and under recovery limit) â†’ loop_recovery
      2. Has tool calls (normal flow)              â†’ check_safety
      3. Done + long conversation                  â†’ summary_node
      4. Done                                      â†’ guardrails_output
    """
    if state.get("turn_count", 0) >= state.get("max_turns", 25):
        return "guardrails_output"
    if state.get("total_tokens_used", 0) >= state.get("token_budget", 50000):
        return "guardrails_output"

    # ── 1. Loop recovery & Hard Loop Escalation ────────────────────────────────
    if state.get("loop_detected", False):
        loop_count = state.get("loop_count", 0)
        if loop_count >= 2:
            return "clarifier"
        return "loop_recovery"

    # ── 2. Normal tool execution ───────────────────────────────────────────────
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        if not state.get("loop_detected", False):
            return "check_safety"

    # ── 3. Done — route to evaluator before ending ──────────────────────────────
    return "evaluator"


async def _route_after_linter(state: AgentState) -> str:
    """Context Compaction Check before returning to executor"""
    if len(state.get("messages", [])) > _SUMMARIZE_AFTER:
        return "summary_node"
    return "executor"


async def _route_after_evaluator(state: AgentState) -> str:
    """Route after evaluator node."""
    if not state.get("is_done", True):
        return "executor"
    return "guardrails_output"


async def _route_after_safety(state: AgentState) -> str:
    """Route after check_safety node. Denied and skipped go back to executor."""
    if state.get("approval_status") in ("denied", "skipped"):
        return "executor"
    return "tools"


async def _route_after_planner(state: AgentState) -> str:
    """Route after planner: skill_manager if a skill is active, plan_approval if mode is plan, else executor."""
    if state.get("active_skill"):
        return "skill_manager"
    if state.get("mode") == "plan":
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


async def _route_after_guardrails_input(state: AgentState) -> str:
    """Route after guardrails_input. If blocked, go to END. Otherwise, route by intent."""
    res = state.get("guardrails_input_result")
    if res and not res.get("safe", True):
        return END

    messages = state.get("messages", [])

    if len(messages) == 1:
        return "title_generator"

    # ── Safe: route by mode and intent (merged from _route_start) ────────────
    if state.get("mode") == "plan":
        return "context_injector"

    if not messages:
        return "executor"

    last_msg = messages[-1].content.lower()

    # If there is a plan or an ongoing workflow, always route to executor
    if state.get("plan") or state.get("pending_tool_calls"):
        return "executor"

    chat_keywords = [
        "hi", "hello", "hey", "who are you", "what can you do",
        "thanks", "thank you", "goodbye", "bye",
    ]
    if (
        any(last_msg.strip().startswith(kw) for kw in chat_keywords)
        and len(last_msg) < 50
    ):
        return "direct_chat"

    if len(messages) == 1:
        return "title_generator"

    # All non-simple tasks should get planned
    return "context_injector"


async def _route_after_title_generator(state: AgentState) -> str:
    if state.get("mode") == "plan":
        return "context_injector"
    return "executor"





# â”€â”€â”€ Build the graph â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
builder = StateGraph(AgentState)  # type: ignore

builder.add_node("guardrails_input", guardrails_input_node)
builder.add_node("guardrails_output", guardrails_output_node)
builder.add_node("context_injector", context_injector_node)
builder.add_node("planner", planner_node)
builder.add_node("plan_approval", plan_approval_node)
builder.add_node("clarifier", clarifier_node)
builder.add_node("skill_manager", _skill_manager)
builder.add_node("executor", call_model)
builder.add_node("direct_chat", direct_chat_node)
builder.add_node("check_safety", check_safety_node)
builder.add_node("tools", RemoteToolNode(ALL_TOOLS))
builder.add_node("loop_recovery", loop_recovery_node)
builder.add_node("evaluator", evaluator_node)
builder.add_node("summary_node", summary_node)
builder.add_node("linter_node", linter_node)
builder.add_node("title_generator", title_generator_node)

builder.add_edge(START, "guardrails_input")
builder.add_conditional_edges("guardrails_input", _route_after_guardrails_input)
builder.add_conditional_edges("planner", _route_after_planner)
builder.add_conditional_edges("plan_approval", _route_after_plan_approval)
builder.add_edge("skill_manager", "executor")
builder.add_conditional_edges("executor", _route_after_executor)
builder.add_conditional_edges("check_safety", _route_after_safety)
builder.add_edge("tools", "linter_node")
builder.add_conditional_edges("linter_node", _route_after_linter)
builder.add_edge("clarifier", "executor")
builder.add_edge("context_injector", "planner")
builder.add_edge("loop_recovery", "executor")
builder.add_conditional_edges("evaluator", _route_after_evaluator)
builder.add_edge("summary_node", "executor")
builder.add_conditional_edges("title_generator", _route_after_title_generator)
builder.add_edge("direct_chat", "guardrails_output")
builder.add_edge("guardrails_output", END)

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
                max_size=20,
                kwargs=connection_kwargs,
            )
            await _checkpointer_pool.open()
            
            pg_checkpointer = AsyncPostgresSaver(_checkpointer_pool)
            await pg_checkpointer.setup()
            
            _workflow = builder.compile(checkpointer=pg_checkpointer, **_compile_kwargs)
        except Exception as exc:
            # Fall back to no checkpointer if DB is unavailable
            print(f"[workflow] Warning: Persistence setup failed: {exc}")
            _workflow = builder.compile(**_compile_kwargs)
    else:
        # No DB configured â€” run without persistence
        _workflow = builder.compile(**_compile_kwargs)

    return _workflow


