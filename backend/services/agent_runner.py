"""
Agent runner — async wrapper around the LangGraph agent workflow.

Provides both streaming and non-streaming interfaces for the FastAPI backend.
"""

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage

from agent.graph.workflow import get_workflow
from agent.telemetry import get_run_config
from agent.workspace import web_workspace_context

from backend.schemas.chat import StreamEvent, StreamEventType, ToolCallData

from langgraph.types import Command

logger = logging.getLogger(__name__)

_NODE_STATUS = {
    "guardrails_input": "Understanding request",
    "context_injector": "Reading project",
    "planner": "Planning changes",
    "plan_approval": "Waiting for approval",
    "executor": "Working on request",
    "tools": "Reading project",
    "linter_node": "Checking changes",
    "evaluator": "Checking changes",
    "guardrails_output": "Completed",
}

def _normalise_mode(mode: str) -> str:
    return {"normal": "edit", "fast": "ask"}.get(mode, mode)


def _configure_web_workspace(config: dict, session_id: str, user_id: str) -> None:
    from backend.db import SessionLocal
    from backend.models.session import ChatSession
    from backend.services.workspace import get_workspace_by_session

    db = SessionLocal()
    try:
        workspace = get_workspace_by_session(db, session_id, user_id)
        context = web_workspace_context(workspace)
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
            ChatSession.is_deleted.is_(False),
        ).first()
        if not session:
            raise ValueError("Session not found.")
        config["configurable"]["execution_target"] = "web"
        config["configurable"]["workspace_context"] = context.to_config()
        config["configurable"]["workspace_id"] = context.workspace_id
        config["configurable"]["project_id"] = context.project_id
        config["configurable"]["context_version"] = context.context_version
        config["configurable"]["context_mismatch"] = bool(
            session.context_version
            and context.context_version
            and session.context_version != context.context_version
        )
    finally:
        db.close()


def _validated_context_files(config: dict, context_files: list[str] | None) -> list[str]:
    from agent.workspace import WorkspaceContext

    if not context_files:
        return []
    workspace = WorkspaceContext.from_config(config["configurable"]["workspace_context"])
    selected = []
    for value in context_files[:20]:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            continue
        target = (workspace.root / path).resolve()
        try:
            target.relative_to(workspace.root)
        except ValueError:
            continue
        if target.is_file():
            selected.append(path.as_posix())
    return selected


async def run_agent_stream(
    user_message: str,
    thread_id: str,
    session_id: str,
    user_id: str,
    mode: str = "edit",
    resume_action: str | None = None,
    user_prefs: dict | None = None,
    run_id: str | None = None,
    context_files: list[str] | None = None,
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
        
    _configure_web_workspace(config, session_id, user_id)
    
    if user_prefs:
        if user_prefs.get("model"):
            config["configurable"]["model"] = user_prefs["model"]
            config["configurable"]["model_executor"] = user_prefs["model"]
            config["configurable"]["model_planner"] = user_prefs["model"]
        encrypted_key = user_prefs.get("llm_api_key_encrypted")
        if encrypted_key:
            from backend.auth.credentials import decrypt_credential
            config["configurable"]["api_key"] = decrypt_credential(encrypted_key)
        if user_prefs.get("llm_provider"):
            config["configurable"]["provider"] = user_prefs["llm_provider"]
        if user_prefs.get("safe_mode") is not None:
            config["configurable"]["safe_mode"] = user_prefs["safe_mode"]
        if user_prefs.get("fast_mode") is not None:
            config["configurable"]["fast_mode"] = user_prefs["fast_mode"]
    
    if resume_action:
        input_msg = Command(resume={"action": resume_action})
    else:
        selected_files = _validated_context_files(config, context_files)
        input_msg = {
            "messages": [
                HumanMessage(
                    content=user_message,
                    additional_kwargs={"context_files": selected_files},
                )
            ],
            "mode": _normalise_mode(mode),
        }

    try:
        from langchain_core.messages import AIMessageChunk, ToolMessage
        if config["configurable"].get("context_mismatch"):
            yield StreamEvent(
                type=StreamEventType.ERROR,
                content="Project changed since this task was created. Refresh context before continuing.",
            )
            return
        stage_started_at = datetime.now(timezone.utc)
        stage_started_clock = time.perf_counter()
        yield StreamEvent(
            type=StreamEventType.STATUS,
            content="Understanding request",
            node="input",
            data={"started_at": stage_started_at.isoformat()},
        )
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
                    finished_at = datetime.now(timezone.utc)
                    duration_ms = round((time.perf_counter() - stage_started_clock) * 1000, 1)
                    status_text = _NODE_STATUS.get(node_name)
                    if node_name == "tools":
                        tool_messages = node_output.get("messages", [])
                        if any(
                            getattr(message, "name", "") in ("write_to_file", "edit_file")
                            for message in tool_messages
                        ):
                            status_text = "Editing files"
                    if status_text:
                        yield StreamEvent(
                            type=StreamEventType.STATUS,
                            content=status_text,
                            node=node_name,
                            data={
                                "started_at": stage_started_at.isoformat(),
                                "finished_at": finished_at.isoformat(),
                                "duration_ms": duration_ms,
                            },
                        )
                    stage_started_at = finished_at
                    stage_started_clock = time.perf_counter()

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
                                yield StreamEvent(
                                    type=StreamEventType.APPROVAL_REQUIRED,
                                    content=desc,
                                    data={"tool_calls": tool_calls}
                                )
                                interrupted = True
                                break
                            elif interrupt_val.value.get("reason") == "plan_approval_required":
                                plan_text = interrupt_val.value.get("plan", "")
                                yield StreamEvent(
                                    type=StreamEventType.APPROVAL_REQUIRED,
                                    content="Plan Approval Required",
                                    data={"reason": "plan_approval_required", "plan": plan_text}
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
    mode: str = "edit",
    user_prefs: dict | None = None,
    context_files: list[str] | None = None,
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
    
    _configure_web_workspace(config, session_id, user_id)
    if config["configurable"].get("context_mismatch"):
        raise ValueError(
            "Project changed since this task was created. Refresh context before continuing."
        )
    
    if user_prefs:
        if user_prefs.get("model"):
            config["configurable"]["model"] = user_prefs["model"]
            config["configurable"]["model_executor"] = user_prefs["model"]
            config["configurable"]["model_planner"] = user_prefs["model"]
        encrypted_key = user_prefs.get("llm_api_key_encrypted")
        if encrypted_key:
            from backend.auth.credentials import decrypt_credential
            config["configurable"]["api_key"] = decrypt_credential(encrypted_key)
        if user_prefs.get("llm_provider"):
            config["configurable"]["provider"] = user_prefs["llm_provider"]
        if user_prefs.get("safe_mode") is not None:
            config["configurable"]["safe_mode"] = user_prefs["safe_mode"]
        if user_prefs.get("fast_mode") is not None:
            config["configurable"]["fast_mode"] = user_prefs["fast_mode"]

    selected_files = _validated_context_files(config, context_files)
    input_msg = {
        "messages": [
            HumanMessage(
                content=user_message,
                additional_kwargs={"context_files": selected_files},
            )
        ],
        "mode": _normalise_mode(mode),
    }

    result = await workflow.ainvoke(input_msg, config=config)
    messages = result.get("messages", [])

    # Return only the new messages (skip the input HumanMessage)
    new_messages = []
    for msg in messages:
        if isinstance(msg, (AIMessage, ToolMessage)):
            new_messages.append(msg)

    return new_messages
