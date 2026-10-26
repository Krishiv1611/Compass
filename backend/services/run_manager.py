import asyncio
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.models.run import AgentRun, RunEvent
from backend.services.run_context import RunContextSnapshot
from backend.services.run_persistence import RUN_STATUSES

_cancel_signals: dict[str, asyncio.Event] = {}


def normalize_run_id(run_id: str) -> str:
    try:
        return str(uuid.UUID(run_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="run_id must be a valid UUID",
        ) from exc


def _validated_run_id(run_id: str) -> str:
    """Backward-compatible alias for callers that only validate a run ID."""
    return normalize_run_id(run_id)


def claim_agent_run(
    db: Session,
    snapshot: RunContextSnapshot,
    requested_run_id: str,
    *,
    resume: bool = False,
) -> AgentRun:
    """Create or resume one run without allowing its session binding to change."""
    run_id = _validated_run_id(requested_run_id)
    existing = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if existing is not None and existing.session_id != snapshot.session_id:
        raise HTTPException(status_code=404, detail="Run not found")

    if resume:
        if existing is None:
            raise HTTPException(status_code=404, detail="Run not found")
        if existing.status != "waiting_for_approval":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Run is not waiting for approval",
            )
        existing.status = "running"
        existing.ended_at = None
        db.commit()
        db.refresh(existing)
        return existing

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="run_id has already been used",
        )

    run = AgentRun(
        id=run_id,
        session_id=snapshot.session_id,
        workspace_id=snapshot.workspace_id,
        project_id=snapshot.project_id,
        context_version=snapshot.context_version,
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def reconcile_interrupted_runs(db: Session) -> int:
    """Mark rows left active by a prior backend process as interrupted."""
    stale_runs = db.query(AgentRun).filter(AgentRun.status == "running").all()
    ended_at = datetime.now(UTC)
    for run in stale_runs:
        run.status = "interrupted"
        run.ended_at = ended_at
    if stale_runs:
        db.commit()
    return len(stale_runs)


def get_cancel_signal(run_id: str) -> asyncio.Event:
    return _cancel_signals.setdefault(run_id, asyncio.Event())


def cancel_agent_run(run_id: str) -> None:
    get_cancel_signal(run_id).set()


def persist_run_event(
    db: Session,
    run_id: str,
    event_type: str,
    content: dict | None = None,
) -> RunEvent:
    """Persist a single event for a run."""
    event = RunEvent(run_id=run_id, event_type=event_type, content=content)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def persist_run_events(
    db: Session,
    run_id: str,
    events: list[tuple[str, dict]],
) -> list[RunEvent]:
    """Persist a batch of meaningful events with one transaction."""
    models = [
        RunEvent(run_id=run_id, event_type=event_type, content=content)
        for event_type, content in events
    ]
    db.add_all(models)
    db.commit()
    return models


def end_agent_run(
    db: Session,
    run_id: str,
    status: str = "completed",
    token_usage: dict | None = None,
):
    """Mark an AgentRun as ended with a supported terminal status."""
    if status not in RUN_STATUSES - {"running"}:
        raise ValueError(f"Unsupported run status: {status}")
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if run:
        run.status = status
        run.ended_at = datetime.now(UTC)
        if token_usage:
            run.token_usage = token_usage
        db.commit()
        db.refresh(run)
    _cancel_signals.pop(run_id, None)
    return run


def active_run_ids_for_session(db: Session, session_id: str) -> list[str]:
    """Return only runs which may still have an in-process agent task."""
    return [
        run_id
        for (run_id,) in (
            db.query(AgentRun.id)
            .filter(AgentRun.session_id == session_id, AgentRun.status == "running")
            .all()
        )
    ]
