from pathlib import Path

import click

from agent.checkpoints import (
    CheckpointConflictError,
    list_checkpoints,
    preview_restore,
    restore_checkpoint,
)
from agent.ui.commands.models import CommandContext, CommandResult, SlashCommand


async def history(_argument: str, context: CommandContext) -> CommandResult:
    if not context.workflow:
        return CommandResult(True, "History is unavailable without an active workflow.")
    state = await context.workflow.aget_state(context.run_config)
    messages = (state.values or {}).get("messages", []) if state else []
    lines = [str(getattr(message, "content", "")) for message in messages]
    return CommandResult(True, "Conversation history:\n" + "\n".join(lines))


def _thread_id(context: CommandContext) -> str | None:
    value = context.run_config.get("configurable", {}).get("thread_id")
    return str(value) if value else None


def _resolve_checkpoint(root: Path, value: str, context: CommandContext):
    matches = [
        item for item in list_checkpoints(root, thread_id=_thread_id(context))
        if item.id.startswith(value)
    ]
    if len(matches) != 1:
        raise ValueError("Checkpoint ID prefix is missing or ambiguous")
    return matches[0]


async def checkpoints(_argument: str, context: CommandContext) -> CommandResult:
    values = list_checkpoints(
        context.workspace or ".", thread_id=_thread_id(context)
    )
    if not values:
        return CommandResult(True, "No file checkpoints for this task.")
    lines = [
        f"{item.id[:10]} · {item.created_at.isoformat()} · "
        f"{item.label or 'checkpoint'} · {len(item.files)} file(s)"
        for item in values[:20]
    ]
    return CommandResult(True, "File checkpoints:\n" + "\n".join(lines))


async def restore(argument: str, context: CommandContext) -> CommandResult:
    parts = argument.split()
    force = "--force" in parts
    ids = [part for part in parts if part != "--force"]
    if len(ids) != 1:
        return CommandResult(True, "Usage: /restore <checkpoint-id> [--force]")
    root = Path(context.workspace or ".").resolve()
    try:
        checkpoint = _resolve_checkpoint(root, ids[0], context)
    except ValueError as exc:
        return CommandResult(True, str(exc))
    preview = preview_restore(root, checkpoint.id)
    if preview.conflicts and not force:
        return CommandResult(
            True,
            "Restore conflicts: " + ", ".join(preview.conflicts)
            + ". Re-run with --force after reviewing them.",
        )
    summary = ", ".join(preview.changes) or "no file changes"
    if not click.confirm(f"Restore checkpoint {checkpoint.id[:10]} ({summary})?", default=False):
        return CommandResult(True, "Restore cancelled; files were unchanged.")
    try:
        restore_checkpoint(root, checkpoint.id, force=force)
    except CheckpointConflictError as exc:
        return CommandResult(True, "Restore conflicts: " + ", ".join(exc.conflicts))
    return CommandResult(
        True,
        f"Restored {checkpoint.id[:10]}: {summary}",
        {"checkpoint_restored": checkpoint.id, "changed_files": preview.changes},
    )


async def undo(_argument: str, context: CommandContext) -> CommandResult:
    values = list_checkpoints(
        context.workspace or ".", thread_id=_thread_id(context)
    )
    if not values:
        return CommandResult(True, "No file checkpoint is available to undo.")
    return await restore(values[0].id, context)


COMMANDS = [
    SlashCommand("/history", (), "Show checkpoint conversation history", history),
    SlashCommand("/checkpoints", (), "List recoverable file checkpoints", checkpoints),
    SlashCommand("/restore", (), "Preview and restore one checkpoint", restore),
    SlashCommand("/undo", (), "Restore the latest file checkpoint", undo),
]
