import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from langchain_core.messages import AIMessage, HumanMessage

from agent.checkpoints import create_checkpoint
from backend.models.message import Message
from backend.models.session import ChatSession
from backend.routers.sessions import fork_existing_session
from backend.schemas.session import SessionForkRequest
from backend.services.session_fork import fork_session
from tests.backend.support import DatabaseTestCase


class FakeWorkflow:
    def __init__(self, source_thread_id: str):
        self.source_thread_id = source_thread_id
        self.updated = []

    async def aget_state(self, config):
        thread_id = config["configurable"]["thread_id"]
        if thread_id != self.source_thread_id:
            return SimpleNamespace(values={})
        return SimpleNamespace(
            values={
                "messages": [
                    HumanMessage(content="before checkpoint"),
                    AIMessage(content="before reply"),
                    HumanMessage(content="after checkpoint"),
                ],
                "summary": "Later summary that must not leak",
                "plan": "1. Later plan that must not leak",
                "approved_operations": ["read_file"],
                "pending_tool_calls": [{"id": "must-clear"}],
                "approval_status": "approved",
                "loop_count": 2,
                "goal_iteration": 3,
            }
        )

    async def aget_state_history(self, _config):
        yield SimpleNamespace(
            created_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
            values={
                "messages": [
                    HumanMessage(content="before checkpoint"),
                    AIMessage(content="before reply"),
                ],
                "summary": "Checkpoint summary",
                "plan": "1. Checkpoint plan",
                "approved_operations": ["read_file"],
                "pending_tool_calls": [],
                "approval_status": None,
                "loop_count": 0,
                "goal_iteration": 0,
            },
        )

    async def aupdate_state(self, config, values):
        self.updated.append((config, values))


class FailingUpdateWorkflow(FakeWorkflow):
    async def aupdate_state(self, _config, _values):
        raise OSError("graph write failed")


class SessionForkTests(DatabaseTestCase, unittest.IsolatedAsyncioTestCase):
    async def test_checkpoint_fork_isolated_workspace_and_history(self):
        workspace = self.workspace()
        self.session.active_workspace_id = workspace.id
        source_root = Path(workspace.storage_path)
        (source_root / "app.py").write_text("before edit", encoding="utf-8")
        (source_root / "other.py").write_text("before later edit", encoding="utf-8")
        (source_root / "asset.bin").write_bytes(b"\x00\x01")
        (source_root / ".env").write_text("TOKEN=secret", encoding="utf-8")
        (source_root / "node_modules").mkdir()
        (source_root / "node_modules" / "cache.js").write_text("cache", encoding="utf-8")

        message_time = datetime.now(timezone.utc) - timedelta(seconds=2)
        first = Message(
            session_id=self.session.id,
            role="user",
            content="before checkpoint",
            created_at=message_time,
        )
        reply = Message(
            session_id=self.session.id,
            role="assistant",
            content="before reply",
            created_at=message_time + timedelta(milliseconds=1),
        )
        self.db.add_all([first, reply])
        self.db.commit()
        checkpoint = create_checkpoint(
            source_root,
            ["app.py"],
            workspace_id=workspace.id,
            thread_id=self.session.thread_id,
            label="before edit",
        )
        (source_root / "app.py").write_text("after edit", encoding="utf-8")
        create_checkpoint(
            source_root,
            ["other.py"],
            workspace_id=workspace.id,
            thread_id=self.session.thread_id,
            label="later edit",
        )
        (source_root / "other.py").write_text("after later edit", encoding="utf-8")
        self.db.add(
            Message(
                session_id=self.session.id,
                role="user",
                content="after checkpoint",
            )
        )
        self.db.commit()
        workflow = FakeWorkflow(self.session.thread_id)

        fork = await fork_session(
            self.session.id,
            self.user.id,
            checkpoint.id,
            db=self.db,
            workflow=workflow,
        )

        self.assertNotEqual(fork.id, self.session.id)
        self.assertNotEqual(fork.thread_id, self.session.thread_id)
        self.assertNotEqual(fork.active_workspace_id, workspace.id)
        fork_root = Path(fork.active_workspace.storage_path)
        self.assertEqual((fork_root / "app.py").read_text(encoding="utf-8"), "before edit")
        self.assertEqual(
            (fork_root / "other.py").read_text(encoding="utf-8"),
            "before later edit",
        )
        self.assertEqual((fork_root / "asset.bin").read_bytes(), b"\x00\x01")
        self.assertFalse((fork_root / ".env").exists())
        self.assertFalse((fork_root / "node_modules").exists())
        self.assertFalse((fork_root / ".compass" / "checkpoints").exists())

        (fork_root / "app.py").write_text("fork only", encoding="utf-8")
        self.assertEqual((source_root / "app.py").read_text(encoding="utf-8"), "after edit")

        copied_messages = [
            message.content for message in fork.messages if message.role != "system"
        ]
        self.assertEqual(copied_messages, ["before checkpoint", "before reply"])
        fork_event = next(message for message in fork.messages if message.role == "system")
        self.assertEqual(fork_event.tool_calls["event"], "session_forked")
        _, copied_state = workflow.updated[-1]
        self.assertEqual(
            [message.content for message in copied_state["messages"][:-1]],
            ["before checkpoint", "before reply"],
        )
        self.assertEqual(copied_state["summary"], "Checkpoint summary")
        self.assertEqual(copied_state["plan"], "1. Checkpoint plan")
        self.assertEqual(copied_state["approved_operations"], [])
        self.assertEqual(copied_state["pending_tool_calls"], [])
        self.assertIsNone(copied_state["approval_status"])
        self.assertEqual(copied_state["loop_count"], 0)
        self.assertEqual(copied_state["goal_iteration"], 0)
        self.assertEqual(copied_state["messages"][-1].additional_kwargs["event"], "session_forked")

    async def test_another_user_cannot_fork_session(self):
        with self.assertRaises(HTTPException) as denied:
            await fork_session(
                self.session.id,
                self.other_user.id,
                db=self.db,
                workflow=FakeWorkflow(self.session.thread_id),
            )

        self.assertEqual(denied.exception.status_code, 404)
        self.assertEqual(self.db.query(ChatSession).count(), 2)

    async def test_failed_copy_removes_partial_rows_and_directory(self):
        workspace = self.workspace()
        self.session.active_workspace_id = workspace.id
        self.db.commit()
        parent = Path(workspace.storage_path).parent
        directories_before = {path.name for path in parent.iterdir() if path.is_dir()}

        def fail_after_creating_partial(_source, target):
            target.mkdir(parents=True)
            (target / "partial.txt").write_text("partial", encoding="utf-8")
            raise OSError("copy failed")

        with patch(
            "backend.services.session_fork._copy_workspace",
            side_effect=fail_after_creating_partial,
        ):
            with self.assertRaises(OSError):
                await fork_session(
                    self.session.id,
                    self.user.id,
                    db=self.db,
                    workflow=FakeWorkflow(self.session.thread_id),
                )

        self.assertEqual(self.db.query(ChatSession).count(), 2)
        self.assertEqual(
            {path.name for path in parent.iterdir() if path.is_dir()},
            directories_before,
        )

    async def test_session_endpoint_returns_the_owned_fork_detail(self):
        workspace = self.workspace()
        self.session.active_workspace_id = workspace.id
        self.db.commit()
        workflow = FakeWorkflow(self.session.thread_id)
        forked = await fork_session(
            self.session.id,
            self.user.id,
            db=self.db,
            workflow=workflow,
        )

        async def return_fork(*_args, **_kwargs):
            return forked

        with patch("backend.routers.sessions.fork_session", side_effect=return_fork):
            detail = await fork_existing_session(
                self.session.id,
                SessionForkRequest(),
                current_user=self.user,
                db=self.db,
            )

        self.assertEqual(detail.id, forked.id)
        self.assertEqual(detail.active_workspace_id, forked.active_workspace_id)

    async def test_fork_file_limit_rejects_and_cleans_up(self):
        workspace = self.workspace()
        self.session.active_workspace_id = workspace.id
        source_root = Path(workspace.storage_path)
        (source_root / "one.txt").write_text("one", encoding="utf-8")
        (source_root / "two.txt").write_text("two", encoding="utf-8")
        self.db.commit()
        directories_before = {
            path.name for path in source_root.parent.iterdir() if path.is_dir()
        }

        with patch("backend.services.session_fork.MAX_FORK_FILES", 1):
            with self.assertRaises(HTTPException) as rejected:
                await fork_session(
                    self.session.id,
                    self.user.id,
                    db=self.db,
                    workflow=FakeWorkflow(self.session.thread_id),
                )

        self.assertEqual(rejected.exception.status_code, 413)
        self.assertEqual(self.db.query(ChatSession).count(), 2)
        self.assertEqual(
            {path.name for path in source_root.parent.iterdir() if path.is_dir()},
            directories_before,
        )

    async def test_graph_failure_compensates_database_and_workspace(self):
        workspace = self.workspace()
        self.session.active_workspace_id = workspace.id
        source_root = Path(workspace.storage_path)
        (source_root / "app.py").write_text("source", encoding="utf-8")
        self.db.commit()
        directories_before = {
            path.name for path in source_root.parent.iterdir() if path.is_dir()
        }

        with self.assertRaises(OSError):
            await fork_session(
                self.session.id,
                self.user.id,
                db=self.db,
                workflow=FailingUpdateWorkflow(self.session.thread_id),
            )

        self.assertEqual(self.db.query(ChatSession).count(), 2)
        self.assertEqual(
            {path.name for path in source_root.parent.iterdir() if path.is_dir()},
            directories_before,
        )


if __name__ == "__main__":
    unittest.main()
