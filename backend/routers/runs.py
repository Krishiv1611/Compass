"""Agent run history and cooperative cancellation."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from backend.auth.dependencies import get_current_user
from backend.db import get_db
from backend.models.run import AgentRun
from backend.models.user import User
from backend.services.ownership import owned_session
from agent.runtime.diagnostics import capability_report, timing_report
from backend.schemas.settings import public_preferences

router = APIRouter(prefix="/sessions/{session_id}/runs", tags=["runs"])


def serialize_run_event(event) -> dict:
    """Restore the canonical StreamEvent shape stored by RunEventBatcher."""
    if isinstance(event.content, dict):
        payload = dict(event.content)
    else:
        payload = {"content": event.content} if event.content is not None else {}
    payload["id"] = event.id
    payload.setdefault("type", event.event_type)
    payload["created_at"] = event.created_at
    return payload


def _run_diagnostics(run: AgentRun) -> dict:
    metrics: dict | None = None
    for event in reversed(run.events):
        payload = event.content if isinstance(event.content, dict) else {}
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        if event.event_type == "usage":
            metrics = data
            break
        if event.event_type == "done" and isinstance(data.get("metrics"), dict):
            metrics = data["metrics"]
            break
    return timing_report(metrics or run.token_usage or {})


@router.get("")
def get_session_runs(
    session_id: str,
    cursor: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owned_session(db, session_id, str(current_user.id))
    query = (
        db.query(AgentRun)
        .options(selectinload(AgentRun.events))
        .filter(AgentRun.session_id == session_id)
    )
    if cursor:
        cursor_run = (
            db.query(AgentRun)
            .filter(
                AgentRun.id == cursor,
                AgentRun.session_id == session_id,
            )
            .first()
        )
        if cursor_run is None:
            raise HTTPException(status_code=400, detail="Invalid run cursor")
        query = query.filter(
            or_(
                AgentRun.started_at < cursor_run.started_at,
                (
                    (AgentRun.started_at == cursor_run.started_at)
                    & (AgentRun.id < cursor_run.id)
                ),
            )
        )
    page = query.order_by(
        AgentRun.started_at.desc(),
        AgentRun.id.desc(),
    ).limit(limit + 1).all()
    has_more = len(page) > limit
    runs = page[:limit]
    items = [
        {
            "id": run.id,
            "status": run.status,
            "started_at": run.started_at,
            "ended_at": run.ended_at,
            "token_usage": run.token_usage,
            "diagnostics": _run_diagnostics(run),
            "event_count": len(run.events),
            "events": [serialize_run_event(event) for event in run.events],
        }
        for run in runs
    ]
    preferences = public_preferences(current_user.preferences or {}).model_dump()
    capabilities = capability_report({
        **preferences,
        "execution_target": "web",
        "database_enabled": True,
        "mcp_enabled": False,
        "custom_tools.enabled": False,
        "shell_enabled": False,
    })
    return {
        "items": items,
        "next_cursor": runs[-1].id if has_more and runs else None,
        "capabilities": capabilities,
    }


@router.post("/{run_id}/cancel")
def cancel_session_run(
    session_id: str,
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owned_session(db, session_id, str(current_user.id))
    run = db.query(AgentRun).filter(
        AgentRun.id == run_id,
        AgentRun.session_id == session_id,
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status == "running":
        from backend.services.run_manager import cancel_agent_run

        cancel_agent_run(run_id)
        run.status = "cancelled"
        from datetime import datetime, timezone

        run.ended_at = datetime.now(timezone.utc)
        db.commit()
    return {"id": run_id, "status": run.status}
