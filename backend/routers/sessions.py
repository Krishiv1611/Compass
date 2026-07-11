"""
Session CRUD router.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.auth.dependencies import get_current_user
from backend.db import get_db
from backend.models.user import User
from backend.schemas.session import (
    SessionCreate,
    SessionRename,
    SessionSummary,
    SessionDetail,
)
from backend.services import session_manager

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionSummary])
def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the current user's chat sessions (paginated, newest first)."""
    return session_manager.list_sessions(db, current_user.id, page, page_size)


@router.post("", response_model=SessionDetail, status_code=status.HTTP_201_CREATED)
def create_session(
    body: SessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new chat session."""
    s = session_manager.create_session(db, current_user.id, body.title)
    return SessionDetail(
        id=s.id,
        title=s.title,
        thread_id=s.thread_id,
        created_at=s.created_at,
        updated_at=s.updated_at,
        messages=[],
    )


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a session with its full message history."""
    detail = session_manager.get_session_detail(db, current_user.id, session_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return detail


@router.patch("/{session_id}", response_model=SessionDetail)
def rename_session(
    session_id: str,
    body: SessionRename,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Rename a session."""
    s = session_manager.rename_session(db, current_user.id, session_id, body.title)
    if not s:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    # Re-fetch full detail for consistent response
    return session_manager.get_session_detail(db, current_user.id, session_id)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft-delete a session."""
    deleted = session_manager.delete_session(db, current_user.id, session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return None
