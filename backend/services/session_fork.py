"""Create bounded, isolated web forks of Compass task sessions."""

from __future__ import annotations

import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from sqlalchemy.orm import Session

from agent.checkpoints import (
    CheckpointManifest,
    get_checkpoint,
    list_checkpoints,
    restore_checkpoint,
)
from agent.graph.workflow import get_workflow
from agent.sessions import copy_thread_state
from agent.workspace import discover_local_workspace
from backend.db import SessionLocal
from backend.models.message import Message
from backend.models.session import ChatSession
from backend.models.workspace import Workspace
from backend.services.ownership import owned_session


MAX_FORK_FILES = 2_000
MAX_FORK_BYTES = 100 * 1024 * 1024
_EXCLUDED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    "target",
    ".next",
    ".cache",
    "coverage",
}
_EXCLUDED_FILES = {
    ".env",
    ".npmrc",
    ".pypirc",
    ".netrc",
    "credentials.json",
    "credentials.yml",
    "credentials.yaml",
    "secrets.json",
    "secrets.yml",
    "secrets.yaml",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}
_SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".jks", ".keystore")
_COMPASS_CACHE_FILES = {
    (".compass", "index_state.json"),
    (".compass", "sessions.json"),
}


def _is_secret_file(relative_path: Path) -> bool:
    name = relative_path.name.lower()
    if name in _EXCLUDED_FILES or name.endswith(_SECRET_SUFFIXES):
        return True
    if name.endswith(".env") or name.startswith(".env."):
        return True
    return any(term in name for term in ("credential", "secret", "api_key", "token"))


def _clone_candidates(source_root: Path) -> list[tuple[Path, Path]]:
    candidates: list[tuple[Path, Path]] = []
    total_bytes = 0
    source_root = source_root.resolve()
    for current_root, directories, filenames in os.walk(source_root):
        current = Path(current_root)
        relative_directory = current.relative_to(source_root)
        directories[:] = [
            name
            for name in directories
            if name.lower() not in _EXCLUDED_DIRECTORIES
            and not (
                tuple(part.lower() for part in relative_directory.parts)
                == (".compass",)
                and name.lower() == "checkpoints"
            )
            and not (current / name).is_symlink()
        ]
        for filename in filenames:
            source = current / filename
            relative = source.relative_to(source_root)
            if source.is_symlink() or not source.is_file():
                continue
            lower_parts = tuple(part.lower() for part in relative.parts)
            if lower_parts in _COMPASS_CACHE_FILES or _is_secret_file(relative):
                continue
            size = source.stat().st_size
            candidates.append((source, relative))
            total_bytes += size
            if len(candidates) > MAX_FORK_FILES:
                raise HTTPException(
                    status_code=413,
                    detail="Workspace contains more than 2,000 forkable files",
                )
            if total_bytes > MAX_FORK_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail="Workspace fork exceeds the 100 MB limit",
                )
    return candidates


def _copy_workspace(source_root: Path, target_root: Path) -> None:
    candidates = _clone_candidates(source_root)
    target_root.mkdir(parents=True, exist_ok=False)
    for source, relative in candidates:
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _purge_rejected_files(target_root: Path) -> None:
    """Remove anything a selected checkpoint could reintroduce."""
    for current_root, directories, filenames in os.walk(target_root, topdown=True):
        current = Path(current_root)
        relative_directory = current.relative_to(target_root)
        for directory in list(directories):
            if (
                directory.lower() in _EXCLUDED_DIRECTORIES
                or (
                    tuple(part.lower() for part in relative_directory.parts)
                    == (".compass",)
                    and directory.lower() == "checkpoints"
                )
            ):
                shutil.rmtree(current / directory, ignore_errors=True)
                directories.remove(directory)
        for filename in filenames:
            target = current / filename
            relative = target.relative_to(target_root)
            lower_parts = tuple(part.lower() for part in relative.parts)
            if lower_parts in _COMPASS_CACHE_FILES or _is_secret_file(relative):
                target.unlink(missing_ok=True)


def _apply_checkpoint_to_fork(
    source_root: Path,
    target_root: Path,
    checkpoint_id: str,
) -> None:
    source_bundle = source_root / ".compass" / "checkpoints" / checkpoint_id
    target_store = target_root / ".compass" / "checkpoints"
    target_bundle = target_store / checkpoint_id
    target_store.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_bundle, target_bundle)
    try:
        restore_checkpoint(target_root, checkpoint_id, force=True)
    finally:
        shutil.rmtree(target_store, ignore_errors=True)
        compass_directory = target_root / ".compass"
        if compass_directory.is_dir() and not any(compass_directory.iterdir()):
            compass_directory.rmdir()


def _apply_checkpoint_chain_to_fork(
    source_root: Path,
    target_root: Path,
    selected_checkpoint: CheckpointManifest,
) -> None:
    """Reverse every later mutation so the fork matches the selected boundary."""
    checkpoints = list_checkpoints(
        source_root,
        workspace_id=selected_checkpoint.workspace_id,
        thread_id=selected_checkpoint.thread_id,
    )
    try:
        selected_index = next(
            index
            for index, checkpoint in enumerate(checkpoints)
            if checkpoint.id == selected_checkpoint.id
        )
    except StopIteration:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    for checkpoint in checkpoints[: selected_index + 1]:
        _apply_checkpoint_to_fork(source_root, target_root, checkpoint.id)
    _purge_rejected_files(target_root)


def _normalized_time(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


async def _graph_state_at_checkpoint(
    workflow,
    config: dict,
    cutoff: datetime,
) -> tuple[dict, bool]:
    """Return the newest graph snapshot at/before the file checkpoint."""
    history = getattr(workflow, "aget_state_history", None)
    if callable(history):
        async for snapshot in history(config):
            created_at = getattr(snapshot, "created_at", None)
            if not created_at:
                continue
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    )
                except ValueError:
                    continue
            if _normalized_time(created_at) <= _normalized_time(cutoff):
                return (snapshot.values or {}), True
    snapshot = await workflow.aget_state(config)
    return ((snapshot.values or {}) if snapshot else {}), False


def _message_role(message: BaseMessage) -> str:
    if isinstance(message, HumanMessage):
        return "user"
    if isinstance(message, AIMessage):
        return "assistant"
    if isinstance(message, ToolMessage):
        return "tool"
    if isinstance(message, SystemMessage):
        return "system"
    return str(getattr(message, "type", ""))


def _message_content(message: BaseMessage) -> str:
    content = getattr(message, "content", "")
    return content if isinstance(content, str) else str(content)


def _graph_messages_through(
    graph_messages: list[BaseMessage],
    database_messages: list[Message],
) -> list[BaseMessage]:
    """Keep the graph prefix represented by the selected database history."""
    if not database_messages:
        return []
    kept: list[BaseMessage] = []
    matched = 0
    for graph_message in graph_messages:
        kept.append(graph_message)
        expected = database_messages[matched]
        if (
            _message_role(graph_message) == expected.role
            and _message_content(graph_message) == (expected.content or "")
        ):
            matched += 1
            if matched == len(database_messages):
                return kept
    return kept[: len(database_messages)]


def _copy_database_messages(
    db: Session,
    source_session_id: str,
    target_session_id: str,
    *,
    cutoff: datetime | None = None,
) -> list[Message]:
    query = db.query(Message).filter(Message.session_id == source_session_id)
    source_messages = query.order_by(Message.created_at.asc(), Message.id.asc()).all()
    if cutoff is not None:
        normalized_cutoff = _normalized_time(cutoff)
        source_messages = [
            message
            for message in source_messages
            if _normalized_time(message.created_at) <= normalized_cutoff
        ]
    for source in source_messages:
        db.add(
            Message(
                session_id=target_session_id,
                role=source.role,
                content=source.content,
                tool_calls=source.tool_calls,
                tool_call_id=source.tool_call_id,
                model=source.model,
                token_count=source.token_count,
                created_at=source.created_at,
            )
        )
    return source_messages


async def _fork_session(
    db: Session,
    source_session_id: str,
    user_id: str,
    checkpoint_id: str | None,
    workflow,
) -> ChatSession:
    source_session = owned_session(db, source_session_id, user_id)
    source_workspace = source_session.active_workspace
    if source_workspace is None or source_workspace.status != "ready":
        raise HTTPException(
            status_code=409,
            detail="A ready active workspace is required before forking",
        )
    source_root = Path(source_workspace.storage_path).resolve()
    if not source_root.is_dir():
        raise HTTPException(
            status_code=409,
            detail="The active workspace directory is unavailable",
        )

    checkpoint = None
    if checkpoint_id:
        try:
            checkpoint = get_checkpoint(source_root, checkpoint_id)
        except (FileNotFoundError, ValueError):
            raise HTTPException(status_code=404, detail="Checkpoint not found")
        if (
            checkpoint.workspace_id != source_workspace.id
            or checkpoint.thread_id != source_session.thread_id
        ):
            raise HTTPException(status_code=404, detail="Checkpoint not found")

    fork_id = uuid.uuid4().hex
    workspace_id = uuid.uuid4().hex
    target_root = source_root.parent / workspace_id
    forked = ChatSession(
        id=fork_id,
        user_id=user_id,
        title=f"Fork of {source_session.title or 'task'}",
        thread_id=uuid.uuid4().hex,
        project_id=f"workspace:{workspace_id}",
        git_remote=source_session.git_remote,
        git_branch=source_session.git_branch,
        git_head=source_session.git_head,
        context_version=source_session.context_version,
    )
    workspace = Workspace(
        id=workspace_id,
        user_id=user_id,
        session_id=fork_id,
        name=f"{source_workspace.name} (fork)",
        storage_path=str(target_root),
        source_type="fork",
        status="preparing",
        project_id=f"workspace:{workspace_id}",
        git_remote=source_workspace.git_remote,
        git_branch=source_workspace.git_branch,
        git_head=source_workspace.git_head,
        context_version=source_workspace.context_version,
    )
    db.add_all([forked, workspace])
    db.flush()

    try:
        _copy_workspace(source_root, target_root)
        if checkpoint is not None:
            _apply_checkpoint_chain_to_fork(source_root, target_root, checkpoint)

        copied_messages = _copy_database_messages(
            db,
            source_session.id,
            forked.id,
            cutoff=checkpoint.created_at if checkpoint else None,
        )
        db.add(
            Message(
                session_id=forked.id,
                role="system",
                content=f"Task forked from session {source_session.id}.",
                tool_calls={
                    "event": "session_forked",
                    "source_session_id": source_session.id,
                    "checkpoint_id": checkpoint.id if checkpoint else None,
                },
            )
        )
        source_config = {"configurable": {"thread_id": source_session.thread_id}}
        if checkpoint is not None:
            source_values, has_historical_state = await _graph_state_at_checkpoint(
                workflow,
                source_config,
                checkpoint.created_at,
            )
        else:
            snapshot = await workflow.aget_state(source_config)
            source_values = (snapshot.values or {}) if snapshot else {}
            has_historical_state = True
        graph_messages = list(source_values.get("messages", []))
        if checkpoint is not None and not has_historical_state:
            selected_graph_messages = _graph_messages_through(
                graph_messages, copied_messages
            )
        else:
            selected_graph_messages = graph_messages
        cloned_files = _clone_candidates(target_root)
        workspace.file_count = len(cloned_files)
        workspace.size_bytes = sum(path.stat().st_size for path, _ in cloned_files)
        identity = discover_local_workspace(target_root)
        workspace.context_version = identity.context_version
        forked.context_version = identity.context_version
        workspace.status = "ready"
        forked.active_workspace_id = workspace.id
        db.flush()
        db.commit()
        db.refresh(forked)
        await copy_thread_state(
            workflow,
            source_config,
            forked.thread_id,
            messages=selected_graph_messages,
            checkpoint_id=checkpoint.id if checkpoint else None,
            source_values=source_values,
            copy_derived_state=has_historical_state,
        )
        return forked
    except Exception:
        db.rollback()
        try:
            persisted_fork = (
                db.query(ChatSession).filter(ChatSession.id == fork_id).first()
            )
            if persisted_fork is not None:
                db.delete(persisted_fork)
                db.commit()
        except Exception:
            db.rollback()
        finally:
            shutil.rmtree(target_root, ignore_errors=True)
        raise


async def fork_session(
    source_session_id: str,
    user_id: str,
    checkpoint_id: str | None = None,
    *,
    db: Session | None = None,
    workflow=None,
) -> ChatSession:
    """Fork a session into a separate bounded web workspace."""
    active_workflow = workflow or await get_workflow(require_durable=True)
    if db is not None:
        return await _fork_session(
            db, source_session_id, user_id, checkpoint_id, active_workflow
        )
    with SessionLocal() as managed_db:
        forked = await _fork_session(
            managed_db,
            source_session_id,
            user_id,
            checkpoint_id,
            active_workflow,
        )
        # Keep the documented return value usable after the managed session closes.
        _ = forked.active_workspace
        _ = list(forked.messages)
        return forked
