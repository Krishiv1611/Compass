from datetime import datetime
from pydantic import BaseModel, Field


# ── Requests ──────────────────────────────────────────────


class SessionCreate(BaseModel):
    """POST /sessions"""

    title: str | None = Field(None, max_length=200)


class SessionRename(BaseModel):
    """PATCH /sessions/{id}"""

    title: str = Field(..., min_length=1, max_length=200)


# ── Responses ─────────────────────────────────────────────


class SessionSummary(BaseModel):
    """Lightweight session item for list views (GET /sessions)."""

    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class MessageInSession(BaseModel):
    """Message embedded inside SessionDetail."""

    id: str
    role: str
    content: str | None = None
    tool_calls: dict | None = None
    tool_call_id: str | None = None
    model: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionDetail(BaseModel):
    """Full session with messages (GET /sessions/{id})."""

    id: str
    title: str | None
    thread_id: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageInSession] = []

    model_config = {"from_attributes": True}
