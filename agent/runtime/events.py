"""Transport-neutral events emitted by the Compass agent runtime."""

from enum import Enum
from typing import Any

from pydantic import BaseModel


class StreamEventType(str, Enum):
    TOKEN = "token"
    ASSISTANT_DELTA = "assistant_delta"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    APPROVAL_REQUIRED = "approval_required"
    CLARIFICATION_REQUIRED = "clarification_required"
    RUN_WAITING = "run_waiting"
    RPC_CALL = "rpc_call"
    WORKSPACE_PATCH = "workspace_patch"
    CHECKPOINT_CREATED = "checkpoint_created"
    CHECKPOINT_RESTORED = "checkpoint_restored"
    SESSION_FORKED = "session_forked"
    PLAN_CREATED = "plan_created"
    PLAN_STEP = "plan_step"
    CHECK_RESULT = "check_result"
    USAGE = "usage"
    LOOP_DETECTED = "loop_detected"
    STATUS = "status"
    DONE = "done"
    ERROR = "error"


class ToolCallData(BaseModel):
    id: str
    name: str
    args: dict


class StreamEvent(BaseModel):
    """A presentation-independent event produced during an agent turn."""

    type: StreamEventType
    content: str | None = None
    tool_call: ToolCallData | None = None
    tool_call_id: str | None = None
    data: Any | None = None
    node: str | None = None
    run_id: str | None = None
    session_id: str | None = None
    thread_id: str | None = None
    message_id: str | None = None
    seq: int | None = None
