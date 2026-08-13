from agent.ui.commands.models import CommandContext, CommandResult, SlashCommand


async def model(_argument: str, context: CommandContext) -> CommandResult:
    provider = context.settings.get("llm_provider") or "not configured"
    model_name = context.settings.get("model") or "not configured"
    return CommandResult(True, f"Active provider: {provider}\nActive model: {model_name}")


COMMANDS = [SlashCommand("/model", (), "Show active provider and model", model)]
