"""CRUD API for reusable skill definitions."""

from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from agent.skills.loader import (
    SkillNameError,
    SkillScope,
    safe_skill_path,
    validate_skill_name,
)
from agent.skills.registry import SkillRegistry
from backend.auth.dependencies import get_current_user
from backend.config import settings
from backend.models.user import User

router = APIRouter(prefix="/skills", tags=["skills"])


def configured_skill_root() -> Path:
    return settings.skills_root.resolve()


class SkillWrite(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=500)
    system_prompt: str = Field(min_length=1, max_length=30000)
    allowed_tools: list[str] = Field(default_factory=list)
    model: str = ""
    max_turns: int = Field(default=8, ge=1, le=30)


class SkillResponse(BaseModel):
    name: str
    description: str
    system_prompt: str
    allowed_tools: list[str] | None = None
    model: str | None = None
    max_turns: int = 8
    source_path: str = ""


def _safe_name(name: str) -> str:
    try:
        return validate_skill_name(name)
    except SkillNameError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


def _registry_for_user(user: User) -> SkillRegistry:
    registry = SkillRegistry(SkillScope.web(configured_skill_root(), str(user.id)))
    registry.load_all()
    return registry


@router.get("", response_model=list[SkillResponse])
def list_skills(current_user: User = Depends(get_current_user)):
    skill_registry = _registry_for_user(current_user)
    return [
        SkillResponse(
            name=skill.name,
            description=skill.description,
            system_prompt=skill.system_prompt,
            allowed_tools=skill.allowed_tools,
            model=skill.model,
            max_turns=skill.max_turns,
            source_path=skill.source_path,
        )
        for skill in skill_registry.list_skills()
    ]


@router.post("", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
def create_skill(
    body: SkillWrite,
    current_user: User = Depends(get_current_user),
):
    name = _safe_name(body.name)
    scope = SkillScope.web(configured_skill_root(), str(current_user.id))
    file_path = safe_skill_path(scope, name)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter: dict = {
        "name": name,
        "description": body.description,
        "max_turns": body.max_turns,
    }
    if body.allowed_tools:
        frontmatter["allowed_tools"] = body.allowed_tools
    if body.model:
        frontmatter["model"] = body.model
    file_path.write_text(
        f"---\n{yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)}---\n\n{body.system_prompt}\n",
        encoding="utf-8",
    )
    return SkillResponse(
        name=name,
        description=body.description,
        system_prompt=body.system_prompt,
        allowed_tools=body.allowed_tools or None,
        model=body.model or None,
        max_turns=body.max_turns,
        source_path="user",
    )


@router.delete("/{skill_name}")
def delete_skill(
    skill_name: str,
    current_user: User = Depends(get_current_user),
):
    name = _safe_name(skill_name)
    file_path = safe_skill_path(
        SkillScope.web(configured_skill_root(), str(current_user.id)), name
    )
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found.")
    file_path.unlink()
    return {"status": "ok", "message": f"Skill '{name}' deleted."}
