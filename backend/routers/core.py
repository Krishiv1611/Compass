"""
Core router — consolidated endpoints for runs, tools, and settings.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List

from backend.db import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.session import ChatSession
from backend.models.run import AgentRun

router = APIRouter(tags=["core"])


# ─── Settings Endpoints ────────────────────────────────────────────────────────

class UserPreferences(BaseModel):
    """User preferences schema."""
    theme: str = "dark"
    model: str = "google/gemma-4-31b-it:free"
    language: str = "en"
    safe_mode: bool = False
    model_config = {"extra": "allow"}

@router.get("/settings", response_model=UserPreferences)
def get_settings(current_user: User = Depends(get_current_user)):
    """Return the current user's preferences."""
    prefs = getattr(current_user, "preferences", None) or {}
    return UserPreferences(**prefs)

@router.put("/settings", response_model=UserPreferences)
def update_settings(
    body: UserPreferences,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the current user's preferences."""
    current_user.preferences = body.model_dump()
    db.commit()
    db.refresh(current_user)
    return UserPreferences(**current_user.preferences)


# ─── Tools Endpoints ──────────────────────────────────────────────────────────

class ToolInfo(BaseModel):
    """Description of an available agent tool."""
    name: str
    description: str
    environment: str = "web"  # "web" or "tui"

@router.get("/tools", response_model=list[ToolInfo])
def list_tools(current_user: User = Depends(get_current_user)):
    """List all available agent tools with their descriptions."""
    from agent.graph.tools_registry import ALL_TOOLS
    # shell_execute runs in TUI only; all others work in web mode
    TUI_ONLY_TOOLS = {"shell_execute"}
    return [
        ToolInfo(
            name=tool.name,
            description=(tool.description or "No description")[:300],
            environment="tui" if tool.name in TUI_ONLY_TOOLS else "web",
        )
        for tool in ALL_TOOLS
        if hasattr(tool, "name")
    ]


# ─── Runs Endpoints ───────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/runs")
def get_session_runs(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all agent runs for a session."""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
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
            ]
        }
        for run in runs
    ]
