from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────

class StreamEventType(str, Enum):
    """Event types pushed over the WebSocket."""
    TOKEN = "token"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    DONE = "done"
    ERROR = "error"


# ── Requests ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    """POST /chat/send  —  non-streaming fallback."""
    session_id: str
    content: str = Field(..., min_length=1)


class WsClientMessage(BaseModel):
    """Message sent by the client over WebSocket."""
    type: str = "message"  # "message" | "cancel"
    content: str | None = None


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

    Examples:
        {"type": "token",       "content": "Hello"}
        {"type": "tool_call",   "tool_call": {"id": "...", "name": "read_file", "args": {...}}}
        {"type": "tool_result", "tool_call_id": "...", "content": "file contents..."}
        {"type": "done"}
        {"type": "error",       "content": "something went wrong"}
    """
    type: StreamEventType
    content: str | None = None
    tool_call: ToolCallData | None = None
    tool_call_id: str | None = None
