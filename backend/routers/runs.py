"""Agent run history and cooperative cancellation."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.auth.dependencies import get_current_user
from backend.db import get_db
from backend.models.run import AgentRun
from backend.models.session import ChatSession
from backend.models.user import User

router = APIRouter(prefix="/sessions/{session_id}/runs", tags=["runs"])


def _owned_session(db: Session, session_id: str, user_id: str) -> ChatSession:
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id,
        ChatSession.is_deleted.is_(False),
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("")
def get_session_runs(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _owned_session(db, session_id, str(current_user.id))
    runs = db.query(AgentRun).filter(
        AgentRun.session_id == session_id
    ).order_by(AgentRun.started_at.desc()).all()
    return [
        {
            "id": run.id,
            "status": run.status,
            "started_at": run.started_at,
            "ended_at": run.ended_at,
            "token_usage": run.token_usage,
            "event_count": len(run.events),
            "events": [
                {
                    "id": event.id,
                    "type": event.event_type,
                    "content": event.content,
                    "created_at": event.created_at,
                }
                for event in run.events
            ],
        }
        for run in runs
    ]


@router.post("/{run_id}/cancel")
def cancel_session_run(
    session_id: str,
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _owned_session(db, session_id, str(current_user.id))
    run = db.query(AgentRun).filter(
        AgentRun.id == run_id,
        AgentRun.session_id == session_id,
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status == "running":
        from backend.services.run_manager import cancel_agent_run

        cancel_agent_run(run_id)
        run.status = "cancelling"
        db.commit()
    return {"id": run_id, "status": run.status}
