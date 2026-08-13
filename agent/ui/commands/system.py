import importlib.util
import os
from pathlib import Path

from agent.ui.commands.models import CommandContext, CommandResult, SlashCommand


async def schedule(_argument: str, _context: CommandContext) -> CommandResult:
    return CommandResult(True, "Scheduling is not available in the TUI yet; no task was created.")


async def doctor(_argument: str, context: CommandContext) -> CommandResult:
    checks = [
        f"agent imports: {'ok' if importlib.util.find_spec('agent') else 'missing'}",
        f"workflow: {'active' if context.workflow else 'not active'}",
        f"provider credential: {'configured' if context.settings.get('has_llm_api_key') else 'missing'}",
        f"MCP config: {'found' if Path('mcp_servers.json').exists() else 'not found'}",
        f"workspace writable: {'yes' if os.access(Path.cwd(), os.W_OK) else 'no'}",
        f"web URL: {context.settings.get('web_url') or 'http://localhost:5173'}",
    ]
    return CommandResult(True, "Doctor:\n" + "\n".join(checks))


COMMANDS = [
    SlashCommand("/schedule", (), "Report scheduling availability", schedule),
    SlashCommand("/doctor", (), "Inspect local Compass configuration", doctor),
]
