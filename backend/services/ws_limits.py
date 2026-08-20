"""Bound in-process WebSocket connection and agent-run cost.

This state deliberately lives in one backend process.  It is released when a
connection disconnects or a run reaches a terminal state.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi import WebSocket

from backend.schemas.chat import MAX_WS_CONTENT_BYTES

MAX_CONNECTIONS_PER_USER = 5
MAX_MESSAGE_BYTES = MAX_WS_CONTENT_BYTES
MAX_ACTIVE_RUNS_PER_USER = 2
MAX_RUN_STARTS_PER_MINUTE = 10


class WebSocketLimits:
    """Process-local limits for one ASGI worker."""

    def __init__(self, clock: Callable[[], datetime] | None = None):
        self.clock = clock or (lambda: datetime.now(UTC))
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._active_runs: dict[str, set[str]] = defaultdict(set)
        self._run_starts: dict[str, deque[datetime]] = defaultdict(deque)
        self._deleting_sessions: set[str] = set()

    def begin_session_deletion(self, session_id: str) -> bool:
        """Block new in-process admissions while this session is being deleted."""
        if session_id in self._deleting_sessions:
            return False
        self._deleting_sessions.add(session_id)
        return True

    def finish_session_deletion(self, session_id: str) -> None:
        self._deleting_sessions.discard(session_id)

    def is_session_deleting(self, session_id: str) -> bool:
        return session_id in self._deleting_sessions

    async def acquire_connection(
        self,
        user_id: str,
        websocket: WebSocket,
        *,
        session_id: str | None = None,
    ) -> bool:
        if session_id and self.is_session_deleting(session_id):
            await websocket.close(code=1008, reason="Session is being deleted")
            return False
        connections = self._connections[user_id]
        if len(connections) >= MAX_CONNECTIONS_PER_USER:
            await websocket.close(code=1008, reason="Connection limit exceeded")
            return False
        connections.add(websocket)
        return True

    def release_connection(self, user_id: str, websocket: WebSocket) -> None:
        connections = self._connections.get(user_id)
        if not connections:
            return
        connections.discard(websocket)
        if not connections:
            self._connections.pop(user_id, None)

    async def validate_message(self, websocket: WebSocket, content: str | None) -> bool:
        if content is not None and len(content.encode("utf-8")) > MAX_MESSAGE_BYTES:
            await websocket.close(code=1009, reason="Message too large")
            return False
        return True

    def _prune_starts(self, user_id: str) -> deque[datetime]:
        starts = self._run_starts[user_id]
        cutoff = self.clock() - timedelta(minutes=1)
        while starts and starts[0] <= cutoff:
            starts.popleft()
        if not starts:
            self._run_starts.pop(user_id, None)
            return deque()
        return starts

    def record_run_start(self, user_id: str) -> bool:
        starts = self._prune_starts(user_id)
        if len(starts) >= MAX_RUN_STARTS_PER_MINUTE:
            return False
        if user_id not in self._run_starts:
            self._run_starts[user_id] = starts
        starts.append(self.clock())
        return True

    def acquire_run(self, user_id: str, run_id: str) -> bool:
        runs = self._active_runs[user_id]
        if len(runs) >= MAX_ACTIVE_RUNS_PER_USER:
            return False
        runs.add(run_id)
        return True

    def begin_run(
        self,
        user_id: str,
        run_id: str,
        *,
        count_start: bool = True,
        session_id: str | None = None,
    ) -> bool:
        if session_id and self.is_session_deleting(session_id):
            return False
        runs = self._active_runs[user_id]
        if len(runs) >= MAX_ACTIVE_RUNS_PER_USER:
            return False
        if count_start and not self.record_run_start(user_id):
            return False
        runs.add(run_id)
        return True

    def release_run(self, user_id: str, run_id: str) -> None:
        runs = self._active_runs.get(user_id)
        if not runs:
            return
        runs.discard(run_id)
        if not runs:
            self._active_runs.pop(user_id, None)


limits = WebSocketLimits()
