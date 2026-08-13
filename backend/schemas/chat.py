from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any, Literal

from agent.runtime.events import StreamEvent, StreamEventType, ToolCallData
from agent.runtime.protocol import ResumeAction


# ── Enums ─────────────────────────────────────────────────


class ChatRequest(BaseModel):
    """POST /chat/send  —  non-streaming fallback."""

    session_id: str
    content: str = Field(..., min_length=1)
    mode: Literal["ask", "edit", "plan", "goal", "normal", "fast"] = "edit"
    context_files: list[str] = Field(default_factory=list)
    active_skill: str | None = None


class WsClientMessage(BaseModel):
    """Message sent by the client over WebSocket."""

    type: str = "message"  # "message" | "cancel" | "tool_result"
    content: str | None = None
    call_id: str | None = None
    result: Any | None = None
    error: str | None = None
    mode: Literal["ask", "edit", "plan", "goal", "normal", "fast"] = "edit"
    context_files: list[str] = Field(default_factory=list)
    active_skill: str | None = None
    action: ResumeAction | None = None
    feedback: str | None = None
    last_seq: int | None = None
    run_id: str | None = None


# ── Responses ─────────────────────────────────────────────


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
