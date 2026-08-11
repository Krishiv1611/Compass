"""Web adapter for the shared Compass agent runtime."""

from typing import AsyncGenerator

from langchain_core.messages import BaseMessage
from langgraph.types import Command

from agent.runtime.events import StreamEvent
from agent.runtime.protocol import ResumeAction, ResumePayload
from agent.runtime.runner import build_turn_input, invoke_agent, stream_agent_events
from agent.telemetry import get_run_config
from agent.workspace import web_workspace_context


def _configure_web_workspace(config: dict, session_id: str, user_id: str) -> None:
    from backend.db import SessionLocal
    from backend.models.session import ChatSession
    from backend.services.workspace import get_workspace_by_session

    with SessionLocal() as db:
        workspace = get_workspace_by_session(db, session_id, user_id)
        context = web_workspace_context(workspace)
        session = (
            db.query(ChatSession)
            .filter(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
                ChatSession.is_deleted.is_(False),
            )
            .first()
        )
        if not session:
            raise ValueError("Session not found.")
        configurable = config["configurable"]
        configurable["execution_target"] = "web"
        configurable["workspace_context"] = context.to_config()
        configurable["workspace_id"] = context.workspace_id
        configurable["project_id"] = context.project_id
        configurable["context_version"] = context.context_version
        configurable["context_mismatch"] = bool(
            session.context_version
            and context.context_version
            and session.context_version != context.context_version
        )


def _apply_user_preferences(config: dict, user_prefs: dict | None) -> None:
    if not user_prefs:
        return
    configurable = config["configurable"]
    if user_prefs.get("model"):
        model = user_prefs["model"]
        configurable["model"] = model
        configurable["model_executor"] = model
        configurable["model_planner"] = model
    encrypted_key = user_prefs.get("llm_api_key_encrypted")
    if encrypted_key:
        from backend.auth.credentials import decrypt_credential

        configurable["api_key"] = decrypt_credential(encrypted_key)
    if user_prefs.get("llm_provider"):
        configurable["provider"] = user_prefs["llm_provider"]
    if user_prefs.get("safe_mode") is not None:
        configurable["safe_mode"] = user_prefs["safe_mode"]
    if user_prefs.get("fast_mode") is not None:
        configurable["fast_mode"] = user_prefs["fast_mode"]


def _web_config(
    thread_id: str,
    session_id: str,
    user_id: str,
    user_prefs: dict | None,
    run_id: str | None = None,
) -> dict:
    config = get_run_config(thread_id=thread_id)
    configurable = config.setdefault("configurable", {})
    configurable["session_id"] = session_id
    configurable["user_id"] = user_id
    if run_id:
        configurable["run_id"] = run_id
    _configure_web_workspace(config, session_id, user_id)
    _apply_user_preferences(config, user_prefs)
    return config


async def run_agent_stream(
    user_message: str,
    thread_id: str,
    session_id: str,
    user_id: str,
    mode: str = "edit",
    resume_action: ResumeAction | str | None = None,
    resume_feedback: str | None = None,
    user_prefs: dict | None = None,
    run_id: str | None = None,
    context_files: list[str] | None = None,
) -> AsyncGenerator[StreamEvent, None]:
    """Stream a web turn using the same runtime as the TUI."""
    config = _web_config(
        thread_id, session_id, user_id, user_prefs, run_id=run_id
    )
    input_value = (
        build_resume_command(resume_action, resume_feedback)
        if resume_action is not None
        else build_turn_input(
            user_message,
            mode=mode,
            context_files=context_files,
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
    thread_id: str,
    session_id: str,
    user_id: str,
    mode: str = "edit",
    user_prefs: dict | None = None,
    context_files: list[str] | None = None,
) -> list[BaseMessage]:
    """Invoke a non-streaming web turn through the shared runtime."""
    config = _web_config(thread_id, session_id, user_id, user_prefs)
    input_value = build_turn_input(
        user_message,
        mode=mode,
        context_files=context_files,
        config=config,
    )
    return await invoke_agent(input_value, config)
