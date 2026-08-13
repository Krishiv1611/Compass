from agent.ui.commands.context import COMMANDS as CONTEXT_COMMANDS
from agent.ui.commands.integrations import COMMANDS as INTEGRATION_COMMANDS
from agent.ui.commands.registry import CommandRegistry
from agent.ui.commands.session import COMMANDS as SESSION_COMMANDS
from agent.ui.commands.system import COMMANDS as SYSTEM_COMMANDS


def build_registry() -> CommandRegistry:
    registry = CommandRegistry()
    for command in (*SESSION_COMMANDS, *CONTEXT_COMMANDS, *INTEGRATION_COMMANDS, *SYSTEM_COMMANDS):
        registry.register(command)
    return registry


__all__ = ["build_registry", "CommandRegistry"]
