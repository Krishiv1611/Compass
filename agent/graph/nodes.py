"""
Compass Agent Nodes — LangGraph node functions.

Four-agent architecture:
  🧠 planner_node      — Decomposes user query into a step-by-step plan
  ⚡ call_model         — Executor: follows the plan, calls tools
  🔄 loop_recovery_node — Analyzes loops and provides corrective guidance
  📝 summary_node       — Compacts conversation context
"""

from agent.graph.state import AgentState
from agent.mcp import get_mcp_tools
from agent.llm import llm
from langchain_core.messages import SystemMessage, AIMessage
from agent.loop_detector import is_looping, get_loop_summary
from langchain_core.messages import BaseMessage as _BaseMessage
from langchain_core.runnables import RunnableConfig


# Note: Tools are dynamically bound in call_model() using ALL_TOOLS from workflow.py
# This ensures custom user tools and MCP tools are included at runtime.

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

## Registered Skills
These skills are available as specialized sub-agents. If the user's request clearly
matches one of these, add a line at the END of your plan:
  SKILL: <skill-name> <arguments>

The Skill Manager will automatically invoke the matching sub-agent.
If no skill matches, do NOT add a SKILL line — the executor will handle it normally.

Available skills:
{skill_list}
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


async def planner_node(state: AgentState, config: RunnableConfig):
    """
    🧠 Planner Agent — analyze the user's query and create a step-by-step plan.

    Runs once at the start of each user turn. The plan is stored in state
    and provided to the executor as context.
    """
    messages = state["messages"]

    # Build planner input: system prompt + the latest user message
    from skills import skill_registry

    skill_list = skill_registry.get_skill_names_descriptions()

    planner_messages: list[_BaseMessage] = [
        SystemMessage(
            content=PLANNER_SYSTEM_PROMPT.format(
                skill_list=skill_list if skill_list else "No skills registered."
            )
        ),
    ]

    # Include summary if available for context
    if state.get("summary"):
        planner_messages.append(
            SystemMessage(content=f"Conversation context:\n{state['summary']}")
        )

    # Add the conversation messages (planner needs context)
    planner_messages.extend(messages)
    
    api_key = config.get("configurable", {}).get("api_key")
    provider = config.get("configurable", {}).get("provider")
    model = config.get("configurable", {}).get("model")
    planner_model = llm("planner", api_key=api_key, provider=provider, model=model)

    response = await planner_model.ainvoke(planner_messages)

    plan_text = (
        response.content if isinstance(response.content, str) else str(response.content)
    )

    # Parse SKILL: directive from the plan
    active_skill = _parse_skill_directive(plan_text)

    update = {
        "plan": plan_text,
        "current_step": 0,
        "loop_count": 0,
        "loop_detected": False,
        "recovery_guidance": "",
        "messages": [response],
    }

    # Only update active_skill if planner found a directive.
    # We do NOT want to overwrite it with None if a slash command already set it!
    if active_skill:
        update["active_skill"] = active_skill

    return update


def _parse_skill_directive(plan_text: str) -> dict | None:
    """Extract 'SKILL: name args' from the plan text."""
    for line in plan_text.strip().splitlines():
        line = line.strip()
        if line.upper().startswith("SKILL:"):
            parts = line[6:].strip().split(maxsplit=1)
            if parts:
                return {
                    "name": parts[0],
                    "arguments": parts[1] if len(parts) > 1 else "",
                }
    return None


async def call_model(state: AgentState, config: RunnableConfig):
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

    workspace = config.get("configurable", {}).get("workspace_dir") or settings.get("workspace_dir")
    if workspace:
        context_parts.append(
            f"⚠️ CRITICAL INSTRUCTION: You must operate entirely within the user's workspace directory: `{workspace}`. "
            f"All files created, edited, and shell commands executed MUST be inside this absolute path unless explicitly requested otherwise."
        )

    if context_parts:
        context_parts.append(
            "IMPORTANT RULES:\n"
            "1. ALWAYS explain what you are doing before calling a tool.\n"
            "2. When a tool finishes and you have completed the user's task, you MUST send a final conversational message explaining what you did. NEVER finish silently without summarizing your work to the user."
        )
        context_msg = SystemMessage(content="\n\n".join(context_parts))
        messages = [context_msg] + messages

    # ── Dynamically load and bind all tools (built-in + custom + MCP) ──────
    mcp_tools = await get_mcp_tools()
    from agent.graph.tools_registry import ALL_TOOLS

    combined_tools = ALL_TOOLS + mcp_tools
    api_key = config.get("configurable", {}).get("api_key")
    provider = config.get("configurable", {}).get("provider")
    model = config.get("configurable", {}).get("model")
    executor_with_tools = llm("executor", api_key=api_key, provider=provider, model=model).bind_tools(combined_tools)

    # ── Check for Cooperative Cancellation ──────────────────────────────────
    run_id = config.get("configurable", {}).get("run_id")
    if run_id:
        from backend.services.run_manager import get_cancel_signal
        if get_cancel_signal(run_id).is_set():
            cancel_msg = AIMessage(content="Run cancelled by user.")
            return {
                "messages": [cancel_msg],
                "turn_count": state.get("turn_count", 0) + 1,
                "is_done": True,
                "token_usage": {},
                "pending_tool_calls": []
            }

    # ── Sanitize empty contents for Google GenAI compatibility ───────────────
    sanitized_messages = []
    for msg in messages:
        if (isinstance(msg.content, str) and not msg.content.strip()) or (isinstance(msg.content, list) and not msg.content):
            # Many models (especially Gemini) crash if content is completely empty
            # If it has tool calls, we keep it as is, but we need to ensure the content isn't strictly empty
            # wait, if it's an AIMessage with tool_calls, sometimes langchain handles it.
            # but to be safe, just set content to a single space if it's a string, or a text block.
            if hasattr(msg, "model_copy"):
                msg = msg.model_copy(update={"content": " "})
            else:
                msg = msg.copy(update={"content": " "})
        sanitized_messages.append(msg)
    messages = sanitized_messages

    # ── Invoke the executor LLM with tools ───────────────────────────────────
    response = await executor_with_tools.ainvoke(messages)

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
        if isinstance(usage, dict):
            token_usage = {
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }
        else:
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


async def loop_recovery_node(state: AgentState, config: RunnableConfig):
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

    recovery_messages: list[_BaseMessage] = [
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
    
    api_key = config.get("configurable", {}).get("api_key")
    provider = config.get("configurable", {}).get("provider")
    model = config.get("configurable", {}).get("model")
    recovery_model = llm("recovery", api_key=api_key, provider=provider, model=model)

    response = await recovery_model.ainvoke(recovery_messages)
    guidance = (
        response.content if isinstance(response.content, str) else str(response.content)
    )

    return {
        "recovery_guidance": guidance,
        "loop_count": loop_count,
        "loop_detected": False,  # Reset so executor can try again
    }


async def summary_node(state: AgentState, config: RunnableConfig):
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

    message_for_summary = state["messages"] + [HumanMessage(content=prompt)]

    api_key = config.get("configurable", {}).get("api_key")
    provider = config.get("configurable", {}).get("provider")
    model = config.get("configurable", {}).get("model")
    summarizer_model = llm("summarizer", api_key=api_key, provider=provider, model=model)

    response = summarizer_model.invoke(message_for_summary)

    # Keep the last 2 messages, delete everything else to free context
    messages_to_delete = state["messages"][:-2]
    return {
        "summary": response.content,
        "messages": [
            RemoveMessage(id=m.id) for m in messages_to_delete if m.id is not None
        ],
    }


async def check_safety_node(state: AgentState, config: RunnableConfig = None):
    """
    🛡️ Safety Node — intercepts risky tool calls and asks for user approval.
    """
    from langgraph.types import interrupt
    from agent.safety import requires_approval, get_call_pattern
    from langchain_core.messages import ToolMessage
    from agent.config import settings

    fast_mode = (state.get("mode") == "fast") or (config.get("configurable", {}).get("fast_mode", False) if config else False) or settings.get("fast_mode", False)
    if fast_mode:
        return {"approval_status": "approved"}

    last_message = state["messages"][-1]
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"approval_status": "approved"}

    approved_ops = state.get("approved_operations", [])
    if not isinstance(approved_ops, list):
        approved_ops = []

    risky_calls = []
    for tc in last_message.tool_calls:
        if requires_approval(tc["name"], tc.get("args", {}), approved_ops):
            risky_calls.append(tc)

    if not risky_calls:
        return {"approval_status": "approved"}

    # We have risky calls, interrupt the graph
    user_decision = interrupt(
        {"reason": "approval_required", "tool_calls": risky_calls}
    )

    # Check if we got a valid dict back from the interrupt
    if not isinstance(user_decision, dict):
        action = "deny"
    else:
        action = user_decision.get("action", "deny")

    if action in ("approve", "always"):
        # Update cache if requested
        new_approvals = list(approved_ops)
        if action == "always":
            for tc in risky_calls:
                pattern = get_call_pattern(tc["name"], tc.get("args", {}))
                if pattern not in new_approvals:
                    new_approvals.append(pattern)

        return {"approval_status": "approved", "approved_operations": new_approvals}
    else:
        # Denied
        # Generate ToolMessages for all pending calls to indicate failure
        tool_msgs = []
        for tc in last_message.tool_calls:
            tool_msgs.append(
                ToolMessage(
                    content="Error: User denied permission to execute this tool.",
                    tool_call_id=tc["id"],
                    name=tc["name"],
                    status="error",
                )
            )

        return {"approval_status": "denied", "messages": tool_msgs}


async def direct_chat_node(state: AgentState, config: RunnableConfig):
    """
    Direct Chat Agent — replies instantly without tools.
    Used for simple conversations to save tokens and latency.
    """
    messages = state["messages"]

    # We use a fast model alias (e.g., evaluator/chat) to slash latency
    api_key = config.get("configurable", {}).get("api_key")
    provider = config.get("configurable", {}).get("provider")
    model = config.get("configurable", {}).get("model")
    fast_model = llm("evaluator", api_key=api_key, provider=provider, model=model)

    system_msg = SystemMessage(
        content="You are Compass, a helpful AI coding assistant. Answer the user's question directly."
    )
    response = await fast_model.ainvoke([system_msg] + messages)

    token_usage = {}
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        usage = response.usage_metadata
        token_usage = {
            "prompt_tokens": getattr(usage, "input_tokens", 0),
            "completion_tokens": getattr(usage, "output_tokens", 0),
            "total_tokens": getattr(usage, "total_tokens", 0),
        }

    return {
        "messages": [response],
        "turn_count": state.get("turn_count", 0) + 1,
        "is_done": True,
        "token_usage": token_usage,
    }


import subprocess
import os

async def linter_node(state: AgentState, config: RunnableConfig):
    """
    Proactive Linter Agent — runs syntax checks if files were modified.
    Provides deterministic grounding for the evaluator.
    """
    messages = state["messages"]
    if not messages:
        return {}

    from langchain_core.messages import ToolMessage
    
    # Check if the last messages are ToolMessages from write/edit tools
    modifications = False
    for msg in reversed(messages):
        if not isinstance(msg, ToolMessage):
            break
        if msg.name in ("write_to_file", "edit_file"):
            modifications = True
            break

    if not modifications:
        return {}

    workspace_dir = config.get("configurable", {}).get("workspace_dir")
    if not workspace_dir or not os.path.isdir(workspace_dir):
        return {}

    errors = []
    # Check TypeScript
    if os.path.exists(os.path.join(workspace_dir, "tsconfig.json")):
        try:
            result = subprocess.run(
                ["npx", "tsc", "--noEmit"],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                errors.append(f"TypeScript Errors:\n{result.stdout}\n{result.stderr}")
        except Exception as e:
            pass

    # Check Python syntax
    try:
        result = subprocess.run(
            ["python", "-m", "compileall", "-q", "."],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            errors.append(f"Python Syntax Errors:\n{result.stderr}")
    except Exception as e:
        pass

    if errors:
        linter_msg = (
            "LINTER FAILED! Please fix the following syntax errors before continuing:\n\n" + 
            "\n".join(errors)
        )
        # We append a ToolMessage pretending to be a linter output, or just a SystemMessage
        # A SystemMessage is best to guide the executor on the next loop
        return {"messages": [SystemMessage(content=linter_msg[:2000])]}
    
    return {"messages": [SystemMessage(content="LINTER PASSED. No syntax errors detected.")]}

async def evaluator_node(state: AgentState, config: RunnableConfig):
    """
    Evaluator Agent — verifies if the task was completed successfully.
    """
    messages = state["messages"]
    
    if not state.get("plan"):
        return {}

    eval_prompt = (
        "You are the Evaluator Agent.\n"
        f"Original Plan:\n{state.get('plan')}\n\n"
        "Review the conversation above. Has the executor fully and successfully completed the task?\n"
        "If yes, reply with exactly 'SUCCESS'.\n"
        "If no, provide a concise list of what is missing or failed (e.g. missing variables, syntax errors) so the executor can self-correct."
    )

    eval_messages = messages[-10:] + [SystemMessage(content=eval_prompt)]

    api_key = config.get("configurable", {}).get("api_key")
    provider = config.get("configurable", {}).get("provider")
    model = config.get("configurable", {}).get("model")
    response = await llm("evaluator", api_key=api_key, provider=provider, model=model).ainvoke(eval_messages)
    
    content = str(response.content).strip()
    
    if content.upper().startswith("SUCCESS"):
        result = {"is_done": True, "evaluator_feedback": ""}
        last_msg = messages[-1]
        if getattr(last_msg, "type", "") == "ai" and not getattr(last_msg, "content", "").strip():
            result["messages"] = [AIMessage(content="I have completed the task successfully.")]
        return result
    
    return {
        "is_done": False, 
        "evaluator_feedback": content,
        "messages": [AIMessage(content=f"Evaluator Feedback: {content}")]
    }


async def clarifier_node(state: AgentState, config: RunnableConfig):
    """
    Clarifier Agent — asks the user for clarification via interrupt.
    """
    from langgraph.types import interrupt
    from langchain_core.messages import HumanMessage
    
    user_response = interrupt({
        "reason": "clarification_required",
        "description": "The agent needs clarification before proceeding.",
    })
    
    if isinstance(user_response, dict) and "action" in user_response:
        msg = user_response["action"]
    else:
        msg = str(user_response)
        
    return {
        "messages": [HumanMessage(content=f"User clarification: {msg}")],
        "is_done": False
    }


async def context_injector_node(state: AgentState, config: RunnableConfig):
    """
    Context Injector Agent — injects relevant codebase context before routing to planner.
    """
    workspace = config.get("configurable", {}).get("workspace_dir")
    messages = list(state.get("messages", []))
    if workspace and messages:
        try:
            import os
            tree = []
            for item in os.listdir(workspace):
                if item.startswith('.') or item == '__pycache__':
                    continue
                path = os.path.join(workspace, item)
                if os.path.isdir(path):
                    tree.append(f"{item}/")
                else:
                    tree.append(item)
            
            tree_str = ", ".join(sorted(tree))
            if tree_str:
                sys_msg = SystemMessage(
                    content=f"Background Context:\nThe current workspace is `{workspace}`. It contains: {tree_str}"
                )
                return {"messages": [sys_msg]}
        except Exception:
            pass
    return {}


async def _generate_title_async(session_id: str, content: str, api_key: str, provider: str | None = None, model: str | None = None):
    prompt = f"Generate a short 3-5 word title for a chat session starting with this message. Do not use quotes or punctuation.\n\nMessage: {content}"
    try:
        response = await llm("evaluator", api_key=api_key, provider=provider, model=model).ainvoke([SystemMessage(content=prompt)])
        title = response.content.strip().strip('"').strip("'")[:100]
        
        from backend.db import SessionLocal
        from backend.models.session import ChatSession
        db = SessionLocal()
        try:
            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if session and session.title in ["New Chat", None, ""]:
                session.title = title
                db.commit()
        finally:
            db.close()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to generate title: {e}")

async def title_generator_node(state: AgentState, config: RunnableConfig):
    """
    Title Generator Agent — asynchronously generates a title for the session.
    Fires off a background task to avoid blocking the user stream.
    """
    session_id = config.get("configurable", {}).get("session_id")
    if not session_id or not state.get("messages"):
        return {}

    first_msg = state["messages"][0]
    if getattr(first_msg, "type", "") != "human":
        return {}

    api_key = config.get("configurable", {}).get("api_key")
    provider = config.get("configurable", {}).get("provider")
    model = config.get("configurable", {}).get("model")
    
    # Fire and forget
    import asyncio
    asyncio.create_task(_generate_title_async(session_id, first_msg.content, api_key, provider, model))

    return {}


from agent.guardrails.engine import GuardrailsEngine
_guardrails_engine = GuardrailsEngine()

async def guardrails_input_node(state: AgentState, config: RunnableConfig = None):
    """Checks input safety using NeMo Guardrails."""
    from agent.config import settings
    fast_mode = (state.get("mode") == "fast") or (config.get("configurable", {}).get("fast_mode", False) if config else False) or settings.get("fast_mode", False)
    if fast_mode:
        return {"guardrails_input_result": {"safe": True}}

    messages = state["messages"]
    if not messages:
        return {}
    
    last_user_msg = ""
    for msg in reversed(messages):
        if msg.type == "human":
            last_user_msg = msg.content
            break
            
    if not last_user_msg:
        return {}

    result = await _guardrails_engine.check_input(last_user_msg)
    
    if not result.safe:
        return {
            "guardrails_input_result": {"safe": False, "reason": result.reason},
            "messages": [SystemMessage(content=f"Input blocked by guardrails: {result.reason}")]
        }
        
    return {"guardrails_input_result": {"safe": True}}

async def guardrails_output_node(state: AgentState, config: RunnableConfig = None):
    """Checks output safety before finalizing."""
    from agent.config import settings
    fast_mode = (state.get("mode") == "fast") or (config.get("configurable", {}).get("fast_mode", False) if config else False) or settings.get("fast_mode", False)
    if fast_mode:
        return {"is_done": True}

    messages = state["messages"]
    if not messages:
        return {"is_done": True}
        
    last_ai_msg = ""
    for msg in reversed(messages):
        if msg.type == "ai":
            last_ai_msg = str(msg.content)
            break
            
    if not last_ai_msg:
        return {"is_done": True}

    result = await _guardrails_engine.check_output(last_ai_msg)
    
    if not result.safe:
        return {
            "guardrails_output_result": {"safe": False, "reason": result.reason},
            "messages": [SystemMessage(content=f"Output sanitized by guardrails: {result.reason}")],
            "is_done": True
        }
        
    return {"guardrails_output_result": {"safe": True}, "is_done": True}
