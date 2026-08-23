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
from agent.runtime.protocol import InterruptData, InterruptKind
from agent.runtime.metrics import begin_run_metrics, end_run_metrics
from agent.runtime.turn_context import prepare_turn_context
from agent.workspace import WorkspaceContext

logger = logging.getLogger(__name__)

_NODE_STATUS = {
    "context_injector": "Reading project",
    "planner": "Planning changes",
    "plan_approval": "Waiting for approval",
    "coordinator": "Running read-only workers",
    "synthesis": "Reviewing worker evidence",
    "executor": "Working on request",
    "tools": "Reading project",
    "linter_node": "Checking changes",
    "evaluator": "Checking changes",
    "verification_hooks": "Preparing verification",
    "verification_hooks_finalize": "Verification finished",
}

_OUTPUT_NODES = {"executor", "direct_chat", "skill_manager", "sub_executor"}


class ToolCallAssembler:
    """Assemble provider tool-call chunks without discarding partial JSON."""

    def __init__(self):
        self._calls: dict[str, dict] = {}

    def add(self, chunk: dict) -> list[StreamEvent]:
        index = chunk.get("index")
        call_id = chunk.get("id")
        if index is None and not call_id:
            return []
        key = f"index:{index}" if index is not None else f"id:{call_id}"
        state = self._calls.setdefault(
            key,
            {"id": "", "name": "", "args_text": "", "args": None, "emitted": False},
        )
        if call_id and state["emitted"] and state["id"] != call_id:
            state = {
                "id": "",
                "name": "",
                "args_text": "",
                "args": None,
                "emitted": False,
            }
            self._calls[key] = state
        if call_id:
            state["id"] = call_id
        if chunk.get("name"):
            state["name"] = chunk["name"]

        args = chunk.get("args")
        if isinstance(args, dict):
            state["args"] = args
        elif isinstance(args, str):
            state["args_text"] += args
            try:
                parsed = json.loads(state["args_text"])
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                state["args"] = parsed

        if (
            state["emitted"]
            or not state["id"]
            or not state["name"]
            or not isinstance(state["args"], dict)
        ):
            return []
        state["emitted"] = True
        return [
            StreamEvent(
                type=StreamEventType.TOOL_CALL,
                tool_call=ToolCallData(
                    id=state["id"],
                    name=state["name"],
                    args=state["args"],
                ),
            )
        ]


_MUTATING_FILE_TOOLS = {"write_to_file", "edit_file", "delete_file"}


def workspace_patch_for_tool_result(
    *,
    tool_call_id: str,
    tool_name: str,
    tool_args: dict,
    status: str,
    result_content: object,
) -> StreamEvent | None:
    """Project a successful file mutation into the shared run artifact."""
    result_text = str(result_content).lstrip().lower()
    if (
        tool_name not in _MUTATING_FILE_TOOLS
        or status == "error"
        or not result_text.startswith(("successfully ", "proposed "))
    ):
        return None
    path = tool_args.get("path") or tool_args.get("file_path")
    if not isinstance(path, str) or not path:
        return None
    return StreamEvent(
        type=StreamEventType.WORKSPACE_PATCH,
        tool_call_id=tool_call_id,
        data={"affected_files": [path]},
    )


def events_for_node_artifacts(node_name: str, node_output: dict) -> list[StreamEvent]:
    """Translate deterministic graph outcomes into surface artifact events."""
    events: list[StreamEvent] = []
    checkpoint_id = node_output.get("last_checkpoint_id")
    if node_name == "tools" and isinstance(checkpoint_id, str) and checkpoint_id:
        events.append(
            StreamEvent(
                type=StreamEventType.CHECKPOINT_CREATED,
                node=node_name,
                data={
                    "checkpoint_id": checkpoint_id,
                    "affected_files": node_output.get("checkpoint_files", []),
                },
            )
        )
    current_step = node_output.get("current_step")
    if (
        node_name in {"executor", "sub_executor"}
        and isinstance(current_step, int)
        and current_step > 0
    ):
        events.append(
            StreamEvent(
                type=StreamEventType.PLAN_STEP,
                node=node_name,
                data={"step": current_step, "status": "completed"},
            )
        )
    if node_name == "linter_node":
        failed = bool(node_output.get("syntax_check_failed", False))
        events.append(
            StreamEvent(
                type=StreamEventType.CHECK_RESULT,
                content="Syntax checks",
                node=node_name,
                data={
                    "status": "failed" if failed else "passed",
                    "details": node_output.get("recovery_guidance"),
                },
            )
        )
    if node_name == "coordinator":
        from agent.orchestration.models import sanitize_artifact_text

        summaries = {
            str(item.get("task_id")): sanitize_artifact_text(str(item.get("summary", "")))
            for item in node_output.get("worker_artifacts", [])
            if isinstance(item, dict) and item.get("task_id")
        }
        for payload in node_output.get("worker_events", []):
            try:
                event = StreamEvent.model_validate(payload)
            except Exception:
                continue
            data = event.data if isinstance(event.data, dict) else {}
            if event.type in {
                StreamEventType.AGENT_COMPLETED,
                StreamEventType.AGENT_FAILED,
            }:
                event.content = summaries.get(str(data.get("task_id"))) or None
            events.append(event)
    if node_name == "synthesis":
        synthesis = node_output.get("synthesis", {})
        if isinstance(synthesis, dict):
            events.append(
                StreamEvent(
                    type=StreamEventType.STATUS,
                    content="Worker evidence synthesized",
                    node=node_name,
                    data={
                        "conflicts": synthesis.get("conflicts", []),
                        "missing_evidence": synthesis.get("missing_evidence", []),
                    },
                )
            )
    return events


def with_node_duration(event: StreamEvent, duration_ms: float) -> StreamEvent:
    """Add node timing without erasing a more precise event duration."""
    data = dict(event.data) if isinstance(event.data, dict) else {}
    data.setdefault("duration_ms", duration_ms)
    event.data = data
    return event


def events_from_interrupts(interrupts: list[dict]) -> list[StreamEvent]:
    """Translate one graph interrupt into the canonical waiting event pair."""

    if not interrupts:
        return []
    data = InterruptData.model_validate(interrupts[0]["value"])
    event_type = (
        StreamEventType.CLARIFICATION_REQUIRED
        if data.kind == InterruptKind.CLARIFICATION
        else StreamEventType.APPROVAL_REQUIRED
    )
    payload = data.model_dump(mode="json")
    payload["reason"] = {
        InterruptKind.TOOL_APPROVAL: "approval_required",
        InterruptKind.PLAN_APPROVAL: "plan_approval_required",
        InterruptKind.CLARIFICATION: "clarification_required",
    }[data.kind]
    return [
        StreamEvent(
            type=event_type,
            content=data.prompt,
            data=payload,
        ),
        StreamEvent(
            type=StreamEventType.RUN_WAITING,
            data={"kind": data.kind.value},
        ),
    ]


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
        "execution_plan": None,
        "worker_artifacts": [],
        "worker_events": [],
        "synthesis": None,
        "orchestration_enabled": False,
        "is_done": False,
        "pending_tool_calls": [],
        "approval_status": None,
        "loop_detected": False,
        "loop_count": 0,
        "recovery_guidance": "",
        "goal_iteration": 0,
        "goal_iteration_limit": 3,
        "needs_replan": False,
        "syntax_checked": False,
        "syntax_check_failed": False,
        "verification_hooks_scheduled": False,
        "last_checkpoint_id": None,
        "checkpoint_files": [],
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


def _message_ids(messages: list[BaseMessage]) -> set[str]:
    return {
        message.id
        for message in messages
        if isinstance(getattr(message, "id", None), str)
    }


def _current_turn_assistant_content(
    before_ids: set[str],
    messages: list[BaseMessage],
) -> str | None:
    from backend.services.run_persistence import messages_created_this_turn

    new_messages = messages_created_this_turn(before_ids, messages)
    for message in reversed(new_messages):
        if isinstance(message, AIMessage):
            content = _content_text(message.content)
            if content:
                return content
    return None


async def stream_agent_events(
    input_value: dict | Command,
    config: dict,
    cancel_event: asyncio.Event | None = None,
    metrics: "RunMetrics | None" = None,
) -> AsyncGenerator[StreamEvent, None]:
    """Run one graph turn and emit the canonical Compass event protocol."""
    if cancel_event and cancel_event.is_set():
        yield StreamEvent(type=StreamEventType.DONE, data={"status": "cancelled"})
        return

    workflow = await get_workflow()
    configurable = config.setdefault("configurable", {})
    configurable.pop("_turn_context", None)
    if configurable.get("context_mismatch"):
        yield StreamEvent(
            type=StreamEventType.ERROR,
            content=(
                "Project changed since this task was created. "
                "Refresh context before continuing."
            ),
            data={"status": "failed"},
        )
        return

    before_state = await workflow.aget_state(config)
    before_messages = (
        before_state.values.get("messages", [])
        if before_state and before_state.values
        else []
    )
    before_ids = _message_ids(before_messages)
    stage_started_at = datetime.now(timezone.utc)
    stage_started_clock = time.perf_counter()
    yield StreamEvent(
        type=StreamEventType.STATUS,
        content="Understanding request",
        node="input",
        data={"started_at": stage_started_at.isoformat()},
    )

    assembler = ToolCallAssembler()
    tool_calls: dict[str, tuple[str, dict]] = {}
    hook_names: dict[str, str] = {}
    for message in before_messages:
        for call in getattr(message, "tool_calls", []) or []:
            call_id = str(call.get("id", ""))
            name = str(call.get("name", ""))
            args = call.get("args") or {}
            if call_id and name and isinstance(args, dict):
                tool_calls[call_id] = (name, args)
                if call_id.startswith("hook-"):
                    hook_names[call_id] = str(
                        args.get("hook_name") or "Verification hook"
                    )
    metrics, metrics_token = begin_run_metrics(metrics)
    for tag in ("provider", "model", "mode", "execution_target"):
        value = configurable.get(tag)
        if value is not None:
            metrics.add_tag(tag, value)
    try:
        await prepare_turn_context(input_value, config)
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
                        for event in assembler.add(tool_call):
                            event.node = node_name
                            if event.tool_call:
                                tool_calls[event.tool_call.id] = (
                                    event.tool_call.name,
                                    event.tool_call.args,
                                )
                            yield event

            elif chunk_type == "updates":
                for node_name, node_output in payload.items():
                    # LangGraph reserves double-underscore entries such as
                    # ``__interrupt__`` for transport metadata. Their values
                    # are tuples, not graph-node update dictionaries.
                    if node_name.startswith("__"):
                        continue
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
                        for message in messages:
                            call_id = str(getattr(message, "tool_call_id", ""))
                            if call_id.startswith("hook-"):
                                yield StreamEvent(
                                    type=StreamEventType.CHECK_RESULT,
                                    content=hook_names.get(call_id, "Verification hook"),
                                    node=node_name,
                                    data={"id": call_id, "status": "running"},
                                )
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

                    for artifact_event in events_for_node_artifacts(
                        node_name,
                        node_output,
                    ):
                        yield with_node_duration(artifact_event, duration_ms)

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
                    elif node_name == "verification_hooks":
                        for message in node_output.get("messages", []):
                            for call in getattr(message, "tool_calls", []) or []:
                                call_id = str(call.get("id", ""))
                                name = str(call.get("name", ""))
                                args = call.get("args") or {}
                                if not call_id or not name or not isinstance(args, dict):
                                    continue
                                tool_calls[call_id] = (name, args)
                                hook_names[call_id] = str(
                                    args.get("hook_name") or "Verification hook"
                                )
                                yield StreamEvent(
                                    type=StreamEventType.TOOL_CALL,
                                    tool_call=ToolCallData(
                                        id=call_id, name=name, args=args
                                    ),
                                    node=node_name,
                                )
                                yield StreamEvent(
                                    type=StreamEventType.CHECK_RESULT,
                                    content=hook_names[call_id],
                                    node=node_name,
                                    data={"id": call_id, "status": "pending"},
                                )
                    elif node_name in {"tools", "check_safety"}:
                        from agent.hooks import hook_result_status, redact_hook_output

                        for message in node_output.get("messages", []):
                            if isinstance(message, ToolMessage):
                                status = getattr(message, "status", "success")
                                is_hook = str(message.tool_call_id).startswith("hook-")
                                content = (
                                    redact_hook_output(message.content, limit=500)
                                    if is_hook
                                    else str(message.content)[:500]
                                )
                                yield StreamEvent(
                                    type=StreamEventType.TOOL_RESULT,
                                    tool_call_id=message.tool_call_id,
                                    content=content,
                                    data={
                                        "name": getattr(message, "name", "tool"),
                                        "status": status,
                                    },
                                    node=node_name,
                                )
                                if is_hook:
                                    call_id = str(message.tool_call_id)
                                    yield StreamEvent(
                                        type=StreamEventType.CHECK_RESULT,
                                        content=hook_names.get(
                                            call_id, "Verification hook"
                                        ),
                                        node=node_name,
                                        data={
                                            "id": call_id,
                                            "status": hook_result_status(
                                                message.content, status
                                            ),
                                            "duration_ms": duration_ms,
                                            "details": redact_hook_output(
                                                message.content
                                            ),
                                        },
                                    )
                                call = tool_calls.get(message.tool_call_id)
                                if call:
                                    patch_event = workspace_patch_for_tool_result(
                                        tool_call_id=message.tool_call_id,
                                        tool_name=call[0],
                                        tool_args=call[1],
                                        status=status,
                                        result_content=message.content,
                                    )
                                    if patch_event:
                                        patch_event.node = node_name
                                        yield patch_event

        with metrics.span("checkpoint.read"):
            state = await workflow.aget_state(config)
        interrupts = [
            {"value": getattr(interrupt_value, "value", None)}
            for task in state.tasks
            for interrupt_value in task.interrupts
            if isinstance(getattr(interrupt_value, "value", None), dict)
        ]
        waiting_events = events_from_interrupts(interrupts)
        if waiting_events:
            metrics_snapshot = metrics.snapshot().model_dump(mode="json")
            token_usage = {
                "prompt_tokens": metrics_snapshot["total_input_tokens"],
                "completion_tokens": metrics_snapshot["total_output_tokens"],
                "total_tokens": metrics_snapshot["total_tokens"],
                "per_node_breakdown": metrics_snapshot["usage_by_node"],
            }
            yield StreamEvent(type=StreamEventType.USAGE, data=metrics_snapshot)
            assistant_content = _current_turn_assistant_content(
                before_ids,
                state.values.get("messages", []) if state.values else [],
            )
            for event in waiting_events:
                if event.type == StreamEventType.RUN_WAITING:
                    event.data = {
                        **(event.data or {}),
                        "status": "waiting_for_approval",
                        "token_usage": token_usage,
                        "assistant_content": assistant_content,
                    }
                yield event
            return

        metrics_snapshot = metrics.snapshot().model_dump(mode="json")
        token_usage = {
            "prompt_tokens": metrics_snapshot["total_input_tokens"],
            "completion_tokens": metrics_snapshot["total_output_tokens"],
            "total_tokens": metrics_snapshot["total_tokens"],
            "per_node_breakdown": metrics_snapshot["usage_by_node"],
        }
        yield StreamEvent(type=StreamEventType.USAGE, data=metrics_snapshot)
        assistant_content = _current_turn_assistant_content(
            before_ids,
            state.values.get("messages", []) if state.values else [],
        )
        yield StreamEvent(
            type=StreamEventType.DONE,
            data={
                "status": "completed",
                "token_usage": token_usage,
                "metrics": metrics_snapshot,
                "assistant_content": assistant_content,
            },
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
        metrics_snapshot = metrics.snapshot().model_dump(mode="json")
        token_usage = {
            "prompt_tokens": metrics_snapshot["total_input_tokens"],
            "completion_tokens": metrics_snapshot["total_output_tokens"],
            "total_tokens": metrics_snapshot["total_tokens"],
            "per_node_breakdown": metrics_snapshot["usage_by_node"],
        }
        yield StreamEvent(
            type=StreamEventType.ERROR,
            content=message[:500],
            data={
                "status": "failed",
                "token_usage": token_usage,
                "metrics": metrics_snapshot,
            },
        )
    finally:
        end_run_metrics(metrics_token)


async def invoke_agent(input_value: dict | Command, config: dict) -> list[BaseMessage]:
    """Invoke the shared graph runtime without streaming."""
    workflow = await get_workflow()
    if config.get("configurable", {}).get("context_mismatch"):
        raise ValueError(
            "Project changed since this task was created. Refresh context first."
        )
    before_state = await workflow.aget_state(config)
    before_messages = (
        before_state.values.get("messages", [])
        if before_state and before_state.values
        else []
    )
    before_ids = _message_ids(before_messages)
    config.setdefault("configurable", {}).pop("_turn_context", None)
    _metrics, metrics_token = begin_run_metrics()
    try:
        await prepare_turn_context(input_value, config)
        result = await workflow.ainvoke(input_value, config=config)
    finally:
        end_run_metrics(metrics_token)
    messages = [
        message
        for message in result.get("messages", [])
        if isinstance(message, (AIMessage, ToolMessage))
    ]
    from backend.services.run_persistence import messages_created_this_turn

    return messages_created_this_turn(before_ids, messages)
