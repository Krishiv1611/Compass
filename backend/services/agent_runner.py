"""Web adapter for the shared Compass agent runtime."""

from pathlib import Path
from typing import AsyncGenerator

from langchain_core.messages import BaseMessage
from langgraph.types import Command

from agent.runtime.events import StreamEvent
from agent.runtime.protocol import ResumeAction, ResumePayload
from agent.runtime.runner import build_turn_input, invoke_agent, stream_agent_events
from agent.runtime.metrics import RunMetrics
from agent.telemetry import get_run_config
from agent.workspace import WorkspaceContext, canonical_git_remote
from backend.services.run_context import RunContextSnapshot


def _configure_web_workspace(
    config: dict,
    snapshot: RunContextSnapshot,
) -> None:
    context = WorkspaceContext(
        root=Path(snapshot.workspace_path).resolve(),
        execution_target="web",
        workspace_id=snapshot.workspace_id,
        project_id=snapshot.project_id,
        source_type=snapshot.source_type or "upload",
        git_remote=canonical_git_remote(snapshot.git_remote),
        git_branch=snapshot.git_branch,
        git_head=snapshot.git_head,
        context_version=snapshot.context_version or snapshot.workspace_id,
    )
    configurable = config["configurable"]
    configurable["execution_target"] = "web"
    configurable["workspace_context"] = context.to_config()
    configurable["workspace_id"] = context.workspace_id
    configurable["project_id"] = context.project_id
    configurable["context_version"] = context.context_version
    configurable["context_mismatch"] = bool(
        snapshot.session_context_version
        and context.context_version
        and snapshot.session_context_version != context.context_version
    )


def _apply_user_preferences(config: dict, user_prefs: dict | None) -> None:
    if not user_prefs:
        raise ValueError("Provider settings are required")
    from backend.services.provider_credentials import resolve_provider_config

    resolved = resolve_provider_config(user_prefs)
    configurable = config["configurable"]
    configurable.update(resolved.to_config())
    configurable["model_executor"] = resolved.model
    configurable["model_planner"] = resolved.model
    if user_prefs.get("safe_mode") is not None:
        configurable["safe_mode"] = user_prefs["safe_mode"]
    if user_prefs.get("fast_mode") is not None:
        configurable["fast_mode"] = user_prefs["fast_mode"]


def _web_config(
    snapshot: RunContextSnapshot,
    run_id: str | None = None,
) -> dict:
    config = get_run_config(thread_id=snapshot.thread_id)
    configurable = config.setdefault("configurable", {})
    configurable["session_id"] = snapshot.session_id
    configurable["user_id"] = snapshot.user_id
    if run_id:
        configurable["run_id"] = run_id
    _configure_web_workspace(config, snapshot)
    _apply_user_preferences(config, snapshot.preferences)
    return config


async def run_agent_stream(
    user_message: str,
    snapshot: RunContextSnapshot,
    mode: str = "edit",
    resume_action: ResumeAction | str | None = None,
    resume_feedback: str | None = None,
    run_id: str | None = None,
    context_files: list[str] | None = None,
    active_skill: str | None = None,
    metrics: RunMetrics | None = None,
) -> AsyncGenerator[StreamEvent, None]:
    """Stream a web turn using the same runtime as the TUI."""
    config = _web_config(snapshot, run_id=run_id)
    input_value = (
        build_resume_command(resume_action, resume_feedback)
        if resume_action is not None
        else build_turn_input(
            user_message,
            mode=mode,
            context_files=context_files,
            active_skill={"name": active_skill, "arguments": ""} if active_skill else None,
            config=config,
        )
    )
    cancel_event = None
    if run_id:
        from backend.services.run_manager import get_cancel_signal

        cancel_event = get_cancel_signal(run_id)
    async for event in stream_agent_events(
        input_value,
        config,
        cancel_event=cancel_event,
        metrics=metrics,
    ):
        yield event


def build_resume_command(
    action: ResumeAction | str,
    feedback: str | None = None,
) -> Command:
    """Build a validated LangGraph resume command for every web action."""

    payload = ResumePayload(action=action, feedback=feedback)
    return Command(resume=payload.model_dump(mode="json"))


async def run_agent_sync(
    user_message: str,
    snapshot: RunContextSnapshot,
    mode: str = "edit",
    context_files: list[str] | None = None,
    active_skill: str | None = None,
) -> list[BaseMessage]:
    """Invoke a non-streaming web turn through the shared runtime."""
    config = _web_config(snapshot)
    input_value = build_turn_input(
        user_message,
        mode=mode,
        context_files=context_files,
        active_skill={"name": active_skill, "arguments": ""} if active_skill else None,
        config=config,
    )
    return await invoke_agent(input_value, config)
