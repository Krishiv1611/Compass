"""Request-scoped registries for skills visible to an agent turn."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token

from agent.skills.loader import SkillScope, discover_skills
from agent.skills.models import SkillDefinition


class SkillRegistry:
    def __init__(self, scope: SkillScope | None = None):
        self.scope = scope or SkillScope.local()
        self._skills: dict[str, SkillDefinition] = {}

    def load_all(self) -> int:
        self._skills = {skill.name: skill for skill in discover_skills(self.scope)}
        return len(self._skills)

    def reload(self) -> int:
        return self.load_all()

    def get(self, name: str) -> SkillDefinition | None:
        return self._skills.get(name)

    def list_skills(self) -> list[SkillDefinition]:
        return list(self._skills.values())

    def get_skill_names_descriptions(self) -> str:
        return "\n".join(
            f"- {name}: {skill.description}" for name, skill in self._skills.items()
        )


_active_scope: ContextVar[SkillScope | None] = ContextVar("active_skill_scope", default=None)
_active_registry: ContextVar[SkillRegistry | None] = ContextVar(
    "active_skill_registry", default=None
)


def current_skill_scope() -> SkillScope:
    return _active_scope.get() or SkillScope.local()


def get_skill_registry(scope: SkillScope | None = None) -> SkillRegistry:
    requested_scope = scope or current_skill_scope()
    registry = _active_registry.get()
    if registry is None or registry.scope != requested_scope:
        registry = SkillRegistry(requested_scope)
        _active_registry.set(registry)
    return registry


@contextmanager
def skill_scope(scope: SkillScope):
    """Bind a fresh registry to a web request or local agent run."""
    scope_token: Token[SkillScope | None] = _active_scope.set(scope)
    registry = SkillRegistry(scope)
    registry.load_all()
    registry_token: Token[SkillRegistry | None] = _active_registry.set(registry)
    try:
        yield
    finally:
        _active_registry.reset(registry_token)
        _active_scope.reset(scope_token)


class _ScopedRegistry:
    """Compatibility facade that resolves the real registry for this request."""

    def load_all(self) -> int:
        return get_skill_registry().load_all()

    def reload(self) -> int:
        return get_skill_registry().reload()

    def get(self, name: str) -> SkillDefinition | None:
        return get_skill_registry().get(name)

    def list_skills(self) -> list[SkillDefinition]:
        return get_skill_registry().list_skills()

    def get_skill_names_descriptions(self) -> str:
        return get_skill_registry().get_skill_names_descriptions()


skill_registry = _ScopedRegistry()
