import unittest

from agent.ui.event_renderer import EventRenderer
from tests.integration.fake_agent import FakeAgent


class SurfaceParityTests(unittest.TestCase):
    def test_all_scenarios_project_expected_terminal_and_resume_outcomes(self):
        agent = FakeAgent()
        expected_status = {
            "ask": "completed", "approved_edit": "completed", "plan_revise": "waiting_for_approval",
            "clarification": "waiting_for_approval", "goal_failure": "failed", "cancel": "cancelled",
        }
        for name, scenario in agent.scenarios.items():
            with self.subTest(name=name):
                renderer = EventRenderer()
                for event in agent.replay(name):
                    artifact = renderer.add(event)
                self.assertEqual(artifact.terminal_status, expected_status[name])
                self.assertEqual(
                    artifact.changed_files,
                    ["a.py"] if name == "approved_edit" else [],
                )
                self.assertEqual(
                    [check.status for check in artifact.checks],
                    ["passed"] if name == "approved_edit" else (["failed"] if name == "goal_failure" else []),
                )
                if scenario["resume"]:
                    agent.resume(scenario["resume"])
                    self.assertEqual(agent.resumes[-1], scenario["resume"])
