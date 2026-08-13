"""
Chat router -- non-streaming POST endpoint + WebSocket streaming.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from jose import JWTError
from sqlalchemy.orm import Session

from backend.auth.dependencies import get_current_user
from backend.auth.jwt import decode_token
from backend.db import get_db, SessionLocal
from backend.models.user import User
from backend.models.session import ChatSession
from backend.models.message import Message
from backend.schemas.chat import (
    ChatRequest,
    ChatResponse,
    MessageResponse,
    StreamEvent,
    StreamEventType,
    WsClientMessage,
)
from backend.services import agent_runner
from backend.services import session_manager
from backend.services.run_context import RunContextSnapshot, load_run_context
from backend.services.run_manager import (
    claim_agent_run,
    end_agent_run,
    persist_run_events,
)
from backend.services.run_persistence import RunEventBatcher, terminal_from_events
from backend.ws.hub import manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

WEBSOCKET_PROTOCOL = "compass.v1"
WEBSOCKET_TOKEN_PREFIX = "compass.jwt."


class WebSocketAuthError(ValueError):
    """Authentication failure that can be returned as a WebSocket close frame."""

    def __init__(self, reason: str, code: int = 4001):
        super().__init__(reason)
        self.code = code
        self.reason = reason


def extract_websocket_access_token(
    protocol_header: str | None,
    query_token: str | None,
) -> str:
    """Extract a JWT from the WebSocket subprotocol header."""
    if query_token is not None:
        raise WebSocketAuthError("Query string credentials are not accepted")
    if not protocol_header:
        raise WebSocketAuthError("Missing credentials")

    protocols = [value.strip() for value in protocol_header.split(",") if value.strip()]
    token_protocols = [
        value for value in protocols if value.startswith(WEBSOCKET_TOKEN_PREFIX)
    ]
    if (
        len(protocols) != 2
        or protocols.count(WEBSOCKET_PROTOCOL) != 1
        or len(token_protocols) != 1
    ):
        raise WebSocketAuthError("Malformed WebSocket credentials")

    token = token_protocols[0][len(WEBSOCKET_TOKEN_PREFIX) :]
    if not token:
        raise WebSocketAuthError("Malformed WebSocket credentials")
    return token


def authenticate_websocket_user(
    protocol_header: str | None,
    query_token: str | None,
    db: Session,
) -> str:
    """Validate WebSocket credentials and return an active user ID."""
    token = extract_websocket_access_token(protocol_header, query_token)
    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise WebSocketAuthError("Invalid or expired token") from exc

    user_id = payload.get("sub")
    if payload.get("type") != "access" or not isinstance(user_id, str) or not user_id:
        raise WebSocketAuthError("Invalid access token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise WebSocketAuthError("User not found")
    if not user.is_active:
        raise WebSocketAuthError("Inactive user")
    return user_id


def _persist_message(
    db: Session,
    session_id: str,
    role: str,
    content: str | None = None,
    tool_calls: dict | None = None,
    tool_call_id: str | None = None,
    model: str | None = None,
) -> Message:
    """Helper to save a message to the database."""
    msg = Message(
        session_id=session_id,
        role=role,
        content=content,
        tool_calls=tool_calls,
        tool_call_id=tool_call_id,
        model=model,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def _validate_session_access(db: Session, user_id: str, session_id: str) -> ChatSession:
    """Validate that the user owns the session and it exists."""
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    return session


def _claim_run_record(
    snapshot: RunContextSnapshot,
    requested_run_id: str,
    *,
    resume: bool,
) -> str:
    with SessionLocal() as db:
        run = claim_agent_run(
            db,
            snapshot,
            requested_run_id,
            resume=resume,
        )
        return run.id


def _persist_run_event_batch(
    run_id: str,
    events: list[tuple[str, dict]],
) -> None:
    if not events:
        return
    with SessionLocal() as db:
        persist_run_events(db, run_id, events)


def _end_run_record(
    run_id: str,
    status_value: str,
    token_usage: dict | None = None,
) -> None:
    with SessionLocal() as db:
        end_agent_run(
            db,
            run_id=run_id,
            status=status_value,
            token_usage=token_usage,
        )


async def _stream_agent_turn(
    snapshot: RunContextSnapshot,
    client_msg: WsClientMessage,
) -> AsyncGenerator[StreamEvent, None]:
    """Stream one turn while opening DB sessions only for short writes."""
    is_resume = client_msg.type == "resume"
    if is_resume and not client_msg.run_id:
        raise HTTPException(status_code=400, detail="resume requires run_id")
    requested_run_id = client_msg.run_id or str(uuid.uuid4())
    run_id = _claim_run_record(
        snapshot,
        requested_run_id,
        resume=is_resume,
    )
    batcher = RunEventBatcher(max_size=25)
    terminal_events: list[StreamEvent] = []
    try:
        async for event in agent_runner.run_agent_stream(
            user_message=client_msg.content or "",
            snapshot=snapshot,
            mode=client_msg.mode,
            resume_action=client_msg.action,
            resume_feedback=client_msg.feedback,
            run_id=run_id,
            context_files=client_msg.context_files,
            active_skill=client_msg.active_skill,
        ):
            event.run_id = run_id
            event.session_id = snapshot.session_id
            batch = batcher.add(event)
            if batch:
                _persist_run_event_batch(run_id, batch)
            if event.type in {
                StreamEventType.RUN_WAITING,
                StreamEventType.DONE,
                StreamEventType.ERROR,
            }:
                terminal_events.append(event)
            yield event

        _persist_run_event_batch(run_id, batcher.flush())
        terminal = terminal_from_events(terminal_events)
        _end_run_record(run_id, terminal.status, terminal.token_usage)
    except Exception:
        _end_run_record(run_id, "failed")
        raise


def _persist_assistant_turn(
    snapshot: RunContextSnapshot,
    user_content: str | None,
    assistant_text: str,
) -> None:
    with SessionLocal() as db:
        _persist_message(
            db,
            snapshot.session_id,
            role="assistant",
            content=assistant_text,
        )
        chat_session = (
            db.query(ChatSession)
            .filter(ChatSession.id == snapshot.session_id)
            .first()
        )
        if chat_session and chat_session.title in ("New Chat", None):
            message_count = (
                db.query(Message)
                .filter(Message.session_id == snapshot.session_id)
                .count()
            )
            if message_count <= 3:
                session_manager.auto_title(
                    db,
                    snapshot.session_id,
                    user_content,
                    assistant_text,
                )
        if chat_session:
            chat_session.updated_at = datetime.now(timezone.utc)
            db.commit()


def _persist_sync_response(
    snapshot: RunContextSnapshot,
    request: ChatRequest,
    response_messages: list,
) -> list[MessageResponse]:
    result_messages: list[MessageResponse] = []
    first_ai_content = None
    with SessionLocal() as db:
        for message in response_messages:
            role = (
                "assistant"
                if hasattr(message, "tool_calls")
                and not hasattr(message, "tool_call_id")
                else getattr(message, "type", "assistant")
            )
            if role == "ai":
                role = "assistant"
            elif role == "tool":
                role = "tool"

            tool_calls = None
            if hasattr(message, "tool_calls") and message.tool_calls:
                tool_calls = [
                    {"id": call["id"], "name": call["name"], "args": call["args"]}
                    for call in message.tool_calls
                ]

            saved = _persist_message(
                db,
                snapshot.session_id,
                role=role,
                content=getattr(message, "content", None),
                tool_calls=tool_calls,
                tool_call_id=getattr(message, "tool_call_id", None),
                model=getattr(message, "response_metadata", {}).get("model", None)
                if hasattr(message, "response_metadata")
                else None,
            )
            if role == "assistant" and first_ai_content is None:
                first_ai_content = getattr(message, "content", "")
            result_messages.append(
                MessageResponse(
                    id=saved.id,
                    role=saved.role,
                    content=saved.content,
                    model=saved.model,
                    created_at=saved.created_at,
                )
            )

        chat_session = _validate_session_access(
            db,
            snapshot.user_id,
            snapshot.session_id,
        )
        if first_ai_content and chat_session.title in ("New Chat", None):
            session_manager.auto_title(
                db,
                chat_session.id,
                request.content,
                first_ai_content,
            )
        chat_session.updated_at = datetime.now(timezone.utc)
        db.commit()
    return result_messages


@router.post("/send", response_model=ChatResponse)
async def send_message(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Send a message and get the full agent response (non-streaming).

    Persists both user and assistant messages to the database.
    """
    user_id = current_user.id
    chat_session = _validate_session_access(db, user_id, body.session_id)

    # Persist user message
    _persist_message(db, chat_session.id, role="user", content=body.content)
    db.close()
    snapshot = load_run_context(body.session_id, user_id)

    # Run agent
    try:
        response_messages = await agent_runner.run_agent_sync(
            user_message=body.content,
            snapshot=snapshot,
            mode=body.mode,
            context_files=body.context_files,
            active_skill=body.active_skill,
        )
    except Exception as exc:
        error_msg = str(exc)
        logger.exception("Agent run failed")

        if "Project changed since this task was created" in error_msg:
            raise HTTPException(status_code=409, detail=error_msg)

        if "UnauthorizedResponseError" in error_msg or "User not found" in error_msg or "401" in error_msg:
            raise HTTPException(
                status_code=401,
                detail="Invalid LLM API Key. Please update your API key in Settings.",
            )

        raise HTTPException(status_code=500, detail="Agent execution failed.")
    return ChatResponse(
        messages=_persist_sync_response(snapshot, body, response_messages)
    )


@router.websocket("/ws/{session_id}")
async def websocket_chat(
    websocket: WebSocket,
    session_id: str,
):
    """
    WebSocket endpoint for real-time chat streaming.

    Authentication uses the ``compass.v1`` and ``compass.jwt.<token>``
    WebSocket subprotocols so credentials never appear in URLs.

    Client sends: {"type": "message", "content": "..."}
    Server sends: {"type": "token|tool_call|tool_result|done|error", ...}
    """
    db = SessionLocal()
    try:
        try:
            user_id = authenticate_websocket_user(
                websocket.headers.get("sec-websocket-protocol"),
                websocket.query_params.get("token"),
                db,
            )
        except WebSocketAuthError as exc:
            await websocket.close(code=exc.code, reason=exc.reason)
            return

        # Validate session ownership only after authentication succeeds.
        chat_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
                ChatSession.is_deleted.is_(False),
            )
            .first()
        )
        if not chat_session:
            await websocket.close(code=4004, reason="Session not found")
            return
    finally:
        db.close()

    # -- Connect --
    await manager.connect(websocket, session_id, subprotocol=WEBSOCKET_PROTOCOL)
    current_run_id: str | None = None

    try:
        while True:
            # Wait for client message
            raw = await websocket.receive_json()

            # Handle pong (heartbeat response)
            if raw.get("type") == "pong":
                continue

            client_msg = WsClientMessage(**raw)

            if client_msg.type == "tool_result" and client_msg.call_id:
                # Handle RPC response from EDGE client
                manager.resolve_call(
                    client_msg.call_id, client_msg.result, client_msg.error
                )
                continue

            if client_msg.type in ("message", "resume"):
                if client_msg.type == "message" and client_msg.content:
                    with SessionLocal() as db:
                        _persist_message(
                            db, session_id, role="user", content=client_msg.content
                        )

                if client_msg.type == "resume" and not client_msg.run_id:
                    client_msg.run_id = current_run_id
                snapshot = load_run_context(session_id, user_id)
                assistant_text: str | None = None
                async for event in _stream_agent_turn(snapshot, client_msg):
                    if event.run_id:
                        current_run_id = event.run_id
                    await manager.send_event(websocket, event)
                    if event.type in {
                        StreamEventType.DONE,
                        StreamEventType.RUN_WAITING,
                    } and isinstance(event.data, dict):
                        final_content = event.data.get("assistant_content")
                        if isinstance(final_content, str) and final_content:
                            assistant_text = final_content

                if assistant_text:
                    _persist_assistant_turn(
                        snapshot,
                        client_msg.content,
                        assistant_text,
                    )

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.exception("WebSocket error")
        try:
            await manager.send_event(
                websocket,
                StreamEvent(type=StreamEventType.ERROR, content=str(exc)[:500]),
            )
        except Exception:
            pass
    finally:
        manager.disconnect(websocket, session_id)

