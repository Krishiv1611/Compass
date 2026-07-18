import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.db import Base

class WorkspacePatch(Base):
    """
    Represents a set of file changes proposed by the agent.
    Can be approved, rejected, or reverted by the user.
    """
    __tablename__ = "workspace_patches"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50), 
        nullable=False, 
        default="pending" # pending, applied, rejected, reverted
    )
    
    # List of changes: [{ "type": "edit|create|delete", "path": "...", "content": "..." }]
    changes: Mapped[list | None] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    workspace = relationship("Workspace")
    run = relationship("AgentRun")

    def __repr__(self) -> str:
        return f"<WorkspacePatch id={self.id!r} status={self.status!r}>"
