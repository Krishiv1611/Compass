"""Small transport objects for TUI slash commands."""

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass(slots=True)
class CommandContext:
    console: Any
    workflow: Any
    run_config: dict
    session_store: Any
    workspace: Any
    settings: dict


@dataclass(slots=True)
class CommandResult:
    consumed: bool
    message: str = ""
    state_updates: dict = field(default_factory=dict)


CommandHandler = Callable[[str, CommandContext], Awaitable[CommandResult]]


@dataclass(frozen=True, slots=True)
class SlashCommand:
    name: str
    aliases: tuple[str, ...]
    help: str
    handler: CommandHandler
