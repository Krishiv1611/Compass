import unittest

from agent.runtime.protocol import InterruptKind, ResumeAction, ResumePayload


class ProtocolContractTests(unittest.TestCase):
    def test_resume_actions_are_stable(self):
        self.assertEqual(
            {item.value for item in ResumeAction},
            {
                "approve",
                "always",
                "deny",
                "skip",
                "execute_plan",
                "revise_plan",
                "cancel",
                "answer",
            },
        )

    def test_feedback_round_trips(self):
        payload = ResumePayload(
            action=ResumeAction.REVISE_PLAN,
            feedback="Split task 2",
        )
        self.assertEqual(
            payload.model_dump(mode="json"),
            {
                "action": "revise_plan",
                "feedback": "Split task 2",
            },
        )

    def test_interrupt_kinds_are_explicit(self):
        self.assertEqual(
            {item.value for item in InterruptKind},
            {"tool_approval", "plan_approval", "clarification"},
        )


if __name__ == "__main__":
    unittest.main()
