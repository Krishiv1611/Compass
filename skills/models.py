from dataclasses import dataclass
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


@dataclass
class SkillDefinition:
    """Definition of a skill loaded from a SKILL.md file."""
    name: str                           # "code-review"
    description: str                    # Human-readable description
    system_prompt: str                  # Body of SKILL.md (after frontmatter)
    allowed_tools: list[str] | None     # Tool whitelist. None = all tools
    model: str | None                   # Override model. None = executor default
    max_turns: int                      # Sub-agent turn limit (default: 8)
    source_path: str                    # Path to the SKILL.md file

    @property
    def slash_command(self) -> str:
        """Returns the slash command for this skill (e.g., '/code-review')."""
        return f"/{self.name}"


class SubAgentState(TypedDict):
    """Lightweight state for ephemeral sub-agent graphs."""
    messages: Annotated[list[BaseMessage], add_messages]
    turn_count: int
    is_done: bool


@dataclass
class SkillResult:
    """Result returned by a sub-agent execution."""
    skill_name: str
    output: str
    tool_calls_made: int
    turns_used: int
