"""Authenticated CRUD API for LangGraph long-term memory."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from agent.tools.memory_tool import delete_memory, list_memories, save_memory
from backend.auth.dependencies import get_current_user
from backend.models.user import User

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryWrite(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    key: str | None = Field(default=None, max_length=160)
    scope: Literal["global", "project"] = "global"
    project_id: str | None = Field(default=None, max_length=512)
    category: str = Field(default="general", max_length=80)
    enabled: bool = True


def _validate_scope(scope: str, project_id: str | None) -> None:
    if scope == "project" and not project_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="project_id is required for project-scoped memory.",
        )


@router.get("")
def get_memory_items(
    scope: Literal["global", "project"] = Query(default="global"),
    project_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    _validate_scope(scope, project_id)
    memories, enabled, error = list_memories(
        str(current_user.id), scope=scope, project_id=project_id
    )
    return {"memories": memories, "enabled": enabled, "error": error}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_memory_item(
    body: MemoryWrite,
    current_user: User = Depends(get_current_user),
):
    _validate_scope(body.scope, body.project_id)
    try:
        return save_memory(
            str(current_user.id),
            body.content,
            key=body.key,
            scope=body.scope,
            project_id=body.project_id,
            category=body.category,
            enabled=body.enabled,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.put("/{memory_key}")
def update_memory_item(
    memory_key: str,
    body: MemoryWrite,
    current_user: User = Depends(get_current_user),
):
    _validate_scope(body.scope, body.project_id)
    try:
        return save_memory(
            str(current_user.id),
            body.content,
            key=memory_key,
            scope=body.scope,
            project_id=body.project_id,
            category=body.category,
            enabled=body.enabled,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.delete("/{memory_key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory_item(
    memory_key: str,
    scope: Literal["global", "project"] = Query(default="global"),
    project_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    _validate_scope(scope, project_id)
    try:
        delete_memory(
            str(current_user.id),
            memory_key,
            scope=scope,
            project_id=project_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
