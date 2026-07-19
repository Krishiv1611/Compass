"""
Agent runner — async wrapper around the LangGraph agent workflow.

Provides both streaming and non-streaming interfaces for the FastAPI backend.
"""

import logging
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage

from agent.graph.workflow import get_workflow
from agent.telemetry import get_run_config

from backend.schemas.chat import StreamEvent, StreamEventType, ToolCallData

from langgraph.types import Command

logger = logging.getLogger(__name__)

async def run_agent_stream(
    user_message: str,
    thread_id: str,
    session_id: str,
    user_id: str,
    mode: str = "normal",
    resume_action: str | None = None,
    user_prefs: dict | None = None,
    run_id: str | None = None,
) -> AsyncGenerator[StreamEvent, None]:
    """
    Invoke the LangGraph agent and yield StreamEvent objects.

    Streams token-by-token output, tool calls, tool results, and a final done event.
    """


    workflow = await get_workflow()
    config = get_run_config(thread_id=thread_id)
    if "configurable" not in config:
        config["configurable"] = {}
    config["configurable"]["session_id"] = session_id
    config["configurable"]["user_id"] = user_id
    if run_id:
        config["configurable"]["run_id"] = run_id
    
    if user_prefs:
        if user_prefs.get("model"):
            config["configurable"]["model"] = user_prefs["model"]
            config["configurable"]["model_executor"] = user_prefs["model"]
            config["configurable"]["model_planner"] = user_prefs["model"]
        if user_prefs.get("llm_api_key"):
            config["configurable"]["api_key"] = user_prefs["llm_api_key"]
        elif user_prefs.get("api_key"):
            config["configurable"]["api_key"] = user_prefs["api_key"]
        if user_prefs.get("llm_provider"):
            config["configurable"]["provider"] = user_prefs["llm_provider"]
        if user_prefs.get("workspace_dir"):
            config["configurable"]["workspace_dir"] = user_prefs["workspace_dir"]
        if user_prefs.get("safe_mode") is not None:
            config["configurable"]["safe_mode"] = user_prefs["safe_mode"]
        if user_prefs.get("fast_mode") is not None:
            config["configurable"]["fast_mode"] = user_prefs["fast_mode"]
    
    if resume_action:
        input_msg = Command(resume={"action": resume_action})
    else:
        input_msg = {"messages": [HumanMessage(content=user_message)], "mode": mode}

    try:
        from langchain_core.messages import AIMessageChunk, ToolMessage
        async for chunk_type, payload in workflow.astream(
            input_msg, config=config, stream_mode=["messages", "updates"]
        ):
            if chunk_type == "messages":
                chunk, metadata = payload
                from langchain_core.messages import AIMessage
                if isinstance(chunk, (AIMessageChunk, AIMessage)):
                    if chunk.content:
                        content_str = ""
                        if isinstance(chunk.content, str):
                            content_str = chunk.content
                        elif isinstance(chunk.content, list):
                            content_str = "".join([
                                str(item.get("text", "")) for item in chunk.content if isinstance(item, dict) and "text" in item
                            ])
                        else:
                            content_str = str(chunk.content)

                        if content_str:
                            yield StreamEvent(
                                type=StreamEventType.TOKEN,
                                content=content_str,
                            )
                    if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                        for tc in chunk.tool_call_chunks:
                            if tc.get("name"):
                                args_val = tc.get("args", {})
                                if isinstance(args_val, str):
                                    import json
                                    try:
                                        args_val = json.loads(args_val) if args_val else {}
                                    except:
                                        args_val = {}
                                
                                yield StreamEvent(
                                    type=StreamEventType.TOOL_CALL,
                                    tool_call=ToolCallData(
                                        id=tc.get("id", ""),
                                        name=tc["name"],
                                        args=args_val,
                                    ),
                                )
            
            elif chunk_type == "updates":
                for node_name, node_output in payload.items():
                    if node_name == "planner":
                        plan_text = node_output.get("plan", "")
                        if plan_text:
                            yield StreamEvent(
                                type=StreamEventType.PLAN_CREATED,
                                content=plan_text,
                                node="planner",
                            )
                    elif node_name == "loop_recovery":
                        loop_count = node_output.get("loop_count", 0)
                        guidance = node_output.get("recovery_guidance", "")
                        yield StreamEvent(
                            type=StreamEventType.LOOP_DETECTED,
                            content=guidance or f"Loop detected, recovery attempt {loop_count}/3",
                            data={"loop_count": loop_count},
                            node="loop_recovery",
                        )
                    elif node_name == "tools":
                        # Tool execution results
                        tool_msgs = node_output.get("messages", [])
                        for msg in tool_msgs:
                            if isinstance(msg, ToolMessage):
                                yield StreamEvent(
                                    type=StreamEventType.TOOL_RESULT,
                                    tool_call_id=msg.tool_call_id,
                                    content=str(msg.content)[:500],
                                )
                    elif node_name == "linter_node":
                        yield StreamEvent(
                            type=StreamEventType.STATUS,
                            content="Running Linter...",
                        )
                    elif node_name == "evaluator":
                        yield StreamEvent(
                            type=StreamEventType.STATUS,
                            content="Evaluating Output...",
                        )

        # ── Done ──────────────────────────────────────────────────────────────
        # Check if the graph was interrupted
        state = await workflow.aget_state(config)
        interrupted = False
        if state.tasks:
            for task in state.tasks:
                if task.interrupts:
                    for interrupt_val in task.interrupts:
                        if hasattr(interrupt_val, "value") and isinstance(interrupt_val.value, dict):
                            if interrupt_val.value.get("reason") == "approval_required":
                                tool_calls = interrupt_val.value.get("tool_calls", [])
                                desc = interrupt_val.value.get("description", "Approval required")
                                # For simplicity, just send the first tool call or a summary
                                # We'll send it as a data payload
                                yield StreamEvent(
                                    type=StreamEventType.APPROVAL_REQUIRED,
                                    content=desc,
                                    data={"tool_calls": tool_calls}
                                )
                                interrupted = True
                                break
                    if interrupted:
                        break

        if not interrupted:
            yield StreamEvent(type=StreamEventType.DONE)

    except Exception as exc:
        error_msg = str(exc)
        logger.exception("Agent execution error")
        
        if "UnauthorizedResponseError" in error_msg or "User not found" in error_msg or "401" in error_msg:
            yield StreamEvent(
                type=StreamEventType.ERROR,
                content="Invalid LLM API Key. Please update your API key in Settings.",
            )
        else:
            yield StreamEvent(
                type=StreamEventType.ERROR,
                content=str(exc)[:500],
            )


async def run_agent_sync(
    user_message: str,
    thread_id: str,
    session_id: str,
    user_id: str,
    mode: str = "normal",
    user_prefs: dict | None = None,
) -> list[BaseMessage]:
    """
    Invoke the LangGraph agent and return all response messages (non-streaming).

    Returns the list of AI/tool messages produced during this turn.
    """


    workflow = await get_workflow()
    config = get_run_config(thread_id=thread_id)
    if "configurable" not in config:
        config["configurable"] = {}
    config["configurable"]["session_id"] = session_id
    config["configurable"]["user_id"] = user_id
    
    if user_prefs:
        if user_prefs.get("model"):
            config["configurable"]["model"] = user_prefs["model"]
            config["configurable"]["model_executor"] = user_prefs["model"]
            config["configurable"]["model_planner"] = user_prefs["model"]
        if user_prefs.get("llm_api_key"):
            config["configurable"]["api_key"] = user_prefs["llm_api_key"]
        elif user_prefs.get("api_key"):
            config["configurable"]["api_key"] = user_prefs["api_key"]
        if user_prefs.get("llm_provider"):
            config["configurable"]["provider"] = user_prefs["llm_provider"]
        if user_prefs.get("workspace_dir"):
            config["configurable"]["workspace_dir"] = user_prefs["workspace_dir"]
        if user_prefs.get("safe_mode") is not None:
            config["configurable"]["safe_mode"] = user_prefs["safe_mode"]
        if user_prefs.get("fast_mode") is not None:
            config["configurable"]["fast_mode"] = user_prefs["fast_mode"]

    input_msg = {"messages": [HumanMessage(content=user_message)], "mode": mode}

    result = await workflow.ainvoke(input_msg, config=config)
    messages = result.get("messages", [])

    # Return only the new messages (skip the input HumanMessage)
    new_messages = []
    for msg in messages:
        if isinstance(msg, (AIMessage, ToolMessage)):
            new_messages.append(msg)

    return new_messages
