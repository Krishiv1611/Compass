"""User preferences and hosted MCP policy endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.auth.dependencies import get_current_user
from backend.models.user import User

router = APIRouter(prefix="/settings", tags=["settings"])


class UserPreferences(BaseModel):
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


@router.get("", response_model=UserPreferences)
def get_settings(current_user: User = Depends(get_current_user)):
    prefs = getattr(current_user, "preferences", None) or {}
    return UserPreferences(
        **prefs,
        has_llm_api_key=bool(prefs.get("llm_api_key_encrypted")),
    )


@router.put("", response_model=UserPreferences)
def update_settings(
    body: UserPreferencesUpdate,
    current_user: User = Depends(get_current_user),
):
    from backend.auth.credentials import encrypt_credential
    from backend.db import SessionLocal

    existing = dict(current_user.preferences or {})
    next_preferences = body.model_dump(exclude={"llm_api_key"})
    if body.llm_api_key:
        next_preferences["llm_api_key_encrypted"] = encrypt_credential(body.llm_api_key)
    elif existing.get("llm_api_key_encrypted"):
        next_preferences["llm_api_key_encrypted"] = existing["llm_api_key_encrypted"]
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.preferences = next_preferences
        db.commit()
        db.refresh(user)
        return UserPreferences(
            **(user.preferences or {}),
            has_llm_api_key=bool((user.preferences or {}).get("llm_api_key_encrypted")),
        )
    finally:
        db.close()


class McpServerConfig(BaseModel):
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


class McpConfig(BaseModel):
    mcpServers: dict[str, McpServerConfig] = Field(default_factory=dict)


@router.get("/mcp-servers")
def get_mcp_servers(current_user: User = Depends(get_current_user)):
    return {
        "mcpServers": {},
        "managed": True,
        "message": "Hosted MCP capabilities are server-managed. Configure command MCP servers in the local TUI.",
    }


@router.post("/mcp-servers")
def update_mcp_servers(
    config: McpConfig,
    current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Hosted workspaces cannot configure local MCP commands. Use the TUI.",
    )


class McpTestRequest(BaseModel):
    name: str
    config: McpServerConfig


@router.post("/mcp-servers/test")
def test_mcp_server(
    request: McpTestRequest,
    current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Hosted workspaces cannot test local MCP commands. Use the TUI.",
    )
