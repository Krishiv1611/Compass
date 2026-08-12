import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import TypedDict
from unittest.mock import patch

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, interrupt

from agent.graph import workflow
from agent.local_sessions import LocalSessionStore
from agent.persistence import get_checkpointer


class _ApprovalState(TypedDict):
    approved: bool


class LocalRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import asyncio

        asyncio.get_running_loop().slow_callback_duration = 1.0

    async def test_missing_db_uri_uses_memory_checkpointer(self):
        with patch.dict(os.environ, {}, clear=True):
            checkpointer = await get_checkpointer(None)
        self.assertIn("memory", checkpointer.__class__.__module__)

    async def test_web_cannot_silently_fall_back(self):
        with self.assertRaisesRegex(RuntimeError, "DB_URI"):
            await get_checkpointer(None, require_durable=True)

    async def test_memory_checkpointer_resumes_an_approval_turn(self):
        async def approval_node(state: _ApprovalState) -> dict:
            decision = interrupt({"kind": "tool_approval"})
            return {"approved": decision["action"] == "approve"}

        builder = StateGraph(_ApprovalState)
        builder.add_node("approval", approval_node)
        builder.add_edge(START, "approval")
        builder.add_edge("approval", END)
        graph = builder.compile(checkpointer=await get_checkpointer(None))
        config = {"configurable": {"thread_id": "local-approval"}}

        await graph.ainvoke({"approved": False}, config)
        result = await graph.ainvoke(
            Command(resume={"action": "approve"}),
            config,
        )

        self.assertTrue(result["approved"])

    async def test_failed_configured_database_fallback_is_not_cached(self):
        await workflow.reset_workflow()
        with (
            patch.dict(os.environ, {"DB_URI": "postgresql://unavailable"}),
            patch(
                "agent.graph.workflow.get_checkpointer",
                side_effect=[InMemorySaver(), InMemorySaver()],
            ),
        ):
            first = await workflow.get_workflow()
            second = await workflow.get_workflow()
        await workflow.reset_workflow()

        self.assertIsNot(first, second)


class MainImportTests(unittest.TestCase):
    def test_main_imports_without_backend_database_settings(self):
        project_root = Path(__file__).resolve().parents[1]
        environment = os.environ.copy()
        environment.pop("DB_URI", None)
        environment["PYTHONPATH"] = str(project_root)
        with tempfile.TemporaryDirectory() as root:
            result = subprocess.run(
                [sys.executable, "-c", "import main"],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)


class LocalSessionStoreTests(unittest.TestCase):
    def test_create_get_rename_touch_and_list_persist_metadata(self):
        with tempfile.TemporaryDirectory() as root:
            store = LocalSessionStore(Path(root))
            first = store.create(
                title="First task",
                project_id="project-1",
                context_version="rev-1",
            )
            second = store.create(
                title="Second task",
                project_id="project-1",
                context_version="rev-2",
            )

            self.assertEqual(
                set(first),
                {
                    "id",
                    "thread_id",
                    "title",
                    "turn_count",
                    "created_at",
                    "updated_at",
                    "project_id",
                    "context_version",
                },
            )
            self.assertEqual(
                store.get(first["thread_id"][:8])["thread_id"],
                first["thread_id"],
            )
            self.assertTrue(store.rename(first["thread_id"], "Renamed task"))
            touched = store.touch(first["thread_id"], turn_count=4)
            self.assertEqual(touched["title"], "Renamed task")
            self.assertEqual(touched["turn_count"], 4)
            self.assertEqual(
                [record["thread_id"] for record in store.list(limit=2)],
                [first["thread_id"], second["thread_id"]],
            )
            reloaded = LocalSessionStore(Path(root))
            self.assertEqual(
                reloaded.get(first["thread_id"])["turn_count"],
                4,
            )


if __name__ == "__main__":
    unittest.main()
