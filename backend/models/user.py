import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Boolean, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.db import Base


class User(Base):
    """
    User account — supports email/password and OAuth logins.
    """
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    email: Mapped[str] = mapped_column(
        String(320), unique=True, nullable=False, index=True
    )
    hashed_password: Mapped[str | None] = mapped_column(
        Text, nullable=True  # nullable for OAuth-only users
    )
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    oauth_provider: Mapped[str | None] = mapped_column(
        String(20), nullable=True  # "google", "github", or None
    )
    oauth_provider_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True  # ID from the OAuth provider
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    preferences: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=None,
        comment="User preferences (theme, model, language, etc.)",
    )

    # Relationships
    sessions = relationship(
        "ChatSession", back_populates="user", cascade="all, delete-orphan"
    )
    uploads = relationship(
        "UploadedFile", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id!r} email={self.email!r}>"
