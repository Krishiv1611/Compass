import yaml
from pathlib import Path

from skills.models import SkillDefinition

def parse_skill_file(file_path: Path) -> SkillDefinition | None:
    """
    Parse a SKILL.md file into a SkillDefinition.
    Returns None if parsing fails.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        
        # Split on YAML frontmatter delimiters
        # Format expects:
        # ---
        # name: "..."
        # ---
        # body
        parts = content.split("---", 2)
        if len(parts) < 3:
            print(f"[skills] Error loading {file_path.name}: Missing YAML frontmatter block")
            return None
            
        frontmatter_text = parts[1]
        body_text = parts[2].strip()
        
        # Parse YAML
        try:
            metadata = yaml.safe_load(frontmatter_text) or {}
        except yaml.YAMLError as e:
            print(f"[skills] Error parsing YAML in {file_path.name}: {e}")
            return None
            
        # Validate required fields
        name = metadata.get("name")
        description = metadata.get("description")
        
        if not name or not description:
            print(f"[skills] Error loading {file_path.name}: Missing 'name' or 'description' in frontmatter")
            return None
            
        return SkillDefinition(
            name=str(name),
            description=str(description),
            system_prompt=body_text,
            allowed_tools=metadata.get("allowed_tools"),
            model=metadata.get("model"),
            max_turns=metadata.get("max_turns", 8),
            source_path=str(file_path),
        )
    except Exception as e:
        print(f"[skills] Failed to load {file_path}: {e}")
        return None

def discover_skills() -> list[SkillDefinition]:
    """
    Scan global (~/.compass/skills) and local (./.compass/skills) directories for SKILL.md files.
    Local overrides global.
    """
    skills_map: dict[str, SkillDefinition] = {}
    
    search_dirs = [
        Path.home() / ".compass" / "skills",
        Path.cwd() / ".compass" / "skills"
    ]
    
    for search_dir in search_dirs:
        if not search_dir.exists() or not search_dir.is_dir():
            continue
            
        for file_path in search_dir.glob("*.md"):
            skill = parse_skill_file(file_path)
            if skill:
                # Local will overwrite global since local is checked second
                skills_map[skill.name] = skill
                
    return list(skills_map.values())
