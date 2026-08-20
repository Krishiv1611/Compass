from pathlib import Path

import click

from agent.checkpoints import (
    CheckpointConflictError,
    list_checkpoints,
    preview_restore,
    restore_checkpoint,
)
from agent.ui.commands.models import CommandContext, CommandResult, SlashCommand
from agent.sessions import copy_thread_state


async def history(_argument: str, context: CommandContext) -> CommandResult:
    if not context.workflow:
        return CommandResult(
            True,
            "History is unavailable without an active workflow.",
            status="unavailable",
        )
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
        return CommandResult(True, "No file checkpoints for this task.", status="unavailable")
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
        return CommandResult(True, "Usage: /restore <checkpoint-id> [--force]", status="failed")
    root = Path(context.workspace or ".").resolve()
    try:
        checkpoint = _resolve_checkpoint(root, ids[0], context)
    except ValueError as exc:
        return CommandResult(True, str(exc), status="failed")
    preview = preview_restore(root, checkpoint.id)
    if preview.conflicts and not force:
        return CommandResult(
            True,
            "Restore conflicts: " + ", ".join(preview.conflicts)
            + ". Re-run with --force after reviewing them.",
            status="failed",
        )
    summary = ", ".join(preview.changes) or "no file changes"
    if not click.confirm(f"Restore checkpoint {checkpoint.id[:10]} ({summary})?", default=False):
        return CommandResult(True, "Restore cancelled; files were unchanged.", status="waiting")
    try:
        restore_checkpoint(root, checkpoint.id, force=force)
    except CheckpointConflictError as exc:
        return CommandResult(
            True, "Restore conflicts: " + ", ".join(exc.conflicts), status="failed"
        )
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
        return CommandResult(
            True, "No file checkpoint is available to undo.", status="unavailable"
        )
    return await restore(values[0].id, context)


async def fork(_argument: str, context: CommandContext) -> CommandResult:
    source_thread_id = _thread_id(context)
    if not source_thread_id or context.session_store is None or context.workflow is None:
        return CommandResult(
            True, "Forking requires an active local task.", status="unavailable"
        )
    try:
        forked = context.session_store.fork_session(source_thread_id)
        await copy_thread_state(
            context.workflow,
            context.run_config,
            forked["thread_id"],
        )
    except ValueError as exc:
        return CommandResult(True, str(exc), status="failed")
    return CommandResult(
        True,
        (
            f"Forked task as {forked['thread_id'][:10]}. "
            "This TUI fork shares the current working directory with its source."
        ),
        {
            "switch_thread_id": forked["thread_id"],
            "session_forked": {
                "source_thread_id": source_thread_id,
                "forked_thread_id": forked["thread_id"],
                "shared_workspace": True,
            },
        },
    )


COMMANDS = [
    SlashCommand("/history", (), "Show checkpoint conversation history", history),
    SlashCommand("/checkpoints", (), "List recoverable file checkpoints", checkpoints),
    SlashCommand("/restore", (), "Preview and restore one checkpoint", restore),
    SlashCommand("/undo", (), "Restore the latest file checkpoint", undo),
    SlashCommand("/fork", (), "Fork this task in the same working directory", fork),
]
