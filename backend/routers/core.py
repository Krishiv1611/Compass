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
    llm_provider: str = "openrouter"
    llm_api_key: str = ""
    language: str = "en"
    safe_mode: bool = False
    fast_mode: bool = False
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


# ─── MCP Settings Endpoints ────────────────────────────────────────────────────────

import os
import json
from pydantic import BaseModel, Field

MCP_CONFIG_FILE = os.path.join(os.getcwd(), ".compass", "mcp_servers.json")

class McpServerConfig(BaseModel):
    command: str
    args: List[str] = []
    env: dict[str, str] = {}

class McpConfig(BaseModel):
    mcpServers: dict[str, McpServerConfig] = {}

@router.get("/settings/mcp-servers")
def get_mcp_servers(current_user: User = Depends(get_current_user)):
    """Return the current MCP server configuration."""
    if not os.path.exists(MCP_CONFIG_FILE):
        return {"mcpServers": {}}
    try:
        with open(MCP_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"mcpServers": {}}

@router.post("/settings/mcp-servers")
def update_mcp_servers(
    config: McpConfig,
    current_user: User = Depends(get_current_user)
):
    """Update the MCP server configuration."""
    os.makedirs(os.path.dirname(MCP_CONFIG_FILE), exist_ok=True)
    with open(MCP_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, indent=2)
    return config

class McpTestRequest(BaseModel):
    name: str
    config: McpServerConfig

@router.post("/settings/mcp-servers/test")
def test_mcp_server(
    request: McpTestRequest,
    current_user: User = Depends(get_current_user)
):
    """Test connectivity to an MCP server."""
    # To truly test an MCP server, we'd need to spin up an MCPClient for it.
    # For now, we will perform a basic validation that the command exists
    # and we can invoke it. A true test requires langchain_mcp_adapters logic.
    import shutil
    import subprocess
    cmd = request.config.command
    if not shutil.which(cmd):
        raise HTTPException(status_code=400, detail=f"Command '{cmd}' not found on system path.")
    
    # Optional: We could run the command briefly, but standard MCP servers block on stdin.
    # We will just return success if the binary exists, as deep protocol testing is complex.
    return {"status": "ok", "message": f"'{cmd}' is available and valid."}


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

