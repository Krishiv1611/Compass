"""Reusable SQLite fixtures for backend service tests."""

from __future__ import annotations

import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.models import Base, ChatSession, Message, User, Workspace


def stub_workspace(*, file_count: int = 0, size_bytes: int = 0):
    """Return a plain workspace-shaped value for service boundary tests."""
    return SimpleNamespace(file_count=file_count, size_bytes=size_bytes)


class DatabaseTestCase(unittest.TestCase):
    """Create an isolated relational database and filesystem per test."""

    def setUp(self):
        self._temp_directory = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_directory.name)
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def _enable_foreign_keys(connection, _record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(self.engine)
        session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.db = session_factory()

        self.user = self._user("owner@example.test")
        self.other_user = self._user("other@example.test")
        self.session = self._session(self.user)
        self.other_session = self._session(self.other_user)
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        self._temp_directory.cleanup()

    def _user(self, email: str) -> User:
        user = User(
            id=uuid.uuid4().hex,
            email=email,
            hashed_password="test-only",
            is_active=True,
        )
        self.db.add(user)
        self.db.flush()
        return user

    def _session(self, user: User) -> ChatSession:
        session = ChatSession(
            id=uuid.uuid4().hex,
            user_id=user.id,
            title="Test session",
            thread_id=uuid.uuid4().hex,
        )
        self.db.add(session)
        self.db.flush()
        return session

    def workspace(
        self,
        *,
        status: str = "ready",
        project_id: str | None = None,
        user: User | None = None,
        session: ChatSession | None = None,
        source_type: str = "upload",
    ) -> Workspace:
        owner = user or self.user
        chat_session = session or self.session
        workspace_id = uuid.uuid4().hex
        storage_path = self.root / workspace_id
        storage_path.mkdir(parents=True)
        record = Workspace(
            id=workspace_id,
            user_id=owner.id,
            session_id=chat_session.id,
            name=f"Workspace {workspace_id[:6]}",
            storage_path=str(storage_path),
            source_type=source_type,
            status=status,
            project_id=project_id or f"workspace:{workspace_id}",
            context_version="content:test",
        )
        self.db.add(record)
        self.db.flush()
        return record

    def github_workspace(self) -> Workspace:
        workspace = self.workspace(source_type="github", project_id="github:owner/repo")
        workspace.git_remote = "https://github.com/owner/repo"
        workspace.git_branch = "main"
        workspace.git_head = "a" * 40
        self.db.flush()
        return workspace

    def add_messages(self, count: int) -> list[Message]:
        messages = [
            Message(
                id=uuid.uuid4().hex,
                session_id=self.session.id,
                role="user",
                content=f"message {index}",
            )
            for index in range(count)
        ]
        self.db.add_all(messages)
        self.db.flush()
        return messages
