"""
WebSocket connection manager.

Tracks active connections per session and provides helpers
for sending events and managing heartbeats.
"""

import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from backend.schemas.chat import StreamEvent

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 30  # seconds


class ConnectionManager:
    """Manages WebSocket connections grouped by session_id."""

    def __init__(self):
        # session_id -> set of WebSocket connections
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._heartbeat_tasks: dict[WebSocket, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        """Accept a WebSocket connection and start heartbeat."""
        await websocket.accept()
        self._connections[session_id].add(websocket)
        self._heartbeat_tasks[websocket] = asyncio.create_task(
            self._heartbeat(websocket)
        )
        logger.info(f"WebSocket connected: session={session_id}")

    def disconnect(self, websocket: WebSocket, session_id: str) -> None:
        """Remove a WebSocket connection and cancel its heartbeat."""
        self._connections[session_id].discard(websocket)
        if not self._connections[session_id]:
            del self._connections[session_id]

        task = self._heartbeat_tasks.pop(websocket, None)
        if task:
            task.cancel()

        logger.info(f"WebSocket disconnected: session={session_id}")

    async def send_event(self, websocket: WebSocket, event: StreamEvent) -> None:
        """Send a StreamEvent as JSON to a single connection."""
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.send_json(event.model_dump(exclude_none=True))
            except Exception:
                logger.warning("Failed to send event to WebSocket")

    async def broadcast(self, session_id: str, event: StreamEvent) -> None:
        """Send a StreamEvent to all connections in a session."""
        connections = self._connections.get(session_id, set()).copy()
        for ws in connections:
            await self.send_event(ws, event)

    def get_connections(self, session_id: str) -> set[WebSocket]:
        """Get all active connections for a session."""
        return self._connections.get(session_id, set())

    async def _heartbeat(self, websocket: WebSocket) -> None:
        """Periodically ping the client to keep the connection alive."""
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                if websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        await websocket.send_json({"type": "ping"})
                    except Exception:
                        break
                else:
                    break
        except asyncio.CancelledError:
            pass


# Singleton instance
manager = ConnectionManager()
