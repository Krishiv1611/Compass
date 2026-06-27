"""
Compass Session Manager — Persist and manage conversation sessions.

Stores lightweight session metadata (thread_id, name, timestamps) in a
local JSON file. The actual conversation state is stored by PostgresSaver
in the database — this module just tracks which thread_ids exist.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import platformdirs


# ─── Session storage location ──────────────────────────────────────────────────
_APP_DIR = Path(platformdirs.user_data_dir("compass", "compass"))
_SESSIONS_FILE = _APP_DIR / "sessions.json"


class SessionManager:
    """Manage session metadata stored in a local JSON file."""

    def __init__(self, sessions_file: Path = _SESSIONS_FILE):
        self._file = sessions_file
        self._sessions: list[dict] = []
        self._load()

    # ── Persistence ─────────────────────────────────────────────────────────

    def _load(self):
        """Load sessions from disk."""
        if self._file.exists():
            try:
                data = json.loads(self._file.read_text(encoding="utf-8"))
                self._sessions = data if isinstance(data, list) else []
            except (json.JSONDecodeError, OSError):
                self._sessions = []
        else:
            self._sessions = []

    def _save(self):
        """Write sessions to disk."""
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(
            json.dumps(self._sessions, indent=2, default=str),
            encoding="utf-8",
        )

    # ── CRUD ────────────────────────────────────────────────────────────────

    def create_session(self, name: str = "") -> dict:
        """Create a new session and return its metadata."""
        now = datetime.now(timezone.utc).isoformat()
        session = {
            "thread_id": uuid.uuid4().hex,
            "name": name or "",
            "created_at": now,
            "last_active": now,
            "turn_count": 0,
        }
        self._sessions.append(session)
        self._save()
        return session

    def get_session(self, thread_id: str) -> dict | None:
        """Look up a session by exact thread_id or prefix match."""
        for s in self._sessions:
            if s["thread_id"] == thread_id or s["thread_id"].startswith(thread_id):
                return s
        return None

    def get_last_session(self) -> dict | None:
        """Return the most recently active session, or None."""
        if not self._sessions:
            return None
        return max(self._sessions, key=lambda s: s.get("last_active", ""))

    def list_sessions(self, limit: int = 10) -> list[dict]:
        """Return recent sessions sorted by last_active descending."""
        sorted_sessions = sorted(
            self._sessions,
            key=lambda s: s.get("last_active", ""),
            reverse=True,
        )
        return sorted_sessions[:limit]

    def update_session(
        self,
        thread_id: str,
        turn_count: int | None = None,
        first_message: str = "",
    ):
        """Update a session's last_active time and optionally turn count / name."""
        session = self.get_session(thread_id)
        if session is None:
            return
        session["last_active"] = datetime.now(timezone.utc).isoformat()
        if turn_count is not None:
            session["turn_count"] = turn_count
        # Auto-name from first user message if not already named
        if first_message and not session.get("name"):
            session["name"] = first_message[:50].strip()
        self._save()

    def rename_session(self, thread_id: str, new_name: str) -> bool:
        """Rename a session. Returns True on success."""
        session = self.get_session(thread_id)
        if session is None:
            return False
        session["name"] = new_name.strip()
        self._save()
        return True

    def delete_session(self, thread_id: str) -> bool:
        """Remove a session record. Returns True if found and deleted."""
        before = len(self._sessions)
        self._sessions = [
            s for s in self._sessions
            if s["thread_id"] != thread_id
            and not s["thread_id"].startswith(thread_id)
        ]
        if len(self._sessions) < before:
            self._save()
            return True
        return False

    # ── Helpers ─────────────────────────────────────────────────────────────

    def session_age_minutes(self, session: dict) -> float:
        """How many minutes ago was this session last active."""
        try:
            last = datetime.fromisoformat(session["last_active"])
            now = datetime.now(timezone.utc)
            return (now - last).total_seconds() / 60
        except (KeyError, ValueError):
            return float("inf")
