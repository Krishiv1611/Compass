"""Shared LangGraph execution and streaming for web, TUI, and automation."""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from langgraph.types import Command

from agent.graph.workflow import get_workflow
from agent.runtime.events import StreamEvent, StreamEventType, ToolCallData
from agent.workspace import WorkspaceContext

logger = logging.getLogger(__name__)

_NODE_STATUS = {
    "context_injector": "Reading project",
    "planner": "Planning changes",
    "plan_approval": "Waiting for approval",
    "executor": "Working on request",
    "tools": "Reading project",
    "linter_node": "Checking changes",
    "evaluator": "Checking changes",
}

_OUTPUT_NODES = {"executor", "direct_chat", "skill_manager", "sub_executor"}


def normalise_mode(mode: str) -> str:
    return {"normal": "edit", "fast": "ask"}.get(mode, mode)


def validated_context_files(
    config: dict, context_files: list[str] | None
) -> list[str]:
    """Keep explicit context inside the configured workspace."""
    if not context_files:
        return []
    workspace_config = config.get("configurable", {}).get("workspace_context")
    if not workspace_config:
        return []
    workspace = WorkspaceContext.from_config(workspace_config)
    selected: list[str] = []
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


def build_turn_input(
    user_message: str,
    mode: str = "edit",
    context_files: list[str] | None = None,
    active_skill: dict | None = None,
    config: dict | None = None,
) -> dict:
    """Build fresh per-turn state so checkpoint data cannot leak across turns."""
    selected_files = validated_context_files(config or {}, context_files)
    payload = {
        "messages": [
            HumanMessage(
                content=user_message,
                additional_kwargs={"context_files": selected_files},
            )
        ],
        "mode": normalise_mode(mode),
        "plan": "",
        "current_step": 0,
        "is_done": False,
        "pending_tool_calls": [],
        "approval_status": None,
        "loop_detected": False,
        "loop_count": 0,
        "recovery_guidance": "",
        "syntax_checked": False,
        "syntax_check_failed": False,
        "token_usage": {},
        "active_skill": active_skill,
        "skill_result": None,
    }
    return payload


def _content_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict) and "text" in item
        )
    return str(content)


async def stream_agent_events(
    input_value: dict | Command,
    config: dict,
    cancel_event: asyncio.Event | None = None,
) -> AsyncGenerator[StreamEvent, None]:
    """Run one graph turn and emit the canonical Compass event protocol."""
    if cancel_event and cancel_event.is_set():
        yield StreamEvent(type=StreamEventType.DONE, data={"status": "cancelled"})
        return

    workflow = await get_workflow()
    configurable = config.setdefault("configurable", {})
    if configurable.get("context_mismatch"):
        yield StreamEvent(
            type=StreamEventType.ERROR,
            content=(
                "Project changed since this task was created. "
                "Refresh context before continuing."
            ),
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

    try:
        async for chunk_type, payload in workflow.astream(
            input_value,
            config=config,
            stream_mode=["messages", "updates"],
        ):
            if cancel_event and cancel_event.is_set():
                yield StreamEvent(
                    type=StreamEventType.DONE,
                    data={"status": "cancelled"},
                )
                return
            if chunk_type == "messages":
                chunk, metadata = payload
                node_name = (
                    metadata.get("langgraph_node")
                    if isinstance(metadata, dict)
                    else None
                )
                if node_name not in _OUTPUT_NODES:
                    continue
                if isinstance(chunk, (AIMessageChunk, AIMessage)):
                    content = _content_text(chunk.content)
                    if content:
                        yield StreamEvent(
                            type=StreamEventType.TOKEN,
                            content=content,
                            node=node_name,
                        )
                    for tool_call in getattr(chunk, "tool_call_chunks", []) or []:
                        if not tool_call.get("name"):
                            continue
                        args = tool_call.get("args", {})
                        if isinstance(args, str):
                            try:
                                args = json.loads(args) if args else {}
                            except json.JSONDecodeError:
                                args = {}
                        yield StreamEvent(
                            type=StreamEventType.TOOL_CALL,
                            node=node_name,
                            tool_call=ToolCallData(
                                id=tool_call.get("id", ""),
                                name=tool_call["name"],
                                args=args,
                            ),
                        )

            elif chunk_type == "updates":
                for node_name, node_output in payload.items():
                    finished_at = datetime.now(timezone.utc)
                    duration_ms = round(
                        (time.perf_counter() - stage_started_clock) * 1000, 1
                    )
                    status_text = _NODE_STATUS.get(node_name)
                    if node_name == "tools":
                        messages = node_output.get("messages", [])
                        if any(
                            getattr(message, "name", "")
                            in ("write_to_file", "edit_file")
                            for message in messages
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
                        plan = node_output.get("plan", "")
                        if plan:
                            yield StreamEvent(
                                type=StreamEventType.PLAN_CREATED,
                                content=plan,
                                node=node_name,
                            )
                    elif node_name == "loop_recovery":
                        loop_count = node_output.get("loop_count", 0)
                        guidance = node_output.get("recovery_guidance", "")
                        yield StreamEvent(
                            type=StreamEventType.LOOP_DETECTED,
                            content=guidance
                            or f"Loop detected, recovery attempt {loop_count}/3",
                            data={"loop_count": loop_count},
                            node=node_name,
                        )
                    elif node_name == "tools":
                        for message in node_output.get("messages", []):
                            if isinstance(message, ToolMessage):
                                yield StreamEvent(
                                    type=StreamEventType.TOOL_RESULT,
                                    tool_call_id=message.tool_call_id,
                                    content=str(message.content)[:500],
                                    data={
                                        "name": getattr(message, "name", "tool"),
                                        "status": getattr(
                                            message, "status", "success"
                                        ),
                                    },
                                    node=node_name,
                                )

        state = await workflow.aget_state(config)
        for task in state.tasks:
            for interrupt_value in task.interrupts:
                value = getattr(interrupt_value, "value", None)
                if not isinstance(value, dict):
                    continue
                reason = value.get("reason")
                if reason == "approval_required":
                    yield StreamEvent(
                        type=StreamEventType.APPROVAL_REQUIRED,
                        content=value.get("description", "Approval required"),
                        data={
                            "reason": reason,
                            "tool_calls": value.get("tool_calls", []),
                        },
                    )
                    return
                if reason == "plan_approval_required":
                    yield StreamEvent(
                        type=StreamEventType.APPROVAL_REQUIRED,
                        content="Plan approval required",
                        data={
                            "reason": reason,
                            "plan": value.get("plan", ""),
                        },
                    )
                    return

        token_usage = state.values.get("token_usage", {}) if state.values else {}
        yield StreamEvent(
            type=StreamEventType.DONE,
            data={"status": "completed", "token_usage": token_usage},
        )

    except Exception as exc:
        logger.exception("Agent execution error")
        message = str(exc)
        if (
            "UnauthorizedResponseError" in message
            or "User not found" in message
            or "401" in message
        ):
            message = "Invalid LLM API key. Update the configured API key."
        yield StreamEvent(type=StreamEventType.ERROR, content=message[:500])


async def invoke_agent(input_value: dict | Command, config: dict) -> list[BaseMessage]:
    """Invoke the shared graph runtime without streaming."""
    workflow = await get_workflow()
    if config.get("configurable", {}).get("context_mismatch"):
        raise ValueError(
            "Project changed since this task was created. Refresh context first."
        )
    result = await workflow.ainvoke(input_value, config=config)
    return [
        message
        for message in result.get("messages", [])
        if isinstance(message, (AIMessage, ToolMessage))
    ]
