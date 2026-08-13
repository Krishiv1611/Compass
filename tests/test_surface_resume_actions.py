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
from agent.runtime.events import StreamEvent
from agent.ui.event_renderer import EventRenderer, artifact_summary_for_event


ROOT = Path(__file__).resolve().parents[1]


class SurfaceResumeActionTests(unittest.TestCase):
    def test_tui_projection_consumes_canonical_artifact_events(self):
        renderer = EventRenderer()
        event = StreamEvent.model_validate(
            {"type": "workspace_patch", "data": {"affected_files": ["src/app.py"]}}
        )

        artifact = renderer.add(event)

        self.assertEqual(artifact.changed_files, ["src/app.py"])
        self.assertEqual(artifact_summary_for_event(event, artifact), "Changed: src/app.py")

    def test_tui_projection_summarizes_status_waiting_and_terminal_events(self):
        renderer = EventRenderer()
        status = StreamEvent.model_validate({"type": "status", "content": "Planning changes"})
        waiting = StreamEvent.model_validate({"type": "run_waiting", "data": {"status": "waiting_for_approval"}})
        done = StreamEvent.model_validate({"type": "done", "data": {"status": "completed"}})

        self.assertEqual(artifact_summary_for_event(status, renderer.add(status)), "Planning changes")
        self.assertEqual(artifact_summary_for_event(waiting, renderer.add(waiting)), "Run waiting for input")
        self.assertEqual(artifact_summary_for_event(done, renderer.add(done)), "Run completed")

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
