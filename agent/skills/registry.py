from agent.skills.models import SkillDefinition
from agent.skills.loader import discover_skills


class SkillRegistry:
    """
    Singleton that holds all loaded skills.
    Skills are ONLY loaded from SKILL.md files on disk — never auto-created.
    """

    def __init__(self):
        self._skills: dict[str, SkillDefinition] = {}

    def load_all(self) -> int:
        """Scan .compass/skills/ dirs, parse all SKILL.md files. Returns count."""
        skills = discover_skills()
        for skill in skills:
            self._skills[skill.name] = skill
        return len(self._skills)

    def reload(self) -> int:
        """Clear and re-scan. Called by /skills reload."""
        self._skills.clear()
        return self.load_all()

    def get(self, name: str) -> SkillDefinition | None:
        """Exact name lookup. Returns None if not found."""
        return self._skills.get(name)

    def list_skills(self) -> list[SkillDefinition]:
        """Return all registered skills."""
        return list(self._skills.values())

    def get_skill_names_descriptions(self) -> str:
        """Format skill list for injection into planner system prompt."""
        if not self._skills:
            return ""

        lines = []
        for name, skill in self._skills.items():
            lines.append(f"- {name}: {skill.description}")
        return "\n".join(lines)


# Module-level singleton
skill_registry = SkillRegistry()
