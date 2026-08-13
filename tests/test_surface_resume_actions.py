import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent.runtime.protocol import ResumeAction
from agent.ui.tui import (
    CLARIFICATION_RESUME_ACTIONS,
    PLAN_RESUME_ACTIONS,
    TOOL_RESUME_ACTIONS,
    _prompt_runtime_approval,
)


ROOT = Path(__file__).resolve().parents[1]


class SurfaceResumeActionTests(unittest.TestCase):
    def test_frontend_protocol_matches_python_protocol(self):
        source = (ROOT / "frontend" / "src" / "types" / "protocol.ts").read_text(
            encoding="utf-8"
        )
        block = source.split("export type ResumeAction =", 1)[1].split(";", 1)[0]
        frontend_actions = set(re.findall(r'"([a-z_]+)"', block))

        self.assertEqual(frontend_actions, {action.value for action in ResumeAction})

    def test_tui_card_action_sets_are_canonical(self):
        self.assertEqual(
            set(TOOL_RESUME_ACTIONS),
            {"approve", "always", "skip", "deny"},
        )
        self.assertEqual(
            set(PLAN_RESUME_ACTIONS),
            {"execute_plan", "revise_plan", "cancel"},
        )
        self.assertEqual(set(CLARIFICATION_RESUME_ACTIONS), {"answer"})

    def test_tui_clarification_preserves_answer(self):
        compass = SimpleNamespace(console=SimpleNamespace(print=lambda *_: None))
        with patch("agent.ui.tui.click.prompt", return_value="Use PostgreSQL"):
            result = _prompt_runtime_approval(
                compass,
                {
                    "reason": "clarification_required",
                    "prompt": "Which database?",
                },
            )

        self.assertEqual(result, {"action": "answer", "feedback": "Use PostgreSQL"})

    def test_tui_tool_prompt_can_skip(self):
        compass = SimpleNamespace(console=SimpleNamespace(print=lambda *_: None))
        with patch("agent.ui.tui.click.prompt", return_value="skip"):
            result = _prompt_runtime_approval(
                compass,
                {"reason": "approval_required", "tool_calls": []},
            )

        self.assertEqual(result, {"action": "skip"})


if __name__ == "__main__":
    unittest.main()
