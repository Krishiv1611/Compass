from agent.ui.commands.models import CommandContext, CommandResult, SlashCommand


async def history(_argument: str, context: CommandContext) -> CommandResult:
    if not context.workflow:
        return CommandResult(True, "History is unavailable without an active workflow.")
    state = await context.workflow.aget_state(context.run_config)
    messages = (state.values or {}).get("messages", []) if state else []
    lines = [str(getattr(message, "content", "")) for message in messages]
    return CommandResult(True, "Conversation history:\n" + "\n".join(lines))


COMMANDS = [SlashCommand("/history", (), "Show checkpoint conversation history", history)]
