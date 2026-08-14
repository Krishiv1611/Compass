"""Pure projection of runtime events into a surface-neutral run artifact."""

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from agent.runtime.events import StreamEvent, StreamEventType


class PlanStepArtifact(BaseModel):
    id: str
    text: str
    status: Literal["pending", "active", "completed", "failed"] = "pending"


class ToolArtifact(BaseModel):
    id: str
    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    result: Any | None = None
    status: Literal["running", "completed", "error"] = "running"


class CheckArtifact(BaseModel):
    id: str
    name: str
    status: str
    duration_ms: float | None = None
    details: Any | None = None


class RunArtifact(BaseModel):
    plan: str | None = None
    steps: list[PlanStepArtifact] = Field(default_factory=list)
    tools: list[ToolArtifact] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    checks: list[CheckArtifact] = Field(default_factory=list)
    usage: dict[str, Any] = Field(default_factory=dict)
    terminal_status: str | None = None
    final_summary: str | None = None


def empty_run_artifact() -> RunArtifact:
    return RunArtifact()


def _plan_steps(plan: str) -> list[PlanStepArtifact]:
    lines = [line.strip() for line in plan.splitlines() if line.strip()]
    numbered = []
    for line in lines:
        match = re.match(r"^\d+[.)]\s*(.+)$", line)
        if match:
            numbered.append(match.group(1).strip())
    values = numbered or ([plan.strip()] if plan.strip() else [])
    return [
        PlanStepArtifact(id=f"step-{index}", text=text)
        for index, text in enumerate(values, start=1)
    ]


def reduce_run_event(artifact: RunArtifact, event: StreamEvent) -> RunArtifact:
    """Return a new artifact with one canonical runtime event applied."""
    result = artifact.model_copy(deep=True)
    data = event.data if isinstance(event.data, dict) else {}

    if event.type == StreamEventType.PLAN_CREATED and event.content:
        result.plan = event.content
        result.steps = _plan_steps(event.content)
    elif event.type == StreamEventType.PLAN_STEP:
        step_number = data.get("step")
        if isinstance(step_number, int) and 0 < step_number <= len(result.steps):
            status = str(data.get("status", "active"))
            if status in {"pending", "active", "completed", "failed"}:
                result.steps[step_number - 1].status = status
    elif event.type == StreamEventType.TOOL_CALL and event.tool_call:
        call = event.tool_call
        existing = next((tool for tool in result.tools if tool.id == call.id), None)
        if existing:
            existing.name = call.name
            existing.args = call.args
        else:
            result.tools.append(
                ToolArtifact(id=call.id, name=call.name, args=call.args)
            )
    elif event.type == StreamEventType.TOOL_RESULT and event.tool_call_id:
        existing = next(
            (tool for tool in result.tools if tool.id == event.tool_call_id), None
        )
        if existing:
            existing.result = event.content
            existing.status = (
                "error" if str(data.get("status", "success")) == "error" else "completed"
            )
    elif event.type == StreamEventType.WORKSPACE_PATCH:
        files = data.get("affected_files", [])
        if isinstance(files, list):
            for path in files:
                if isinstance(path, str) and path not in result.changed_files:
                    result.changed_files.append(path)
    elif event.type == StreamEventType.CHECK_RESULT:
        check_id = str(
            data.get("id")
            or f"check-{event.seq if event.seq is not None else len(result.checks) + 1}"
        )
        value = CheckArtifact(
            id=check_id,
            name=event.content or event.node or "Check",
            status=str(data.get("status", "unknown")),
            duration_ms=(
                float(data["duration_ms"])
                if isinstance(data.get("duration_ms"), (int, float))
                else None
            ),
            details=data.get("details"),
        )
        existing = next(
            (check for check in result.checks if check.id == check_id), None
        )
        if existing:
            existing.name = value.name
            existing.status = value.status
            existing.duration_ms = value.duration_ms
            existing.details = value.details
        else:
            result.checks.append(value)
    elif event.type == StreamEventType.USAGE:
        result.usage = dict(data)
    elif event.type == StreamEventType.RUN_WAITING:
        result.terminal_status = str(data.get("status", "waiting_for_approval"))
    elif event.type == StreamEventType.DONE:
        result.terminal_status = str(data.get("status", "completed"))
        usage = data.get("metrics") or data.get("token_usage")
        if isinstance(usage, dict):
            result.usage = dict(usage)
        result.final_summary = event.content or data.get("assistant_content")
    elif event.type == StreamEventType.ERROR:
        result.terminal_status = "failed"
        result.final_summary = event.content

    return result
