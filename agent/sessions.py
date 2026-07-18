"""
Shim for SessionManager to route TUI session requests to the database backend.
Provides the same API that `agent/ui/tui.py` and `main.py` expect, but uses
`backend.services.session_manager` and SQLAlchemy under the hood.
"""

from datetime import datetime, timezone
from backend.db import SessionLocal
from backend.services import session_manager as backend_sm

# CLI users don't have authentication, so we use a hardcoded local user ID.
CLI_USER_ID = "local_cli_user"

class SessionManager:
    """Manage session metadata via the backend database."""

    def __init__(self):
        # Ensure the CLI user exists
        with SessionLocal() as db:
            from backend.models.user import User
            user = db.query(User).filter(User.id == CLI_USER_ID).first()
            if not user:
                user = User(id=CLI_USER_ID, email="cli@compass.local", display_name="CLI User")
                db.add(user)
                db.commit()

    def create_session(self, name: str = "") -> dict:
        """Create a new session and return its metadata as a dict."""
        with SessionLocal() as db:
            session = backend_sm.create_session(db, CLI_USER_ID, title=name)
            return {
                "id": session.id,
                "thread_id": session.thread_id,
                "name": session.title,
                "created_at": session.created_at.isoformat(),
                "last_active": session.updated_at.isoformat(),
                "turn_count": 0,  # We can't easily track this without counting messages
            }

    def get_session(self, thread_id_prefix: str) -> dict | None:
        """Look up a session by exact thread_id or prefix match."""
        with SessionLocal() as db:
            from backend.models.session import ChatSession
            session = db.query(ChatSession).filter(
                ChatSession.user_id == CLI_USER_ID,
                ChatSession.is_deleted.is_(False),
                ChatSession.thread_id.startswith(thread_id_prefix)
            ).order_by(ChatSession.updated_at.desc()).first()
            
            if not session:
                return None
                
            return {
                "id": session.id,
                "thread_id": session.thread_id,
                "name": session.title,
                "created_at": session.created_at.isoformat(),
                "last_active": session.updated_at.isoformat(),
            }

    def get_last_session(self) -> dict | None:
        """Return the most recently active session, or None."""
        with SessionLocal() as db:
            from backend.models.session import ChatSession
            session = db.query(ChatSession).filter(
                ChatSession.user_id == CLI_USER_ID,
                ChatSession.is_deleted.is_(False),
            ).order_by(ChatSession.updated_at.desc()).first()
            
            if not session:
                return None
                
            return {
                "id": session.id,
                "thread_id": session.thread_id,
                "name": session.title,
                "created_at": session.created_at.isoformat(),
                "last_active": session.updated_at.isoformat(),
            }

    def list_sessions(self, limit: int = 10) -> list[dict]:
        """Return recent sessions sorted by last_active descending."""
        with SessionLocal() as db:
            summaries = backend_sm.list_sessions(db, CLI_USER_ID, page=1, page_size=limit)
            return [
                {
                    "id": s.id,
                    "thread_id": self._get_thread_id(db, s.id), # list_sessions doesn't return thread_id, we fetch it
                    "name": s.title,
                    "created_at": s.created_at.isoformat(),
                    "last_active": s.updated_at.isoformat(),
                    "turn_count": s.message_count // 2,
                }
                for s in summaries
            ]
            
    def _get_thread_id(self, db, session_id: str) -> str:
        from backend.models.session import ChatSession
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        return session.thread_id if session else ""

    def update_session(
        self,
        thread_id: str,
        turn_count: int | None = None,
        first_message: str = "",
    ):
        """Update a session's last_active time and optionally auto-name it."""
        with SessionLocal() as db:
            from backend.models.session import ChatSession
            session = db.query(ChatSession).filter(
                ChatSession.thread_id == thread_id,
                ChatSession.user_id == CLI_USER_ID
            ).first()
            
            if not session:
                return
                
            session.updated_at = datetime.now(timezone.utc)
            
            if first_message and session.title in ("New Chat", "", None):
                session.title = first_message[:50].strip()
                
            db.commit()

    def rename_session(self, thread_id: str, new_name: str) -> bool:
        """Rename a session. Returns True on success."""
        with SessionLocal() as db:
            from backend.models.session import ChatSession
            session = db.query(ChatSession).filter(
                ChatSession.thread_id == thread_id,
                ChatSession.user_id == CLI_USER_ID
            ).first()
            
            if not session:
                return False
                
            backend_sm.rename_session(db, CLI_USER_ID, session.id, new_name)
            return True

    def session_age_minutes(self, session: dict) -> float:
        """How many minutes ago was this session last active."""
        try:
            last = datetime.fromisoformat(session["last_active"])
            now = datetime.now(timezone.utc)
            return (now - last).total_seconds() / 60
        except (KeyError, ValueError, TypeError):
            return float("inf")
