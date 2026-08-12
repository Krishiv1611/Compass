"""
Session management service — CRUD operations for chat sessions.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from agent.llm import llm
from backend.models.session import ChatSession
from backend.models.message import Message
from backend.models.workspace import Workspace
from backend.schemas.session import SessionSummary, SessionDetail, MessageInSession


def create_session(
    db: Session,
    user_id: str,
    title: str | None = None,
) -> ChatSession:
    """Create a new chat session for a user."""
    session = ChatSession(
        user_id=user_id,
        title=title or "New Chat",
        thread_id=uuid.uuid4().hex,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_sessions(
    db: Session,
    user_id: str,
    page: int = 1,
    page_size: int = 20,
) -> list[SessionSummary]:
    """List a user's non-deleted sessions, ordered by most recently updated."""
    offset = (page - 1) * page_size

    message_counts = (
        db.query(
            Message.session_id.label("session_id"),
            func.count(Message.id).label("message_count"),
        )
        .group_by(Message.session_id)
        .subquery()
    )

    rows = (
        db.query(
            ChatSession,
            func.coalesce(message_counts.c.message_count, 0).label("message_count"),
            Workspace.name.label("workspace_name"),
        )
        .outerjoin(
            message_counts,
            message_counts.c.session_id == ChatSession.id,
        )
        .outerjoin(Workspace, Workspace.id == ChatSession.active_workspace_id)
        .filter(
            ChatSession.user_id == user_id,
            ChatSession.is_deleted.is_(False),
        )
        .order_by(ChatSession.updated_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return [
        SessionSummary(
            id=s.id,
            title=s.title,
            created_at=s.created_at,
            updated_at=s.updated_at,
            message_count=int(count),
            active_workspace_id=s.active_workspace_id,
            workspace_name=workspace_name,
            project_id=s.project_id,
            git_branch=s.git_branch,
            git_head=s.git_head,
            context_version=s.context_version,
        )
        for s, count, workspace_name in rows
    ]


def get_session_detail(
    db: Session,
    user_id: str,
    session_id: str,
) -> SessionDetail | None:
    """Get a single session with its full message history."""
    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
            ChatSession.is_deleted.is_(False),
        )
        .first()
    )
    if not session:
        return None

    messages = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
        .all()
    )

    return SessionDetail(
        id=session.id,
        title=session.title,
        thread_id=session.thread_id,
        active_workspace_id=session.active_workspace_id,
        project_id=session.project_id,
        git_remote=session.git_remote,
        git_branch=session.git_branch,
        git_head=session.git_head,
        context_version=session.context_version,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[
            MessageInSession(
                id=m.id,
                role=m.role,
                content=m.content,
                tool_calls=m.tool_calls,
                tool_call_id=m.tool_call_id,
                model=m.model,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )


def rename_session(
    db: Session,
    user_id: str,
    session_id: str,
    title: str,
) -> ChatSession | None:
    """Rename a session. Returns None if not found."""
    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
            ChatSession.is_deleted.is_(False),
        )
        .first()
    )
    if not session:
        return None

    session.title = title
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session


def delete_session(
    db: Session,
    user_id: str,
    session_id: str,
) -> bool:
    """Soft-delete a session. Returns True if found and deleted."""
    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
            ChatSession.is_deleted.is_(False),
        )
        .first()
    )
    if not session:
        return False

    session.is_deleted = True
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    return True


def auto_title(
    db: Session,
    session_id: str,
    first_user_msg: str,
    first_ai_msg: str,
) -> str | None:
    """
    Generate a short session title from the first exchange using the LLM.

    Returns the generated title, or None on failure.
    """

    try:
        summarizer = llm("summarizer")
        prompt = (
            "Generate a concise chat title (max 6 words) for a conversation that starts with:\n\n"
            f"User: {first_user_msg[:200]}\n"
            f"Assistant: {first_ai_msg[:200]}\n\n"
            "Reply with ONLY the title, no quotes or punctuation."
        )
        response = summarizer.invoke(prompt)
        title = response.content.strip().strip("\"'")[:200]

        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session and title:
            session.title = title
            session.updated_at = datetime.now(timezone.utc)
            db.commit()
            return title
    except Exception:
        pass  # Non-critical — keep default title

    return None
