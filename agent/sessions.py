"""Session metadata facade for local TUI and database-backed runs."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from agent.local_sessions import LocalSessionStore
from agent.workspace import WorkspaceContext, discover_local_workspace


CLI_USER_ID = "local_cli_user"


def _local_view(record: dict) -> dict:
    return {
        **record,
        "name": record["title"],
        "last_active": record["updated_at"],
    }


class _LocalSessionAdapter:
    def __init__(self, workspace: WorkspaceContext):
        self.workspace = workspace
        self.store = LocalSessionStore(workspace.root)

    def create_session(self, name: str = "") -> dict:
        return _local_view(
            self.store.create(
                title=name,
                project_id=self.workspace.project_id,
                context_version=self.workspace.context_version,
            )
        )

    def get_session(self, thread_id_prefix: str) -> dict | None:
        record = self.store.get(thread_id_prefix)
        return _local_view(record) if record else None

    def get_last_session(self) -> dict | None:
        records = self.store.list(limit=1)
        return _local_view(records[0]) if records else None

    def list_sessions(self, limit: int = 10) -> list[dict]:
        return [_local_view(record) for record in self.store.list(limit=limit)]

    def update_session(
        self,
        thread_id: str,
        turn_count: int | None = None,
        first_message: str = "",
    ) -> None:
        existing = self.store.get(thread_id)
        title = None
        if (
            existing
            and first_message
            and existing["title"] in ("New Chat", "")
        ):
            title = first_message[:50].strip()
        self.store.touch(thread_id, turn_count=turn_count, title=title)

    def rename_session(self, thread_id: str, new_name: str) -> bool:
        return self.store.rename(thread_id, new_name.strip())


class _DatabaseSessionAdapter:
    """Backend adapter whose database imports occur only when selected."""

    def __init__(self, workspace: WorkspaceContext):
        from backend.db import SessionLocal
        from backend.models.user import User

        self.workspace = workspace
        self._session_factory = SessionLocal
        with SessionLocal() as db:
            user = db.query(User).filter(User.id == CLI_USER_ID).first()
            if not user:
                db.add(
                    User(
                        id=CLI_USER_ID,
                        email="cli@compass.local",
                        display_name="CLI User",
                    )
                )
                db.commit()

    @staticmethod
    def _view(session, *, turn_count: int = 0) -> dict:
        return {
            "id": session.id,
            "thread_id": session.thread_id,
            "name": session.title,
            "title": session.title,
            "created_at": session.created_at.isoformat(),
            "last_active": session.updated_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "turn_count": turn_count,
            "project_id": session.project_id,
            "git_remote": session.git_remote,
            "git_branch": session.git_branch,
            "git_head": session.git_head,
            "context_version": session.context_version,
        }

    def create_session(self, name: str = "") -> dict:
        from backend.services import session_manager

        with self._session_factory() as db:
            session = session_manager.create_session(
                db,
                CLI_USER_ID,
                title=name,
            )
            session.project_id = self.workspace.project_id
            session.git_remote = self.workspace.git_remote
            session.git_branch = self.workspace.git_branch
            session.git_head = self.workspace.git_head
            session.context_version = self.workspace.context_version
            db.commit()
            db.refresh(session)
            return self._view(session)

    def get_session(self, thread_id_prefix: str) -> dict | None:
        from backend.models.session import ChatSession

        with self._session_factory() as db:
            session = (
                db.query(ChatSession)
                .filter(
                    ChatSession.user_id == CLI_USER_ID,
                    ChatSession.is_deleted.is_(False),
                    ChatSession.thread_id.startswith(thread_id_prefix),
                )
                .order_by(ChatSession.updated_at.desc())
                .first()
            )
            return self._view(session) if session else None

    def get_last_session(self) -> dict | None:
        from backend.models.session import ChatSession

        with self._session_factory() as db:
            session = (
                db.query(ChatSession)
                .filter(
                    ChatSession.user_id == CLI_USER_ID,
                    ChatSession.is_deleted.is_(False),
                )
                .order_by(ChatSession.updated_at.desc())
                .first()
            )
            return self._view(session) if session else None

    def list_sessions(self, limit: int = 10) -> list[dict]:
        from backend.models.message import Message
        from backend.models.session import ChatSession

        with self._session_factory() as db:
            sessions = (
                db.query(ChatSession)
                .filter(
                    ChatSession.user_id == CLI_USER_ID,
                    ChatSession.is_deleted.is_(False),
                )
                .order_by(ChatSession.updated_at.desc())
                .limit(limit)
                .all()
            )
            return [
                self._view(
                    session,
                    turn_count=(
                        db.query(Message)
                        .filter(Message.session_id == session.id)
                        .count()
                        // 2
                    ),
                )
                for session in sessions
            ]

    def update_session(
        self,
        thread_id: str,
        turn_count: int | None = None,
        first_message: str = "",
    ) -> None:
        from backend.models.session import ChatSession

        with self._session_factory() as db:
            session = (
                db.query(ChatSession)
                .filter(
                    ChatSession.thread_id == thread_id,
                    ChatSession.user_id == CLI_USER_ID,
                )
                .first()
            )
            if not session:
                return
            session.updated_at = datetime.now(timezone.utc)
            if first_message and session.title in ("New Chat", "", None):
                session.title = first_message[:50].strip()
            db.commit()

    def rename_session(self, thread_id: str, new_name: str) -> bool:
        from backend.models.session import ChatSession
        from backend.services import session_manager

        with self._session_factory() as db:
            session = (
                db.query(ChatSession)
                .filter(
                    ChatSession.thread_id == thread_id,
                    ChatSession.user_id == CLI_USER_ID,
                )
                .first()
            )
            if not session:
                return False
            session_manager.rename_session(
                db,
                CLI_USER_ID,
                session.id,
                new_name,
            )
            return True


class SessionManager:
    """Select local JSON metadata unless a database is explicitly configured."""

    def __init__(self):
        self.workspace = discover_local_workspace()
        adapter_type = (
            _DatabaseSessionAdapter
            if os.environ.get("DB_URI")
            else _LocalSessionAdapter
        )
        self._adapter = adapter_type(self.workspace)

    def create_session(self, name: str = "") -> dict:
        return self._adapter.create_session(name)

    def get_session(self, thread_id_prefix: str) -> dict | None:
        return self._adapter.get_session(thread_id_prefix)

    def get_last_session(self) -> dict | None:
        return self._adapter.get_last_session()

    def list_sessions(self, limit: int = 10) -> list[dict]:
        return self._adapter.list_sessions(limit)

    def update_session(
        self,
        thread_id: str,
        turn_count: int | None = None,
        first_message: str = "",
    ) -> None:
        self._adapter.update_session(thread_id, turn_count, first_message)

    def rename_session(self, thread_id: str, new_name: str) -> bool:
        return self._adapter.rename_session(thread_id, new_name)

    @staticmethod
    def session_age_minutes(session: dict) -> float:
        try:
            last = datetime.fromisoformat(session["last_active"])
            return (datetime.now(timezone.utc) - last).total_seconds() / 60
        except (KeyError, ValueError, TypeError):
            return float("inf")
