import asyncio
import unittest
import uuid
from dataclasses import FrozenInstanceError
from pathlib import Path
from threading import get_ident
from types import SimpleNamespace
from unittest.mock import patch

from agent.runtime.events import StreamEvent, StreamEventType
from backend.auth.credentials import encrypt_credential
from backend.routers import chat, uploads
from backend.schemas.chat import WsClientMessage
from backend.services import agent_runner
from backend.services.run_context import RunContextSnapshot
from backend.services.run_context import load_run_context
from tests.backend.support import DatabaseTestCase


class RunContextTests(DatabaseTestCase):
    def test_snapshot_contains_plain_values_and_is_immutable(self):
        workspace = self.workspace(status="ready", project_id="project-stable")
        self.session.active_workspace_id = workspace.id
        self.user.preferences = {"model": "test/model"}
        self.db.commit()

        with patch(
            "backend.services.run_context.SessionLocal",
            self.SessionLocal,
        ):
            snapshot = load_run_context(self.session.id, self.user.id)

        self.assertEqual(snapshot.workspace_id, workspace.id)
        self.assertEqual(snapshot.workspace_path, workspace.storage_path)
        self.assertEqual(snapshot.thread_id, self.session.thread_id)
        self.assertEqual(snapshot.project_id, "project-stable")
        self.assertEqual(snapshot.preferences, {"model": "test/model"})
        with self.assertRaises(FrozenInstanceError):
            snapshot.workspace_id = "other"

    def test_preferences_are_copied_out_of_the_database_model(self):
        workspace = self.workspace(status="ready")
        self.session.active_workspace_id = workspace.id
        self.user.preferences = {"safe_mode": True}
        self.db.commit()

        with patch(
            "backend.services.run_context.SessionLocal",
            self.SessionLocal,
        ):
            snapshot = load_run_context(self.session.id, self.user.id)

        self.user.preferences["safe_mode"] = False
        self.assertEqual(snapshot.preferences, {"safe_mode": True})


class AgentRunnerSnapshotTests(unittest.IsolatedAsyncioTestCase):
    async def test_runner_builds_web_config_only_from_snapshot(self):
        snapshot = RunContextSnapshot(
            user_id="user-1",
            session_id="session-1",
            thread_id="thread-1",
            workspace_id="workspace-1",
            workspace_path=str(Path.cwd()),
            project_id="project-1",
            context_version="content:new",
            session_context_version="content:old",
            preferences={
                "llm_provider": "openrouter",
                "model": "test/model",
                "llm_credentials_encrypted": {
                    "openrouter": encrypt_credential("test-key"),
                },
            },
            source_type="upload",
        )

        async def invoke(_input, config):
            self.assertEqual(config["configurable"]["user_id"], "user-1")
            self.assertEqual(config["configurable"]["workspace_id"], "workspace-1")
            self.assertEqual(config["configurable"]["project_id"], "project-1")
            self.assertTrue(config["configurable"]["context_mismatch"])
            self.assertEqual(config["configurable"]["model"], "test/model")
            return []

        with (
            patch.object(
                agent_runner,
                "get_run_config",
                return_value={"configurable": {}},
            ),
            patch.object(agent_runner, "build_turn_input", return_value={}),
            patch.object(agent_runner, "invoke_agent", side_effect=invoke),
        ):
            result = await agent_runner.run_agent_sync(
                user_message="hello",
                snapshot=snapshot,
            )

        self.assertEqual(result, [])

    async def test_stream_runner_passes_selected_skill_to_turn_input(self):
        snapshot = RunContextSnapshot(
            user_id="user-1",
            session_id="session-1",
            thread_id="thread-1",
            workspace_id="workspace-1",
            workspace_path=str(Path.cwd()),
            project_id="project-1",
            context_version="content:new",
            session_context_version="content:new",
            preferences={
                "llm_provider": "openrouter",
                "model": "test/model",
                "llm_credentials_encrypted": {
                    "openrouter": encrypt_credential("test-key"),
                },
            },
            source_type="upload",
        )

        async def stream(_input, _config, cancel_event=None):
            yield StreamEvent(type=StreamEventType.DONE)

        with (
            patch.object(agent_runner, "get_run_config", return_value={"configurable": {}}),
            patch.object(agent_runner, "build_turn_input", return_value={}) as build,
            patch.object(agent_runner, "stream_agent_events", side_effect=stream),
        ):
            events = [
                event
                async for event in agent_runner.run_agent_stream(
                    user_message="review this",
                    snapshot=snapshot,
                    active_skill="code-review",
                )
            ]

        self.assertEqual(events[0].type, StreamEventType.DONE)
        self.assertEqual(
            build.call_args.kwargs["active_skill"],
            {"name": "code-review", "arguments": ""},
        )


class _TrackingSession:
    def __init__(self, database, tracker):
        self._database = database
        self._tracker = tracker
        self._closed = False
        tracker.active += 1

    def __getattr__(self, name):
        return getattr(self._database, name)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def close(self):
        if not self._closed:
            self._closed = True
            self._database.close()
            self._tracker.active -= 1


class _TrackingSessionFactory:
    def __init__(self, factory):
        self._factory = factory
        self.active = 0

    def __call__(self):
        return _TrackingSession(self._factory(), self)


class AsyncBoundaryTests(DatabaseTestCase):
    def test_chat_closes_database_before_runner_first_yield(self):
        workspace = self.workspace(status="ready")
        self.session.active_workspace_id = workspace.id
        self.db.commit()
        snapshot = RunContextSnapshot(
            user_id=self.user.id,
            session_id=self.session.id,
            thread_id=self.session.thread_id,
            workspace_id=workspace.id,
            workspace_path=workspace.storage_path,
            project_id=workspace.project_id,
            context_version=workspace.context_version,
            session_context_version=self.session.context_version,
            preferences={},
        )
        tracker = _TrackingSessionFactory(self.SessionLocal)
        active_at_runner_start = []

        async def slow_runner(**_kwargs):
            await asyncio.sleep(0)
            active_at_runner_start.append(tracker.active)
            yield StreamEvent(type=StreamEventType.DONE)

        async def consume_turn():
            return [
                event
                async for event in chat._stream_agent_turn(
                    snapshot,
                    WsClientMessage(
                        type="message",
                        content="hello",
                        run_id=str(uuid.uuid4()),
                    ),
                )
            ]

        with (
            patch.object(chat, "SessionLocal", tracker),
            patch.object(chat.agent_runner, "run_agent_stream", slow_runner),
        ):
            events = asyncio.run(consume_turn())

        self.assertEqual([event.type for event in events], [StreamEventType.DONE])
        self.assertEqual(active_at_runner_start, [0])
        self.assertEqual(tracker.active, 0)

    def test_upload_indexing_runs_off_the_event_loop_thread(self):
        loop_thread = get_ident()
        index_threads = []

        def indexer(*_args, **_kwargs):
            index_threads.append(get_ident())
            return SimpleNamespace(chunks_added=2)

        async def index_upload():
            with patch.object(uploads, "index_uploaded_file", indexer):
                return await uploads._index_uploaded_file_off_loop(
                    Path("document.txt"),
                    document_id="upload-1",
                    filename="document.txt",
                    user_id="user-1",
                    session_id="session-1",
                    content_type="text/plain",
                )

        result = asyncio.run(index_upload())

        self.assertEqual(result.chunks_added, 2)
        self.assertEqual(len(index_threads), 1)
        self.assertNotEqual(index_threads[0], loop_thread)


if __name__ == "__main__":
    unittest.main()
