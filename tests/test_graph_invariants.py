import unittest
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from agent.graph.tool_node import CompassToolNode
from agent.graph.routing import route_after_executor
from agent.tools.registry import ToolPolicy, ToolRegistry, ToolSpec


class _SequenceState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    pending_tool_calls: list[dict]
    mode: str
    is_done: bool


class GraphInvariantTests(unittest.IsolatedAsyncioTestCase):
    async def test_pending_calls_always_route_to_safety_first(self):
        state = {
            "pending_tool_calls": [
                {"id": "1", "name": "read_file", "args": {"path": "a.py"}}
            ],
            "loop_detected": True,
            "needs_replan": True,
            "mode": "goal",
            "is_done": False,
        }
        self.assertEqual(await route_after_executor(state), "check_safety")

    async def test_goal_iteration_limit_ends_with_explicit_failure(self):
        state = {
            "pending_tool_calls": [],
            "loop_detected": False,
            "needs_replan": False,
            "mode": "goal",
            "is_done": False,
            "goal_iteration": 3,
            "goal_iteration_limit": 3,
        }
        self.assertEqual(await route_after_executor(state), "goal_limit")

    async def test_tool_calls_are_followed_by_all_results_before_final_ai(self):
        @tool
        def first_tool(value: str) -> str:
            """Return the first value."""

            return f"first:{value}"

        @tool
        def second_tool(value: str) -> str:
            """Return the second value."""

            return f"second:{value}"

        calls = 0

        async def fake_executor(state: _SequenceState) -> dict:
            nonlocal calls
            calls += 1
            if calls == 1:
                tool_calls = [
                    {
                        "id": "call-1",
                        "name": "first_tool",
                        "args": {"value": "one"},
                        "type": "tool_call",
                    },
                    {
                        "id": "call-2",
                        "name": "second_tool",
                        "args": {"value": "two"},
                        "type": "tool_call",
                    },
                ]
                return {
                    "messages": [AIMessage(content="", tool_calls=tool_calls)],
                    "pending_tool_calls": tool_calls,
                    "is_done": False,
                }
            return {
                "messages": [AIMessage(content="Finished")],
                "pending_tool_calls": [],
                "is_done": True,
            }

        async def fake_safety(state: _SequenceState) -> dict:
            return {}

        safe_policy = ToolPolicy(
            risk="safe",
            mutates_workspace=False,
            web_allowed=True,
            worker_allowed=True,
        )
        registry = ToolRegistry(
            [
                ToolSpec(first_tool, safe_policy),
                ToolSpec(second_tool, safe_policy),
            ]
        )
        builder = StateGraph(_SequenceState)
        builder.add_node("executor", fake_executor)
        builder.add_node("check_safety", fake_safety)
        builder.add_node("tools", CompassToolNode(registry))
        builder.add_edge(START, "executor")
        builder.add_conditional_edges(
            "executor",
            route_after_executor,
            {"check_safety": "check_safety", "end": END},
        )
        builder.add_edge("check_safety", "tools")
        builder.add_edge("tools", "executor")

        result = await builder.compile().ainvoke(
            {
                "messages": [HumanMessage(content="Use both tools")],
                "pending_tool_calls": [],
                "mode": "edit",
                "is_done": False,
            },
            config={"configurable": {"execution_target": "tui"}},
        )

        self.assertEqual(
            [message.type for message in result["messages"]],
            ["human", "ai", "tool", "tool", "ai"],
        )


if __name__ == "__main__":
    unittest.main()
