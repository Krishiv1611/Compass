import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from agent.runtime.artifacts import empty_run_artifact, reduce_run_event
from agent.runtime.events import StreamEvent
from agent.runtime.runner import ToolCallAssembler, events_for_node_artifacts
from backend.routers.runs import serialize_run_event


FIXTURE = Path(__file__).parent / "fixtures" / "run_events" / "basic_edit.json"


class RunArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_projects_basic_edit_fixture(self):
        artifact = empty_run_artifact()
        for payload in self.fixture["events"]:
            artifact = reduce_run_event(artifact, StreamEvent.model_validate(payload))

        self.assertEqual(
            artifact.model_dump(mode="json"),
            self.fixture["expected"],
        )

    def test_assembles_split_tool_call_once_with_real_id_and_arguments(self):
        assembler = ToolCallAssembler()
        emitted = []
        for chunk in self.fixture["tool_call_chunks"]:
            emitted.extend(assembler.add(chunk))

        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0].tool_call.id, "call-read")
        self.assertEqual(emitted[0].tool_call.name, "read_file")
        self.assertEqual(emitted[0].tool_call.args, {"path": "src/app.py"})

    def test_reuses_provider_index_for_a_later_tool_call(self):
        assembler = ToolCallAssembler()

        first = assembler.add(
            {"index": 0, "id": "call-one", "name": "read_file", "args": {"path": "a.py"}}
        )
        second = assembler.add(
            {"index": 0, "id": "call-two", "name": "read_file", "args": {"path": "b.py"}}
        )

        self.assertEqual(
            [event.tool_call.id for event in first + second],
            ["call-one", "call-two"],
        )

    def test_mutating_tool_result_projects_changed_file(self):
        from agent.runtime.runner import workspace_patch_for_tool_result

        event = workspace_patch_for_tool_result(
            tool_call_id="edit-1",
            tool_name="edit_file",
            tool_args={"path": "src/app.py"},
            status="success",
            result_content="Successfully edited src/app.py",
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.data, {"affected_files": ["src/app.py"]})
        self.assertIsNone(
            workspace_patch_for_tool_result(
                tool_call_id="read-1",
                tool_name="read_file",
                tool_args={"path": "src/app.py"},
                status="success",
                result_content="contents",
            )
        )
        self.assertIsNone(
            workspace_patch_for_tool_result(
                tool_call_id="edit-2",
                tool_name="edit_file",
                tool_args={"path": "src/app.py"},
                status="success",
                result_content="Error: old_content not found",
            )
        )
        self.assertIsNone(
            workspace_patch_for_tool_result(
                tool_call_id="edit-3",
                tool_name="edit_file",
                tool_args={"path": "../secret.py"},
                status="success",
                result_content="Access denied: path escapes the workspace directory.",
            )
        )

    def test_projects_plan_step_and_check_from_node_outputs(self):
        step_events = events_for_node_artifacts("executor", {"current_step": 2})
        check_events = events_for_node_artifacts(
            "linter_node",
            {"syntax_check_failed": False},
        )

        self.assertEqual(step_events[0].type.value, "plan_step")
        self.assertEqual(step_events[0].data, {"step": 2, "status": "completed"})
        self.assertEqual(check_events[0].type.value, "check_result")
        self.assertEqual(check_events[0].data["status"], "passed")

        checkpoint_events = events_for_node_artifacts(
            "tools",
            {"last_checkpoint_id": "abc", "checkpoint_files": ["app.py"]},
        )
        self.assertEqual(checkpoint_events[0].type.value, "checkpoint_created")
        self.assertEqual(checkpoint_events[0].data["affected_files"], ["app.py"])

    def test_history_serialization_restores_canonical_event_shape(self):
        stored = SimpleNamespace(
            id="stored-1",
            event_type="tool_call",
            content={
                "type": "tool_call",
                "tool_call": {
                    "id": "call-1",
                    "name": "read_file",
                    "args": {"path": "a.py"},
                },
                "seq": 4,
            },
            created_at="2026-08-13T00:00:00Z",
        )

        self.assertEqual(
            serialize_run_event(stored),
            {
                "id": "stored-1",
                "type": "tool_call",
                "tool_call": {
                    "id": "call-1",
                    "name": "read_file",
                    "args": {"path": "a.py"},
                },
                "seq": 4,
                "created_at": "2026-08-13T00:00:00Z",
            },
        )

    def test_check_status_updates_in_place_by_hook_id(self):
        artifact = reduce_run_event(
            empty_run_artifact(),
            StreamEvent(type="check_result", content="tests", data={"id": "hook-1", "status": "pending"}),
        )
        artifact = reduce_run_event(
            artifact,
            StreamEvent(type="check_result", content="tests", data={"id": "hook-1", "status": "passed", "duration_ms": 12}),
        )
        self.assertEqual(len(artifact.checks), 1)
        self.assertEqual(artifact.checks[0].status, "passed")


if __name__ == "__main__":
    unittest.main()
