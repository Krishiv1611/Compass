import asyncio
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.models.run import AgentRun, RunEvent

_cancel_signals: dict[str, asyncio.Event] = {}


def get_cancel_signal(run_id: str) -> asyncio.Event:
    return _cancel_signals.setdefault(run_id, asyncio.Event())


def cancel_agent_run(run_id: str) -> None:
    get_cancel_signal(run_id).set()


def create_agent_run(db: Session, session_id: str, workspace_id: str | None = None) -> AgentRun:
    """Create a new AgentRun in 'running' state."""
    run = AgentRun(session_id=session_id, workspace_id=workspace_id, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def persist_run_event(db: Session, run_id: str, event_type: str, content: dict | None = None) -> RunEvent:
    """Persist a single event for a run."""
    event = RunEvent(run_id=run_id, event_type=event_type, content=content)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def end_agent_run(db: Session, run_id: str, status: str = "completed", token_usage: dict | None = None):
    """Mark an AgentRun as ended with a given status and optional token usage."""
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if run:
        run.status = status
        run.ended_at = datetime.now(timezone.utc)
        if token_usage:
            run.token_usage = token_usage
        db.commit()
        db.refresh(run)
    if status != "running":
        _cancel_signals.pop(run_id, None)
    return run
