import unittest
import uuid

from fastapi import HTTPException
from langchain_core.messages import AIMessage, HumanMessage

from agent.runtime.events import StreamEvent, StreamEventType
from backend.models.run import AgentRun
from backend.routers.runs import get_session_runs
from backend.services.run_context import RunContextSnapshot
from backend.services.run_manager import claim_agent_run, reconcile_interrupted_runs
from backend.services.run_persistence import (
    RunEventBatcher,
    messages_created_this_turn,
    terminal_from_events,
)
from tests.backend.support import DatabaseTestCase


class RunTerminalTests(unittest.TestCase):
    def test_error_is_failed_not_completed(self):
        terminal = terminal_from_events(
            [StreamEvent(type=StreamEventType.ERROR, content="boom")]
        )
        self.assertEqual(terminal.status, "failed")

    def test_approval_is_waiting(self):
        terminal = terminal_from_events(
            [
                StreamEvent(
                    type=StreamEventType.RUN_WAITING,
                    data={"kind": "tool_approval"},
                )
            ]
        )
        self.assertEqual(terminal.status, "waiting_for_approval")

    def test_done_carries_usage_and_current_turn_assistant_content(self):
        terminal = terminal_from_events(
            [
                StreamEvent(
                    type=StreamEventType.DONE,
                    data={
                        "status": "completed",
                        "token_usage": {"total_tokens": 12},
                        "assistant_content": "final answer",
                    },
                )
            ]
        )
        self.assertEqual(terminal.status, "completed")
        self.assertEqual(terminal.token_usage, {"total_tokens": 12})
        self.assertEqual(terminal.assistant_content, "final answer")

    def test_nonstream_returns_only_new_messages(self):
        messages = messages_created_this_turn(
            {"old"},
            [
                HumanMessage(content="old", id="old"),
                AIMessage(content="new", id="new"),
            ],
        )
        self.assertEqual([message.id for message in messages], ["new"])


class RunEventBatcherTests(unittest.TestCase):
    def test_flushes_at_25_events_and_immediately_on_terminal_event(self):
        batcher = RunEventBatcher(max_size=25)
        for index in range(24):
            self.assertEqual(
                batcher.add(
                    StreamEvent(
                        type=StreamEventType.STATUS,
                        content=f"step {index}",
                    )
                ),
                [],
            )

        full_batch = batcher.add(
            StreamEvent(type=StreamEventType.STATUS, content="step 24")
        )
        self.assertEqual(len(full_batch), 25)

        self.assertEqual(
            len(
                batcher.add(
                    StreamEvent(type=StreamEventType.ERROR, content="boom")
                )
            ),
            1,
        )

    def test_token_events_are_not_persisted(self):
        batcher = RunEventBatcher()
        self.assertEqual(
            batcher.add(StreamEvent(type=StreamEventType.TOKEN, content="word")),
            [],
        )
        self.assertEqual(batcher.flush(), [])


class RunIdentityTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.workspace_record = self.workspace(status="ready")
        self.session.active_workspace_id = self.workspace_record.id
        self.db.commit()
        self.snapshot = RunContextSnapshot(
            user_id=self.user.id,
            session_id=self.session.id,
            thread_id=self.session.thread_id,
            workspace_id=self.workspace_record.id,
            workspace_path=self.workspace_record.storage_path,
            project_id=self.workspace_record.project_id,
            context_version=self.workspace_record.context_version,
            session_context_version=self.session.context_version,
            preferences={},
        )

    def test_client_run_id_is_validated_and_duplicate_is_rejected(self):
        with self.assertRaises(HTTPException) as invalid:
            claim_agent_run(self.db, self.snapshot, "not-a-uuid")
        self.assertEqual(invalid.exception.status_code, 400)

        run_id = str(uuid.uuid4())
        run = claim_agent_run(self.db, self.snapshot, run_id)
        self.assertEqual(run.id, run_id)
        self.assertEqual(run.session_id, self.session.id)

        with self.assertRaises(HTTPException) as duplicate:
            claim_agent_run(self.db, self.snapshot, run_id)
        self.assertEqual(duplicate.exception.status_code, 409)

    def test_run_id_cannot_move_to_another_session(self):
        run_id = str(uuid.uuid4())
        claim_agent_run(self.db, self.snapshot, run_id)
        second_session = self._session(self.user)
        second_workspace = self.workspace(
            status="ready",
            session=second_session,
            user=self.user,
        )
        second_session.active_workspace_id = second_workspace.id
        self.db.commit()
        other_snapshot = RunContextSnapshot(
            user_id=self.user.id,
            session_id=second_session.id,
            thread_id=second_session.thread_id,
            workspace_id=second_workspace.id,
            workspace_path=second_workspace.storage_path,
            project_id=second_workspace.project_id,
            context_version=second_workspace.context_version,
            session_context_version=second_session.context_version,
            preferences={},
        )

        with self.assertRaises(HTTPException) as mismatch:
            claim_agent_run(
                self.db,
                other_snapshot,
                run_id,
                resume=True,
            )
        self.assertEqual(mismatch.exception.status_code, 404)

    def test_resume_reuses_waiting_owned_run(self):
        run_id = str(uuid.uuid4())
        run = claim_agent_run(self.db, self.snapshot, run_id)
        run.status = "waiting_for_approval"
        self.db.commit()

        resumed = claim_agent_run(
            self.db,
            self.snapshot,
            run_id,
            resume=True,
        )

        self.assertEqual(resumed.id, run_id)
        self.assertEqual(resumed.status, "running")
        self.assertIsNone(resumed.ended_at)

    def test_stale_running_rows_are_reconciled_as_interrupted(self):
        run = claim_agent_run(self.db, self.snapshot, str(uuid.uuid4()))

        count = reconcile_interrupted_runs(self.db)

        self.db.refresh(run)
        self.assertEqual(count, 1)
        self.assertEqual(run.status, "interrupted")
        self.assertIsNotNone(run.ended_at)


class RunPaginationTests(DatabaseTestCase):
    def test_run_history_uses_cursor_and_bounded_page(self):
        for index in range(3):
            run = AgentRun(
                id=str(uuid.uuid4()),
                session_id=self.session.id,
                status="completed",
            )
            self.db.add(run)
            self.db.flush()
            run.started_at = run.started_at.replace(microsecond=index)
        self.db.commit()

        first_page = get_session_runs(
            self.session.id,
            cursor=None,
            limit=2,
            current_user=self.user,
            db=self.db,
        )
        self.assertEqual(len(first_page["items"]), 2)
        self.assertIsNotNone(first_page["next_cursor"])

        second_page = get_session_runs(
            self.session.id,
            cursor=first_page["next_cursor"],
            limit=2,
            current_user=self.user,
            db=self.db,
        )
        self.assertEqual(len(second_page["items"]), 1)
        self.assertIsNone(second_page["next_cursor"])


if __name__ == "__main__":
    unittest.main()
