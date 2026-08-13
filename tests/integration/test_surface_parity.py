import unittest

from agent.runtime.artifacts import empty_run_artifact, reduce_run_event
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
                artifact = empty_run_artifact()
                for event in agent.replay(name):
                    artifact = reduce_run_event(artifact, event)
                self.assertEqual(artifact.terminal_status, expected_status[name])
                if scenario["resume"]:
                    agent.resume(scenario["resume"])
                    self.assertEqual(agent.resumes[-1], scenario["resume"])
