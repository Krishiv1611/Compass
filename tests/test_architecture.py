"""Fast architecture invariants that do not require external services."""

import unittest

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.store.base import BaseStore

from agent.graph.workflow import (
    _executor_scope_expanded,
    _needs_planning,
    _route_start,
)
from agent.tools import memory_tool


class WorkflowRoutingTests(unittest.TestCase):
    def test_greeting_uses_direct_chat_even_with_stale_plan_state(self):
        state = {
            "messages": [HumanMessage(content="hello")],
            "mode": "edit",
            "plan": "old plan",
            "pending_tool_calls": [{"name": "old"}],
        }
        self.assertEqual(_route_start(state), "direct_chat")

    def test_edit_request_uses_executor(self):
        state = {
            "messages": [HumanMessage(content="Rename the submit button label")],
            "mode": "edit",
        }
        self.assertEqual(_route_start(state), "executor")

    def test_complex_edit_uses_planner(self):
        state = {
            "messages": [
                HumanMessage(
                    content="Redesign the authentication system across the codebase"
                )
            ],
            "mode": "edit",
        }
        self.assertTrue(_needs_planning(state["messages"][0].content))
        self.assertEqual(_route_start(state), "context_injector")

    def test_ask_mode_does_not_force_planning(self):
        state = {
            "messages": [HumanMessage(content="Explain the current architecture")],
            "mode": "ask",
        }
        self.assertEqual(_route_start(state), "executor")
    def test_unplanned_cross_file_edit_escalates_before_mutation(self):
        calls = [
            {
                "id": f"call-{index}",
                "name": "edit_file",
                "args": {"path": f"src/file_{index}.py"},
                "type": "tool_call",
            }
            for index in range(3)
        ]
        state = {
            "messages": [AIMessage(content="", tool_calls=calls)],
            "mode": "edit",
            "plan": "",
        }
        self.assertTrue(_executor_scope_expanded(state))
    def test_plan_and_goal_read_context_first(self):
        for mode in ("plan", "goal"):
            with self.subTest(mode=mode):
                state = {"messages": [HumanMessage(content="Change the API")], "mode": mode}
                self.assertEqual(_route_start(state), "context_injector")


class LongTermMemoryTests(unittest.TestCase):
    def test_store_proxy_is_lazy_langgraph_store(self):
        self.assertIsInstance(memory_tool.MEMORY_STORE, BaseStore)

    def test_memory_namespaces_are_isolated(self):
        self.assertEqual(
            memory_tool.memory_namespace("user-a"),
            ("memories", "user-a", "global"),
        )
        self.assertEqual(
            memory_tool.memory_namespace("user-a", scope="project", project_id="project-a"),
            ("memories", "user-a", "project", "project-a"),
        )
        self.assertNotEqual(
            memory_tool.memory_namespace("user-a"),
            memory_tool.memory_namespace("user-b"),
        )


if __name__ == "__main__":
    unittest.main()
