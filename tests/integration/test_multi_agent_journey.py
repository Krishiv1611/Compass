import tempfile
import unittest
from pathlib import Path

from agent.checkpoints import list_checkpoints
from agent.runtime.events import StreamEventType
from agent.ui.event_renderer import EventRenderer
from tests.integration.fake_agent import FakeAgent


MUTATING_TOOLS = {"edit_file", "write_to_file", "delete_file", "move_file", "shell_execute"}


def project(events):
    renderer = EventRenderer()
    for event in events:
        artifact = renderer.add(event)
    return artifact


def parity_signature(artifact):
    return {
        "plan": artifact.plan,
        "workers": [
            (worker.task_id, worker.status, worker.evidence_count)
            for worker in artifact.workers
        ],
        "worker_contributions": artifact.walkthrough["worker_contributions"],
        "changed_files": artifact.changed_files,
        "checks": [(check.name, check.status) for check in artifact.checks],
        "usage": artifact.usage,
        "conflicts": artifact.unresolved_conflicts,
        "terminal_status": artifact.terminal_status,
    }


class MultiAgentJourneyTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_bounded_journey_matches_shared_web_recording(self):
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder)
            fake = FakeAgent()
            journey = await fake.run_multi_agent_journey(workspace)
            artifact = project(journey["events"])

            self.assertEqual(journey["maximum_active"], 2)
            self.assertEqual(fake.resumes, [{"action": "approve"}])
            for task in journey["plan"].tasks:
                self.assertTrue(MUTATING_TOOLS.isdisjoint(task.allowed_tools))

            actions = journey["actions"]
            self.assertLess(actions.index("approval_resumed"), actions.index("checkpoint"))
            self.assertLess(actions.index("checkpoint"), actions.index("write"))
            self.assertLess(actions.index("write"), actions.index("hook"))
            self.assertEqual(
                len(list_checkpoints(
                    workspace,
                    workspace_id="acceptance",
                    thread_id="journey",
                )),
                1,
            )
            self.assertEqual(journey["changed_content"], "new content")
            self.assertEqual(journey["hook_status"], "passed")
            self.assertEqual(
                set(journey["usage_by_node"]),
                {"planner", "worker.backend", "worker.web", "synthesizer", "executor"},
            )
            self.assertTrue(artifact.unresolved_conflicts)
            self.assertEqual(artifact.terminal_status, "completed")

            writes = [
                event for event in journey["events"]
                if event.type == StreamEventType.TOOL_CALL
                and event.tool_call
                and event.tool_call.name in MUTATING_TOOLS
            ]
            self.assertEqual(len(writes), 1)
            self.assertEqual(writes[0].data["actor"], "main-executor")

            _recording, replayed_events = fake.multi_agent_journey()
            replayed = project(replayed_events)
            self.assertEqual(parity_signature(replayed), parity_signature(artifact))


if __name__ == "__main__":
    unittest.main()
