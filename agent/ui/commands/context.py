from pathlib import Path

import click

from agent.instructions import (
    append_learned_instruction,
    initialize_compass_file,
    proposed_learned_instruction,
)
from agent.checkpoints import create_checkpoint, seal_checkpoint
from agent.ui.commands.models import CommandContext, CommandResult, SlashCommand


async def model(_argument: str, context: CommandContext) -> CommandResult:
    provider = context.settings.get("llm_provider") or "not configured"
    model_name = context.settings.get("model") or "not configured"
    return CommandResult(True, f"Active provider: {provider}\nActive model: {model_name}")


async def init(argument: str, context: CommandContext) -> CommandResult:
    force = argument.strip() == "--force"
    if argument.strip() not in {"", "--force"}:
        return CommandResult(True, "Usage: /init [--force]")
    root = Path(context.workspace or ".").resolve()
    target = root / "COMPASS.md"
    if target.exists() and not force:
        return CommandResult(
            True,
            "COMPASS.md already exists and was not changed. Use /init --force to replace it.",
        )
    approved = False
    if target.exists() and force:
        approved = click.confirm(
            f"Replace existing {target}? This requires write approval.", default=False
        )
        if not approved:
            return CommandResult(True, "Initialization cancelled; COMPASS.md was unchanged.")
    configurable = context.run_config.get("configurable", {})
    checkpoint = create_checkpoint(
        root,
        ["COMPASS.md"],
        workspace_id=str((configurable.get("workspace_context") or {}).get("workspace_id") or "local"),
        thread_id=str(configurable.get("thread_id") or "local"),
        label="Before /init",
    )
    try:
        initialize_compass_file(root, force=force, approved=approved)
    except FileExistsError:
        return CommandResult(True, "COMPASS.md already exists and was not changed.")
    seal_checkpoint(root, checkpoint.id)
    return CommandResult(True, f"Created {target}")


async def learn(argument: str, context: CommandContext) -> CommandResult:
    try:
        addition = proposed_learned_instruction(argument)
    except ValueError:
        return CommandResult(True, "Usage: /learn <one-line instruction>")
    if not click.confirm(
        f"Append this exact line to COMPASS.md?\n\n{addition}", default=False
    ):
        return CommandResult(True, "Learn cancelled; COMPASS.md was unchanged.")
    root = Path(context.workspace or ".").resolve()
    configurable = context.run_config.get("configurable", {})
    checkpoint = create_checkpoint(
        root,
        ["COMPASS.md"],
        workspace_id=str((configurable.get("workspace_context") or {}).get("workspace_id") or "local"),
        thread_id=str(configurable.get("thread_id") or "local"),
        label="Before /learn",
    )
    append_learned_instruction(root, argument, approved=True)
    seal_checkpoint(root, checkpoint.id)
    return CommandResult(True, f"Added to COMPASS.md:\n{addition}")


COMMANDS = [
    SlashCommand("/model", (), "Show active provider and model", model),
    SlashCommand("/init", (), "Create COMPASS.md without overwriting", init),
    SlashCommand("/learn", (), "Approve and append one project instruction", learn),
]
