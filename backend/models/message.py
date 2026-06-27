import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.db import Base


class Message(Base):
    """
    A single message (user, assistant, or tool) within a chat session.
    """
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="One of: user, assistant, system, tool",
    )
    content: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Text content of the message (may be null for pure tool-call messages)",
    )
    tool_calls: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="Serialized tool call invocations (name, args, id) when role=assistant",
    )
    tool_call_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="ID of the tool call this message responds to (when role=tool)",
    )
    model: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="LLM model that generated this message (for assistant messages)",
    )
    token_count: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Approximate token count for this message",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    session = relationship("ChatSession", back_populates="messages")

    def __repr__(self) -> str:
        preview = (self.content or "")[:40]
        return f"<Message id={self.id!r} role={self.role!r} content={preview!r}>"
