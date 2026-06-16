"""
Compass Agent Nodes — LangGraph node functions.

Four-agent architecture:
  🧠 planner_node      — Decomposes user query into a step-by-step plan
  ⚡ call_model         — Executor: follows the plan, calls tools
  🔄 loop_recovery_node — Analyzes loops and provides corrective guidance
  📝 summary_node       — Compacts conversation context
"""

from graph.state import AgentState
from tools.file_tools import read_file, write_to_file, edit_file
from tools.directory_tools import list_dir, find_files
from tools.search_tools import grep_search
from tools.web_tools import web_search
from tools.shell_tool import shell_execute
from tools.memory_tool import memory
from tools.todo_tool import todo
from rag.retriever import codebase_search
from model.get_llm import llm
from langchain_core.messages import SystemMessage, AIMessage
from context.loop_detector import is_looping, get_loop_summary


# ─── Four LLM Instances ─────────────────────────────────────────────────────────
_planner_model    = llm("planner")
_executor_model   = llm("executor")
_recovery_model   = llm("recovery")
_summarizer_model = llm("summarizer")

# Only the executor gets tools bound
_executor_with_tools = _executor_model.bind_tools([
    read_file, write_to_file, edit_file,   # file tools
    list_dir, find_files,                   # directory tools
    grep_search,                            # search tools
    codebase_search,                        # RAG semantic search
    web_search,                             # web tools
    shell_execute,                          # shell tool
    memory,                                 # memory tool
    todo,                                   # todo tool
])

# ─── System Prompts ──────────────────────────────────────────────────────────────

PLANNER_SYSTEM_PROMPT = """\
You are the **Planner Agent** for Compass, an AI coding assistant.

Your job is to analyze the user's request and create a clear, actionable step-by-step plan.

Rules:
1. Output a numbered list of steps (1, 2, 3, ...).
2. For each step, specify which tool should be used (if applicable).
3. Available tools: read_file, write_to_file, edit_file, list_dir, find_files, \
grep_search, codebase_search, web_search, shell_execute, memory, todo.
4. Do NOT execute anything — only plan.
5. Keep plans concise (typically 2-6 steps).
6. If the request is simple (e.g., a question), the plan can be just 1 step: "Respond directly."

Example:
User: "Read main.py and explain how the CLI works"
Plan:
1. Use `read_file` to read the contents of `main.py`.
2. Analyze the code structure, focusing on CLI argument parsing.
3. Respond with a clear explanation of how the CLI works.
"""

RECOVERY_SYSTEM_PROMPT = """\
You are the **Loop Recovery Agent** for Compass, an AI coding assistant.

The Executor agent is stuck in a loop — it keeps calling the same tool(s) with \
the same arguments and getting the same results.

Your job:
1. Analyze WHY the executor is stuck (e.g., file not found, wrong path, wrong approach).
2. Provide specific, actionable guidance on what to do differently.
3. Suggest alternative tools or approaches.
4. Keep your guidance concise (2-4 sentences max).

Do NOT call any tools. Just provide guidance text.
"""


# ─── Node Functions ──────────────────────────────────────────────────────────────

def planner_node(state: AgentState):
    """
    🧠 Planner Agent — analyze the user's query and create a step-by-step plan.

    Runs once at the start of each user turn. The plan is stored in state
    and provided to the executor as context.
    """
    messages = state["messages"]

    # Build planner input: system prompt + the latest user message
    planner_messages = [
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
    ]

    # Include summary if available for context
    if state.get("summary"):
        planner_messages.append(
            SystemMessage(content=f"Conversation context:\n{state['summary']}")
        )

    # Add the conversation messages (planner needs context)
    planner_messages.extend(messages)

    response = _planner_model.invoke(planner_messages)

    plan_text = response.content if isinstance(response.content, str) else str(response.content)

    return {
        "plan": plan_text,
        "current_step": 0,
        "loop_count": 0,
        "loop_detected": False,
        "recovery_guidance": "",
        "messages": [response],
    }


def call_model(state: AgentState):
    """
    ⚡ Executor Agent — follow the plan and call tools to accomplish the task.

    Receives the planner's plan as context. Populates all state fields
    including loop detection, token usage, and pending tool calls.
    """
    messages = list(state["messages"])

    # ── Build context from plan + recovery guidance ──────────────────────────
    context_parts = []

    if state.get("summary"):
        context_parts.append(f"Conversation Summary:\n{state['summary']}")

    plan = state.get("plan", "")
    if plan:
        current_step = state.get("current_step", 0)
        context_parts.append(
            f"Follow this plan:\n{plan}\n\n"
            f"You are currently on step {current_step + 1}. "
            f"Execute the next step(s) using the appropriate tools."
        )

    recovery = state.get("recovery_guidance", "")
    if recovery:
        context_parts.append(
            f"⚠️ IMPORTANT — Recovery guidance (you were stuck in a loop):\n{recovery}\n"
            f"Please try a DIFFERENT approach based on this guidance."
        )

    if context_parts:
        context_msg = SystemMessage(content="\n\n".join(context_parts))
        messages = [context_msg] + messages

    # ── Invoke the executor LLM with tools ───────────────────────────────────
    response = _executor_with_tools.invoke(messages)

    # ── Populate state fields ────────────────────────────────────────────────
    has_tool_calls = hasattr(response, "tool_calls") and bool(response.tool_calls)

    # Extract pending tool calls
    pending = []
    if has_tool_calls:
        for tc in response.tool_calls:
            pending.append({"name": tc["name"], "args": tc.get("args", {})})

    # Extract token usage if available
    token_usage = {}
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        usage = response.usage_metadata
        token_usage = {
            "prompt_tokens": getattr(usage, "input_tokens", 0),
            "completion_tokens": getattr(usage, "output_tokens", 0),
            "total_tokens": getattr(usage, "total_tokens", 0),
        }

    # ── Build state update ───────────────────────────────────────────────────
    new_state = {
        "messages": [response],
        "turn_count": state.get("turn_count", 0) + 1,
        "is_done": not has_tool_calls,
        "pending_tool_calls": pending,
        "approval_status": "auto",
        "token_usage": token_usage,
    }

    # Increment current_step when tool calls complete a cycle
    if has_tool_calls:
        new_state["current_step"] = state.get("current_step", 0) + 1

    # ── Loop detection ───────────────────────────────────────────────────────
    # We check AFTER adding the new response to detect patterns
    # But since messages haven't been committed yet, we check current state
    loop = is_looping(state, max_identical_calls=3)
    new_state["loop_detected"] = loop

    if loop:
        # Keep existing loop_count (will be incremented by loop_recovery_node)
        new_state["loop_count"] = state.get("loop_count", 0)

    return new_state


def loop_recovery_node(state: AgentState):
    """
    🔄 Loop Recovery Agent — analyze why the executor is stuck and provide guidance.

    Examines the repeated tool calls and their results, then provides specific
    actionable guidance on what different tools or approaches to try.

    Hard-breaks after 3 consecutive loop recoveries (sets is_done=True).
    """
    loop_count = state.get("loop_count", 0) + 1
    loop_summary = get_loop_summary(state)

    # ── Hard break after 3 recovery attempts ─────────────────────────────────
    if loop_count >= 3:
        return {
            "loop_count": loop_count,
            "loop_detected": False,
            "is_done": True,
            "recovery_guidance": "",
            "messages": [
                AIMessage(
                    content="I've been unable to make progress after multiple attempts. "
                            "Let me summarize what I tried and suggest how you might "
                            "approach this differently."
                )
            ],
        }

    # ── Build recovery analysis context ──────────────────────────────────────
    messages = state.get("messages", [])

    # Get last several messages for context (tool calls + results)
    recent_messages = messages[-8:] if len(messages) > 8 else messages

    recovery_messages = [
        SystemMessage(content=RECOVERY_SYSTEM_PROMPT),
        SystemMessage(
            content=(
                f"Plan the executor was following:\n{state.get('plan', 'No plan available')}\n\n"
                f"Loop analysis:\n{loop_summary}\n\n"
                f"This is recovery attempt {loop_count} of 3."
            )
        ),
    ]
    recovery_messages.extend(recent_messages)

    response = _recovery_model.invoke(recovery_messages)
    guidance = response.content if isinstance(response.content, str) else str(response.content)

    return {
        "recovery_guidance": guidance,
        "loop_count": loop_count,
        "loop_detected": False,  # Reset so executor can try again
    }


def summary_node(state: AgentState):
    """
    📝 Summarizer Agent — compact the conversation to free context space.

    Uses its own LLM instance to summarize the conversation, then removes
    old messages via RemoveMessage to keep context lean.
    """
    from langchain_core.messages import HumanMessage, RemoveMessage

    existing_summary = state.get("summary", "")

    if existing_summary:
        prompt = (
            f"Existing summary:\n{existing_summary}\n\n"
            "Extend the summary using the new conversation above."
        )
    else:
        prompt = "Summarise the conversation above."

    message_for_summary = state["messages"] + [
        HumanMessage(content=prompt)
    ]
    response = _summarizer_model.invoke(message_for_summary)

    # Keep the last 2 messages, delete everything else to free context
    messages_to_delete = state["messages"][:-2]
    return {
        "summary": response.content,
        "messages": [RemoveMessage(id=m.id) for m in messages_to_delete if m.id is not None],
    }
