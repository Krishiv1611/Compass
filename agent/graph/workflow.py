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
from agent.graph.remote_tool_node import RemoteToolNode
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from agent.tools.memory_tool import _store as memory_store

from agent.graph.state import AgentState
from agent.graph.nodes import (
    planner_node,
    call_model,
    loop_recovery_node,
    summary_node,
    check_safety_node,
    direct_chat_node,
)
from agent.model.get_llm import llm
from agent.tools.file_tools import read_file, write_to_file, edit_file
from agent.tools.directory_tools import list_dir, find_files
from agent.tools.search_tools import grep_search
from agent.tools.web_tools import web_search
from agent.tools.shell_tool import shell_execute
from agent.tools.memory_tool import memory
from agent.tools.todo_tool import todo
from agent.rag.retriever import codebase_search
from agent.tools.discovery import get_custom_tools

# Load environment variables
load_dotenv()

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
]

from agent.tools.create_skill_tool import create_skill

ALL_TOOLS.append(create_skill)  # skill creation tool

# ─── Conditionally Load Custom Tools ─────────────────────────────────────────────

custom_tools = get_custom_tools()
if custom_tools:
    print(f"[tools] Loaded {len(custom_tools)} custom tool(s).")
    ALL_TOOLS.extend(custom_tools)

# ─── Load Skills ───────────────────────────────────────────────────────────────

from agent.skills import skill_registry, SubAgentFactory, SkillManagerAgent

skill_count = skill_registry.load_all()
if skill_count:
    print(f"[skills] Loaded {skill_count} skill(s).")

_skill_factory = SubAgentFactory(ALL_TOOLS)
_skill_manager = SkillManagerAgent(_skill_factory, skill_registry)


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


async def _route_after_planner(state: AgentState) -> str:
    """Route after planner: skill_manager if a skill is active, else executor."""
    if state.get("active_skill"):
        return "skill_manager"
    return "executor"


async def _route_start(state: AgentState) -> str:
    """Route from START based on mode and intent."""
    if state.get("mode") == "plan":
        return "planner"

    # "normal" mode: fast intent routing
    messages = state["messages"]
    if not messages:
        return "executor"

    last_msg = messages[-1].content.lower()

    # Fast heuristic for chat vs task
    chat_keywords = [
        "hi",
        "hello",
        "hey",
        "who are you",
        "what can you do",
        "thanks",
        "thank you",
        "goodbye",
        "bye",
    ]
    if (
        any(last_msg.strip().startswith(kw) for kw in chat_keywords)
        and len(last_msg) < 50
    ):
        return "direct_chat"

    # Use LLM for intent routing if not obvious
    try:
        router_llm = llm("planner")  # Reuse planner model
        prompt = f"Is the following user message a simple chat/greeting (reply 'chat') or a task requiring codebase/tool access (reply 'task')? Message: '{last_msg}'"
        response = await router_llm.ainvoke(prompt)
        if (
            "chat" in response.content.lower()
            and "task" not in response.content.lower()
        ):
            return "direct_chat"
    except Exception:
        pass  # Fallback to executor if routing fails

    return "executor"


# ─── Build the graph ────────────────────────────────────────────────────────────
builder = StateGraph(AgentState)  # type: ignore

builder.add_node("planner", planner_node)
builder.add_node("skill_manager", _skill_manager)
builder.add_node("executor", call_model)
builder.add_node("direct_chat", direct_chat_node)
builder.add_node("check_safety", check_safety_node)
builder.add_node("tools", RemoteToolNode(ALL_TOOLS))
builder.add_node("loop_recovery", loop_recovery_node)
builder.add_node("summary_node", summary_node)

builder.add_conditional_edges(START, _route_start)
builder.add_conditional_edges("planner", _route_after_planner)
builder.add_edge("skill_manager", "executor")
builder.add_conditional_edges("executor", _route_after_executor)
builder.add_conditional_edges("check_safety", _route_after_safety)
builder.add_edge("tools", "executor")
builder.add_edge("loop_recovery", "executor")
builder.add_edge("summary_node", END)
builder.add_edge("direct_chat", END)

# ─── Async Workflow Factory ────────────────────────────────────────────────────
# AsyncPostgresSaver requires async initialization, so we expose an async factory
# function instead of a module-level `workflow` object.

DB_URI = os.environ.get("DB_URI")

_workflow = None  # cached after first call


async def get_workflow():
    """
    Build and return the compiled workflow (cached after first call).

    Uses AsyncPostgresSaver for persistence when DB_URI is configured.
    Falls back to no checkpointer if DB is unavailable.
    """
    global _workflow
    if _workflow is not None:
        return _workflow

    _compile_kwargs = {}
    if memory_store is not None:
        _compile_kwargs["store"] = memory_store

    if DB_URI:
        try:
            _checkpointer_ctx = AsyncPostgresSaver.from_conn_string(DB_URI)
            checkpointer = await _checkpointer_ctx.__aenter__()
            await checkpointer.setup()
            _workflow = builder.compile(checkpointer=checkpointer, **_compile_kwargs)
        except Exception:
            # Fall back to no checkpointer if DB is unavailable
            _workflow = builder.compile(**_compile_kwargs)
    else:
        # No DB configured — run without persistence
        _workflow = builder.compile(**_compile_kwargs)

    return _workflow
