import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.db import Base

class AgentRun(Base):
    """
    Tracks a single execution of the agent, grouping together all the events 
    (tool calls, tokens, etc.) that occurred during that run.
    """
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50), 
        nullable=False, 
        default="running"
    )
    
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    token_usage: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # Relationships
    session = relationship("ChatSession", back_populates="runs")
    events = relationship(
        "RunEvent",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="RunEvent.created_at",
    )

    def __repr__(self) -> str:
        return f"<AgentRun id={self.id!r} status={self.status!r}>"


class RunEvent(Base):
    """
    A single event in an AgentRun. Can be a token generation, a tool call starting, 
    stdout from a command, an error, etc.
    """
    __tablename__ = "run_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(50), 
        nullable=False
    )
    content: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    run = relationship("AgentRun", back_populates="events")

    def __repr__(self) -> str:
        return f"<RunEvent id={self.id!r} type={self.event_type!r}>"
