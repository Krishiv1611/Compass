from agent.ui.commands.models import CommandContext, CommandResult, SlashCommand


class CommandRegistry:
    def __init__(self):
        self._commands: dict[str, SlashCommand] = {}

    def register(self, command: SlashCommand) -> None:
        for name in (command.name, *command.aliases):
            self._commands[name] = command

    async def execute(self, line: str, context: CommandContext) -> CommandResult:
        parts = line.strip().split(maxsplit=1)
        name = parts[0].lower() if parts else ""
        argument = parts[1].strip() if len(parts) > 1 else ""
        command = self._commands.get(name)
        if not command:
            return CommandResult(consumed=False)
        try:
            result = await command.handler(argument, context)
        except Exception as exc:
            return CommandResult(
                consumed=True,
                message=f"Command failed: {exc}",
                status="failed",
            )
        if result.status not in {"performed", "waiting", "unavailable", "failed"}:
            return CommandResult(
                consumed=True,
                message="Command failed: invalid command status.",
                status="failed",
            )
        return result

    def help_text(self) -> str:
        commands = {command.name: command.help for command in self._commands.values()}
        return "\n".join(f"{name}  {help_text}" for name, help_text in sorted(commands.items()))
