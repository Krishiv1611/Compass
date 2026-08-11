import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage

from agent.graph.nodes import (
    check_safety_node,
    clarifier_node,
    plan_approval_node,
)
from agent.runtime.events import StreamEventType
from agent.runtime.protocol import InterruptData, InterruptKind, ResumeAction
from agent.runtime.runner import events_from_interrupts
from backend.services.agent_runner import build_resume_command


class InterruptRuntimeTests(unittest.TestCase):
    def test_clarification_is_not_done(self):
        events = events_from_interrupts(
            [
                {
                    "value": {
                        "kind": "clarification",
                        "prompt": "Which package should be edited?",
                        "tool_calls": [],
                        "plan": None,
                    }
                }
            ]
        )
        self.assertEqual(
            [event.type for event in events],
            [
                StreamEventType.CLARIFICATION_REQUIRED,
                StreamEventType.RUN_WAITING,
            ],
        )

    def test_every_resume_action_preserves_action_and_feedback(self):
        for action in ResumeAction:
            with self.subTest(action=action.value):
                feedback = (
                    "Use the packages directory."
                    if action in (ResumeAction.REVISE_PLAN, ResumeAction.ANSWER)
                    else None
                )
                command = build_resume_command(action, feedback)
                self.assertEqual(
                    command.resume,
                    {"action": action.value, "feedback": feedback},
                )


class InterruptNodeResumeTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_approval_actions_reach_the_safety_node(self):
        expectations = {
            ResumeAction.APPROVE: "approved",
            ResumeAction.ALWAYS: "approved",
            ResumeAction.DENY: "denied",
            ResumeAction.SKIP: "skipped",
        }
        tool_call = {
            "id": "call-1",
            "name": "write_to_file",
            "args": {"path": "a.py", "content": "pass\n"},
            "type": "tool_call",
        }
        state = {
            "messages": [AIMessage(content="", tool_calls=[tool_call])],
            "approved_operations": [],
            "mode": "edit",
        }

        for action, expected_status in expectations.items():
            with self.subTest(action=action.value):
                resume = {"action": action.value, "feedback": "exact feedback"}
                with patch(
                    "langgraph.types.interrupt",
                    return_value=resume,
                ) as fake_interrupt:
                    result = await check_safety_node(
                        state,
                        {"configurable": {}},
                    )
                request = InterruptData.model_validate(
                    fake_interrupt.call_args.args[0]
                )
                self.assertEqual(request.kind, InterruptKind.TOOL_APPROVAL)
                self.assertEqual(result["approval_status"], expected_status)

    async def test_plan_resume_actions_and_revision_feedback(self):
        cases = {
            ResumeAction.EXECUTE_PLAN: None,
            ResumeAction.REVISE_PLAN: "Change the second step.",
            ResumeAction.CANCEL: None,
        }
        state = {"plan": "1. Inspect\n2. Edit", "messages": []}

        for action, feedback in cases.items():
            with self.subTest(action=action.value):
                with patch(
                    "langgraph.types.interrupt",
                    return_value={
                        "action": action.value,
                        "feedback": feedback,
                    },
                ) as fake_interrupt:
                    result = await plan_approval_node(
                        state,
                        {"configurable": {}},
                    )
                request = InterruptData.model_validate(
                    fake_interrupt.call_args.args[0]
                )
                self.assertEqual(request.kind, InterruptKind.PLAN_APPROVAL)
                if action == ResumeAction.REVISE_PLAN:
                    self.assertIn(feedback, result["messages"][0].content)
                elif action == ResumeAction.CANCEL:
                    self.assertTrue(result["is_done"])
                else:
                    self.assertEqual(result, {})

    async def test_clarification_answer_uses_feedback_verbatim(self):
        feedback = "Edit the packages/api directory."
        with patch(
            "langgraph.types.interrupt",
            return_value={
                "action": ResumeAction.ANSWER.value,
                "feedback": feedback,
            },
        ) as fake_interrupt:
            result = await clarifier_node(
                {"messages": []},
                {"configurable": {}},
            )
        request = InterruptData.model_validate(fake_interrupt.call_args.args[0])
        self.assertEqual(request.kind, InterruptKind.CLARIFICATION)
        self.assertEqual(
            result["messages"][0].content,
            f"User clarification: {feedback}",
        )


if __name__ == "__main__":
    unittest.main()
