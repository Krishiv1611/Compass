import yaml
from langchain_core.tools import tool

from agent.skills.loader import SkillNameError, safe_skill_path
from agent.skills.registry import current_skill_scope, skill_registry


@tool
def create_skill(
    name: str,
    description: str,
    system_prompt: str,
    allowed_tools: str = "",
    model: str = "",
    max_turns: int = 8,
) -> str:
    """
    Create a new skill in the current workspace or user scope.
    Only call this when the user explicitly asks to create/register a new skill.

    Args:
        name: Skill name (kebab-case, e.g., 'code-review')
        description: Short description of what the skill does
        system_prompt: The full system prompt for the sub-agent. Use $ARGUMENTS
                       as a placeholder for user-provided arguments.
        allowed_tools: Comma-separated tool names (e.g., 'read_file,grep_search').
                       Leave empty for all tools.
        model: Optional model override. Leave empty for default.
        max_turns: Max turns for the sub-agent (default: 8).

    Returns:
        Success message with a display-safe source label.
    """
    scope = current_skill_scope()
    try:
        file_path = safe_skill_path(scope, name)
    except SkillNameError as exc:
        return f"Skill not created: {exc}"

    # Build YAML frontmatter
    frontmatter = {"name": name, "description": description, "max_turns": max_turns}
    if allowed_tools:
        frontmatter["allowed_tools"] = [t.strip() for t in allowed_tools.split(",")]
    if model:
        frontmatter["model"] = model

    # The active scope is a workspace for TUI runs and a user directory for web runs.
    file_path.parent.mkdir(parents=True, exist_ok=True)

    content = f"---\n{yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)}---\n\n{system_prompt}\n"
    file_path.write_text(content, encoding="utf-8")

    skill_registry.reload()

    source = "user" if scope.user_dir is not None else "workspace"
    return f"✔ Skill '{name}' created in {source} skills\nUse /{name} <args> to invoke it."
