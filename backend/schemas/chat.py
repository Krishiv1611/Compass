from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Any


# ── Enums ─────────────────────────────────────────────────


class StreamEventType(str, Enum):
    """Event types pushed over the WebSocket."""

    TOKEN = "token"
    ASSISTANT_DELTA = "assistant_delta"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    APPROVAL_REQUIRED = "approval_required"
    RPC_CALL = "rpc_call"
    WORKSPACE_PATCH = "workspace_patch"
    PLAN_CREATED = "plan_created"
    PLAN_STEP = "plan_step"
    LOOP_DETECTED = "loop_detected"
    STATUS = "status"
    DONE = "done"
    ERROR = "error"


# ── Requests ──────────────────────────────────────────────


class ChatRequest(BaseModel):
    """POST /chat/send  —  non-streaming fallback."""

    session_id: str
    content: str = Field(..., min_length=1)
    mode: str = "normal"


class WsClientMessage(BaseModel):
    """Message sent by the client over WebSocket."""

    type: str = "message"  # "message" | "cancel" | "tool_result"
    content: str | None = None
    call_id: str | None = None
    result: Any | None = None
    error: str | None = None
    mode: str = "normal"
    action: str | None = None


# ── Responses ─────────────────────────────────────────────


class ToolCallData(BaseModel):
    """Serialized representation of a single tool invocation."""

    id: str
    name: str
    args: dict


class MessageResponse(BaseModel):
    """A complete message returned by the non-streaming endpoint."""

    id: str
    role: str
    content: str | None = None
    tool_calls: list[ToolCallData] | None = None
    model: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    """POST /chat/send response (non-streaming)."""

    messages: list[MessageResponse]


class StreamEvent(BaseModel):
    """
    A single event pushed over the WebSocket connection.
    """

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
