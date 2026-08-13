"""Shared runtime contract tests that require no model or database."""

import asyncio
import unittest
from pathlib import Path

from agent.runtime.events import StreamEvent, StreamEventType
from agent.runtime.runner import build_turn_input, stream_agent_events
from backend.schemas.chat import StreamEvent as WebStreamEvent


class SharedRuntimeTests(unittest.TestCase):
    def test_turn_input_resets_transient_graph_state(self):
        payload = build_turn_input("Rename the button", mode="normal")

        self.assertEqual(payload["mode"], "edit")
        self.assertEqual(payload["plan"], "")
        self.assertEqual(payload["pending_tool_calls"], [])
        self.assertIsNone(payload["approval_status"])
        self.assertFalse(payload["loop_detected"])
        self.assertFalse(payload["syntax_checked"])

    def test_skill_directive_survives_shared_input_builder(self):
        skill = {"name": "code-review", "arguments": "agent/"}
        payload = build_turn_input(
            "/code-review agent/",
            active_skill=skill,
        )
        self.assertEqual(payload["active_skill"], skill)

    def test_web_socket_schema_accepts_selected_skill(self):
        from backend.schemas.chat import WsClientMessage

        message = WsClientMessage.model_validate(
            {"type": "message", "content": "review", "active_skill": "code-review"}
        )
        self.assertEqual(message.active_skill, "code-review")

    def test_web_and_tui_share_the_same_event_model(self):
        self.assertIs(WebStreamEvent, StreamEvent)
        event = StreamEvent(
            type=StreamEventType.APPROVAL_REQUIRED,
            data={"reason": "plan_approval_required"},
        )
        self.assertEqual(event.type, StreamEventType.APPROVAL_REQUIRED)

    def test_tui_has_no_private_graph_stream_loop(self):
        source = Path("agent/ui/tui.py").read_text(encoding="utf-8-sig")
        self.assertNotIn("workflow.astream(", source)
        self.assertIn("stream_agent_events(", source)


class RuntimeCancellationTests(unittest.IsolatedAsyncioTestCase):
    async def test_pre_cancelled_turn_ends_without_loading_the_graph(self):
        cancel_event = asyncio.Event()
        cancel_event.set()
        events = [
            event
            async for event in stream_agent_events(
                {"messages": []},
                {"configurable": {}},
                cancel_event=cancel_event,
            )
        ]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, StreamEventType.DONE)
        self.assertEqual(events[0].data["status"], "cancelled")

if __name__ == "__main__":
    unittest.main()
