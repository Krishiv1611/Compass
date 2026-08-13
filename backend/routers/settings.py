"""User preferences and hosted MCP policy endpoints."""

import time

import anyio
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.auth.dependencies import get_current_user
from backend.db import get_db, SessionLocal
from backend.models.user import User
from backend.schemas.settings import (
    ProviderTestRequest,
    ProviderTestResponse,
    UserPreferences,
    UserPreferencesUpdate,
    public_preferences,
)
from backend.services.provider_credentials import (
    migrate_legacy_credential,
    remove_provider_credential,
    resolve_provider_config,
    store_provider_credential,
    validate_provider_model,
)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=UserPreferences)
def get_settings(current_user: User = Depends(get_current_user)):
    preferences = migrate_legacy_credential(current_user.preferences or {})
    return public_preferences(preferences)


@router.put("", response_model=UserPreferences)
def update_settings(
    body: UserPreferencesUpdate,
    current_user: User = Depends(get_current_user),
):
    try:
        provider, model = validate_provider_model(body.llm_provider, body.model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    next_preferences = migrate_legacy_credential(current_user.preferences or {})
    next_preferences.update(body.model_dump(exclude={"llm_api_key"}))
    next_preferences["llm_provider"] = provider
    next_preferences["model"] = model
    if body.llm_api_key:
        next_preferences = store_provider_credential(
            next_preferences,
            provider,
            body.llm_api_key,
        )
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.preferences = next_preferences
        db.commit()
        db.refresh(user)
        return public_preferences(user.preferences or {})


@router.delete("/credentials/{provider}", response_model=UserPreferences)
def delete_provider_credential(
    provider: str,
    current_user: User = Depends(get_current_user),
):
    try:
        preferences = remove_provider_credential(
            current_user.preferences or {},
            provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == current_user.id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        user.preferences = preferences
        db.commit()
        db.refresh(user)
        return public_preferences(user.preferences or {})


@router.post("/provider-test", response_model=ProviderTestResponse)
async def test_provider_credential(
    body: ProviderTestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    preferences = migrate_legacy_credential(current_user.preferences or {})
    db.close()
    preferences["llm_provider"] = body.provider
    preferences["model"] = body.model
    try:
        validate_provider_model(body.provider, body.model)
        if body.api_key:
            preferences = store_provider_credential(
                preferences,
                body.provider,
                body.api_key,
            )
        resolved = resolve_provider_config(preferences)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    started_at = time.perf_counter()
    error = None
    success = False
    try:
        from agent.llm import llm

        model = llm(
            "executor",
            api_key=resolved.api_key,
            provider=resolved.provider,
            model=resolved.model,
        )
        with anyio.fail_after(15):
            await anyio.to_thread.run_sync(
                model.invoke,
                "Reply with OK",
                abandon_on_cancel=True,
            )
        success = True
    except Exception as exc:
        error = str(exc).replace(resolved.api_key, "[redacted]")[:300]
    return ProviderTestResponse(
        provider=resolved.provider,
        model=resolved.model,
        success=success,
        latency_ms=round((time.perf_counter() - started_at) * 1000, 1),
        error=error,
    )


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
