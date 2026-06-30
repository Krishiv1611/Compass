"""
Chat router â€” non-streaming POST endpoint + WebSocket streaming.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, status
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
from backend.ws.hub import manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


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
    chat_session = _validate_session_access(db, current_user.id, body.session_id)

    # Persist user message
    _persist_message(db, chat_session.id, role="user", content=body.content)

    # Run agent
    try:
        response_messages = await agent_runner.run_agent_sync(
            user_message=body.content,
            thread_id=chat_session.thread_id,
            mode=body.mode,
        )
    except Exception as e:
        logger.exception("Agent run failed")
        raise HTTPException(status_code=500, detail=f"Agent Error: {str(e)}")

    # Persist and collect response messages
    result_messages = []
    first_ai_content = None

    for msg in response_messages:
        role = "assistant" if hasattr(msg, "tool_calls") and not hasattr(msg, "tool_call_id") else getattr(msg, "type", "assistant")
        if role == "ai":
            role = "assistant"
        elif role == "tool":
            role = "tool"

        tc_data = None
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            tc_data = [{"id": tc["id"], "name": tc["name"], "args": tc["args"]} for tc in msg.tool_calls]

        saved = _persist_message(
            db,
            chat_session.id,
            role=role,
            content=getattr(msg, "content", None),
            tool_calls=tc_data,
            tool_call_id=getattr(msg, "tool_call_id", None),
            model=getattr(msg, "response_metadata", {}).get("model", None) if hasattr(msg, "response_metadata") else None,
        )

        if role == "assistant" and first_ai_content is None:
            first_ai_content = getattr(msg, "content", "")

        result_messages.append(
            MessageResponse(
                id=saved.id,
                role=saved.role,
                content=saved.content,
                model=saved.model,
                created_at=saved.created_at,
            )
        )

    # Auto-title on first exchange
    if first_ai_content and chat_session.title in ("New Chat", None):
        session_manager.auto_title(db, chat_session.id, body.content, first_ai_content)

    # Update session timestamp
    chat_session.updated_at = datetime.now(timezone.utc)
    db.commit()

    return ChatResponse(messages=result_messages)


@router.websocket("/ws/{session_id}")
async def websocket_chat(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(default=""),
):
    """
    WebSocket endpoint for real-time chat streaming.

    Authentication via query param: /chat/ws/{session_id}?token=<jwt>

    Client sends: {"type": "message", "content": "..."}
    Server sends: {"type": "token|tool_call|tool_result|done|error", ...}
    """
    # â”€â”€ Authenticate â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4001, reason="Invalid token type")
            return
        user_id = payload["sub"]
    except JWTError:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    # â”€â”€ Validate session ownership â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    db = SessionLocal()
    try:
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
        thread_id = chat_session.thread_id
    finally:
        db.close()

    # â”€â”€ Connect â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    await manager.connect(websocket, session_id)

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
                manager.resolve_call(client_msg.call_id, client_msg.result, client_msg.error)
                continue

            if client_msg.type == "message" and client_msg.content:
                # Persist user message
                db = SessionLocal()
                try:
                    _persist_message(db, session_id, role="user", content=client_msg.content)
                finally:
                    db.close()

                # Stream agent response
                full_content = []
                async for event in agent_runner.run_agent_stream(
                    user_message=client_msg.content,
                    thread_id=thread_id,
                    mode=client_msg.mode,
                ):
                    await manager.send_event(websocket, event)

                    # Accumulate tokens for persistence
                    if event.type == StreamEventType.TOKEN and event.content:
                        full_content.append(event.content)

                # Persist assistant response
                if full_content:
                    assistant_text = "".join(full_content)
                    db = SessionLocal()
                    try:
                        _persist_message(db, session_id, role="assistant", content=assistant_text)

                        # Auto-title on first message
                        cs = db.query(ChatSession).filter(ChatSession.id == session_id).first()
                        if cs and cs.title in ("New Chat", None):
                            msg_count = db.query(Message).filter(Message.session_id == session_id).count()
                            if msg_count <= 3:
                                session_manager.auto_title(db, session_id, client_msg.content, assistant_text)

                        # Update session timestamp
                        if cs:
                            cs.updated_at = datetime.now(timezone.utc)
                            db.commit()
                    finally:
                        db.close()

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


