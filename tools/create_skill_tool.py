import yaml
from pathlib import Path

from langchain_core.tools import tool

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
    Create a new SKILL.md file in .compass/skills/.
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
        Success message with the skill file path.
    """
    # Build YAML frontmatter
    frontmatter = {
        "name": name, 
        "description": description, 
        "max_turns": max_turns
    }
    if allowed_tools:
        frontmatter["allowed_tools"] = [t.strip() for t in allowed_tools.split(",")]
    if model:
        frontmatter["model"] = model

    # Write SKILL.md
    skills_dir = Path.cwd() / ".compass" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    file_path = skills_dir / f"{name}.md"
    
    content = f"---\n{yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)}---\n\n{system_prompt}\n"
    file_path.write_text(content, encoding="utf-8")

    # Hot-reload into registry
    from skills.registry import skill_registry
    skill_registry.reload()

    return f"✔ Skill '{name}' created at {file_path}\nUse /{name} <args> to invoke it."
