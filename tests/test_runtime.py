"""Shared runtime contract tests that require no model or database."""

import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.messages import AIMessage

from agent.runtime.events import StreamEvent, StreamEventType
from agent.runtime.runner import build_turn_input, stream_agent_events
from agent.runtime.metrics import current_run_metrics
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

    async def test_done_carries_all_node_metrics_and_resets_context(self):
        class FakeWorkflow:
            calls = 0

            async def aget_state(self, _config):
                self.calls += 1
                if self.calls == 1:
                    return SimpleNamespace(values={"messages": []}, tasks=[])
                return SimpleNamespace(
                    values={"messages": [AIMessage(id="answer", content="done")]},
                    tasks=[],
                )

            async def astream(self, _input, config, stream_mode):
                metrics = current_run_metrics()
                self_outer.assertIsNotNone(metrics)
                with metrics.span("executor.model"):
                    metrics.add_usage(
                        "executor",
                        {"input_tokens": 7, "output_tokens": 3},
                    )
                yield "updates", {"executor": {"messages": []}}

        self_outer = self
        with (
            patch("agent.runtime.runner.get_workflow", return_value=FakeWorkflow()),
            patch("agent.runtime.runner.prepare_turn_context"),
        ):
            events = [
                event
                async for event in stream_agent_events(
                    {"messages": []},
                    {"configurable": {}},
                )
            ]

        done = next(event for event in events if event.type == StreamEventType.DONE)
        self.assertEqual(done.data["metrics"]["total_tokens"], 10)
        self.assertEqual(done.data["metrics"]["calls_by_node"], {"executor": 1})
        self.assertIsNone(current_run_metrics())

    async def test_interrupt_update_does_not_abort_streaming(self):
        class InterruptingWorkflow:
            async def aget_state(self, _config):
                return SimpleNamespace(values={"messages": []}, tasks=[])

            async def astream(self, _input, config, stream_mode):
                yield "updates", {"__interrupt__": ({"value": {}},)}

        with (
            patch("agent.runtime.runner.get_workflow", return_value=InterruptingWorkflow()),
            patch("agent.runtime.runner.prepare_turn_context"),
        ):
            events = [
                event
                async for event in stream_agent_events(
                    {"messages": []},
                    {"configurable": {}},
                )
            ]

        self.assertFalse(any(event.type == StreamEventType.ERROR for event in events))
        self.assertEqual(StreamEventType.DONE, events[-1].type)

    async def test_error_carries_metrics_collected_before_failure(self):
        class FailingWorkflow:
            async def aget_state(self, _config):
                return SimpleNamespace(values={"messages": []}, tasks=[])

            async def astream(self, _input, config, stream_mode):
                metrics = current_run_metrics()
                metrics.add_usage("executor", {"input_tokens": 9, "output_tokens": 2})
                if False:
                    yield None
                raise RuntimeError("provider failed")

        with (
            patch("agent.runtime.runner.get_workflow", return_value=FailingWorkflow()),
            patch("agent.runtime.runner.prepare_turn_context"),
        ):
            events = [
                event async for event in stream_agent_events(
                    {"messages": []}, {"configurable": {}}
                )
            ]

        error = next(event for event in events if event.type == StreamEventType.ERROR)
        self.assertEqual(error.data["token_usage"]["total_tokens"], 11)
        self.assertEqual(error.data["metrics"]["calls_by_node"], {"executor": 1})

if __name__ == "__main__":
    unittest.main()
