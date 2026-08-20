"""Scoped skill discovery and safe paths for persisted skill definitions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from agent.skills.models import SkillDefinition

SKILL_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class SkillNameError(ValueError):
    """Raised when a supplied skill name cannot name a skill file."""


@dataclass(frozen=True)
class SkillScope:
    """Directories visible to one local or web skill registry."""

    global_dir: Path
    workspace_dir: Path | None = None
    user_dir: Path | None = None

    @classmethod
    def local(
        cls, global_dir: Path | None = None, workspace_dir: Path | None = None
    ) -> SkillScope:
        return cls(
            global_dir=(global_dir or Path.home() / ".compass" / "skills").resolve(),
            workspace_dir=(workspace_dir or Path.cwd() / ".compass" / "skills").resolve(),
        )

    @classmethod
    def web(cls, global_dir: Path, user_id: str) -> SkillScope:
        root = global_dir.resolve()
        user_dir = _safe_child_path(root / "users", str(user_id))
        return cls(global_dir=root, user_dir=user_dir)

    @property
    def writable_dir(self) -> Path:
        if self.user_dir is not None:
            return self.user_dir
        if self.workspace_dir is not None:
            return self.workspace_dir
        raise ValueError("The global skill directory is read-only.")

    def directories(self) -> list[tuple[str, Path]]:
        result = [("global", self.global_dir)]
        if self.workspace_dir is not None:
            result.append(("workspace", self.workspace_dir))
        if self.user_dir is not None:
            result.append(("user", self.user_dir))
        return result


def _safe_child_path(parent: Path, name: str) -> Path:
    if not name or name in {".", ".."} or Path(name).name != name:
        raise ValueError("Invalid path component")
    resolved_parent = parent.resolve()
    candidate = (resolved_parent / name).resolve()
    try:
        candidate.relative_to(resolved_parent)
    except ValueError as exc:
        raise ValueError("Path escapes its permitted skill directory") from exc
    return candidate


def validate_skill_name(name: str) -> str:
    if not isinstance(name, str) or not SKILL_NAME.fullmatch(name):
        raise SkillNameError(
            "Skill names must contain lowercase letters, numbers, and hyphens only."
        )
    return name


def safe_skill_path(scope: SkillScope, name: str) -> Path:
    """Return a validated writable skill path beneath this scope only."""
    return _safe_child_path(scope.writable_dir, f"{validate_skill_name(name)}.md")


def parse_skill_file(file_path: Path, *, source: str) -> SkillDefinition | None:
    """Parse one skill file, retaining only a display-safe source label."""
    try:
        content = file_path.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        if len(parts) < 3:
            print(f"[skills] Error loading {file_path.name}: Missing YAML frontmatter block")
            return None

        try:
            metadata = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError as exc:
            print(f"[skills] Error parsing YAML in {file_path.name}: {exc}")
            return None

        name = metadata.get("name")
        description = metadata.get("description")
        if not name or not description:
            print(
                f"[skills] Error loading {file_path.name}: Missing 'name' or 'description' in frontmatter"
            )
            return None
        validate_skill_name(str(name))

        return SkillDefinition(
            name=str(name),
            description=str(description),
            system_prompt=parts[2].strip(),
            allowed_tools=metadata.get("allowed_tools"),
            model=metadata.get("model"),
            max_turns=metadata.get("max_turns", 8),
            source_path=source,
        )
    except (OSError, SkillNameError, ValueError) as exc:
        print(f"[skills] Failed to load {file_path.name}: {exc}")
        return None


def discover_skills(scope: SkillScope | None = None) -> list[SkillDefinition]:
    """Discover only global and caller-specific skills in ``scope``."""
    scope = scope or SkillScope.local()
    skills_map: dict[str, SkillDefinition] = {}
    for source, search_dir in scope.directories():
        if not search_dir.is_dir():
            continue
        resolved_search_dir = search_dir.resolve()
        for file_path in search_dir.glob("*.md"):
            try:
                resolved_file_path = file_path.resolve()
                resolved_file_path.relative_to(resolved_search_dir)
            except (OSError, RuntimeError, ValueError):
                continue
            skill = parse_skill_file(resolved_file_path, source=source)
            if skill:
                skills_map[skill.name] = skill
    return list(skills_map.values())
