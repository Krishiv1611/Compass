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
    """Safe preferences returned to the browser."""
    theme: str = "dark"
    model: str = "google/gemma-4-31b-it:free"
    llm_provider: str = "openrouter"
    language: str = "en"
    safe_mode: bool = False
    fast_mode: bool = False
    has_llm_api_key: bool = False
    model_config = {"extra": "ignore"}


class UserPreferencesUpdate(BaseModel):
    theme: str = "dark"
    model: str = "google/gemma-4-31b-it:free"
    llm_provider: str = "openrouter"
    llm_api_key: str | None = None
    language: str = "en"
    safe_mode: bool = False
    fast_mode: bool = False

@router.get("/settings", response_model=UserPreferences)
def get_settings(current_user: User = Depends(get_current_user)):
    """Return the current user's preferences."""
    prefs = getattr(current_user, "preferences", None) or {}
    return UserPreferences(
        **prefs,
        has_llm_api_key=bool(prefs.get("llm_api_key_encrypted")),
    )

@router.put("/settings", response_model=UserPreferences)
def update_settings(
    body: UserPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the current user's preferences."""
    from backend.auth.credentials import encrypt_credential

    existing = dict(current_user.preferences or {})
    next_preferences = body.model_dump(exclude={"llm_api_key"})
    if body.llm_api_key:
        next_preferences["llm_api_key_encrypted"] = encrypt_credential(body.llm_api_key)
    elif existing.get("llm_api_key_encrypted"):
        next_preferences["llm_api_key_encrypted"] = existing["llm_api_key_encrypted"]
    current_user.preferences = next_preferences
    db.commit()
    db.refresh(current_user)
    return UserPreferences(
        **current_user.preferences,
        has_llm_api_key=bool(current_user.preferences.get("llm_api_key_encrypted")),
    )


# ─── MCP Settings Endpoints ────────────────────────────────────────────────────────

class McpServerConfig(BaseModel):
    """Legacy local MCP shape, retained only for a clear rejected-request contract."""
    command: str
    args: List[str] = []
    env: dict[str, str] = {}


class McpConfig(BaseModel):
    mcpServers: dict[str, McpServerConfig] = {}

@router.get("/settings/mcp-servers")
def get_mcp_servers(current_user: User = Depends(get_current_user)):
    """Expose only managed MCP capability status to hosted web clients.

    Local command-based MCP remains a TUI/project configuration concern. Letting a
    browser user submit an executable command here would turn the web settings page
    into a remote process-launch surface.
    """
    return {
        "mcpServers": {},
        "managed": True,
        "message": "MCP capabilities are managed by this workspace. Configure local command MCP servers in the TUI.",
    }

@router.post("/settings/mcp-servers")
def update_mcp_servers(
    config: McpConfig,
    current_user: User = Depends(get_current_user)
):
    """Reject arbitrary executable MCP configuration in the hosted web product."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Hosted workspaces cannot configure local MCP commands. Use the TUI for local MCP configuration.",
    )

class McpTestRequest(BaseModel):
    name: str
    config: McpServerConfig

@router.post("/settings/mcp-servers/test")
def test_mcp_server(
    request: McpTestRequest,
    current_user: User = Depends(get_current_user)
):
    """Reject local executable probes from the hosted web product."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Hosted workspaces cannot test local MCP commands. Use the TUI for local MCP configuration.",
    )


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


# ─── Skills Endpoints ────────────────────────────────────────────────────────

import yaml
from pathlib import Path as PPath

SKILLS_DIR = PPath.cwd() / ".compass" / "skills"


class SkillCreateRequest(BaseModel):
    name: str
    description: str
    system_prompt: str
    allowed_tools: list[str] = []
    model: str = ""
    max_turns: int = 8


class SkillResponse(BaseModel):
    name: str
    description: str
    system_prompt: str
    allowed_tools: list[str] | None = None
    model: str | None = None
    max_turns: int = 8
    source_path: str = ""


@router.get("/skills", response_model=list[SkillResponse])
def list_skills(current_user: User = Depends(get_current_user)):
    """List all registered skills."""
    from agent.skills.registry import skill_registry
    skill_registry.reload()
    skills = skill_registry.list_skills()
    return [
        SkillResponse(
            name=s.name,
            description=s.description,
            system_prompt=s.system_prompt,
            allowed_tools=s.allowed_tools,
            model=s.model,
            max_turns=s.max_turns,
            source_path=s.source_path,
        )
        for s in skills
    ]


@router.post("/skills", response_model=SkillResponse)
def create_skill(
    body: SkillCreateRequest,
    current_user: User = Depends(get_current_user),
):
    """Create a new skill by writing a SKILL.md file."""
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    file_path = SKILLS_DIR / f"{body.name}.md"

    # Build YAML frontmatter
    frontmatter: dict = {
        "name": body.name,
        "description": body.description,
        "max_turns": body.max_turns,
    }
    if body.allowed_tools:
        frontmatter["allowed_tools"] = body.allowed_tools
    if body.model:
        frontmatter["model"] = body.model

    content = f"---\n{yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)}---\n\n{body.system_prompt}\n"
    file_path.write_text(content, encoding="utf-8")

    # Hot-reload
    from agent.skills.registry import skill_registry
    skill_registry.reload()

    return SkillResponse(
        name=body.name,
        description=body.description,
        system_prompt=body.system_prompt,
        allowed_tools=body.allowed_tools or None,
        model=body.model or None,
        max_turns=body.max_turns,
        source_path=str(file_path),
    )


@router.delete("/skills/{skill_name}")
def delete_skill(
    skill_name: str,
    current_user: User = Depends(get_current_user),
):
    """Delete a skill file and reload the registry."""
    file_path = SKILLS_DIR / f"{skill_name}.md"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found.")
    file_path.unlink()

    from agent.skills.registry import skill_registry
    skill_registry.reload()

    return {"status": "ok", "message": f"Skill '{skill_name}' deleted."}
