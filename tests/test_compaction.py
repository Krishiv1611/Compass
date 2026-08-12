import unittest
from typing import Annotated, TypedDict
from unittest.mock import patch

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import RemoveMessage, add_messages

from agent.graph.nodes import summary_node
from agent.runtime.compaction import build_compaction_update, compact_thread
from agent.graph.routing import route_after_executor


class CompactionTests(unittest.TestCase):
    def test_old_messages_are_removed_and_recent_messages_remain(self):
        messages = [
            HumanMessage(content=str(index), id=str(index))
            for index in range(12)
        ]
        update = build_compaction_update(
            messages,
            "summary",
            keep_recent=6,
        )
        removals = [
            item
            for item in update["messages"]
            if isinstance(item, RemoveMessage)
        ]
        self.assertEqual(
            [item.id for item in removals],
            [str(index) for index in range(6)],
        )
        self.assertEqual(update["summary"], "summary")


class AutomaticCompactionRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import asyncio

        asyncio.get_running_loop().slow_callback_duration = 1.0

    async def test_long_completed_turn_routes_to_compaction(self):
        state = {
            "messages": [
                HumanMessage(content=str(index), id=str(index))
                for index in range(11)
            ],
            "pending_tool_calls": [],
            "mode": "edit",
            "is_done": True,
        }

        self.assertEqual(
            await route_after_executor(state),
            "summary_node",
        )

    async def test_pending_tool_calls_still_take_priority(self):
        state = {
            "messages": [
                HumanMessage(content=str(index), id=str(index))
                for index in range(11)
            ],
            "pending_tool_calls": [{"id": "call-1", "name": "read_file"}],
            "mode": "edit",
            "is_done": False,
        }

        self.assertEqual(
            await route_after_executor(state),
            "check_safety",
        )


class _CompactionState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    summary: str
    is_done: bool


class ManualCompactionTests(unittest.IsolatedAsyncioTestCase):
    async def test_compaction_updates_checkpoint_with_one_summary_call(self):
        class FakeSummarizer:
            def __init__(self):
                self.calls = 0

            async def ainvoke(self, messages):
                self.calls += 1
                return AIMessage(content="Stored summary")

        fake = FakeSummarizer()
        builder = StateGraph(_CompactionState)
        builder.add_node("summary_node", summary_node)
        builder.add_edge(START, "summary_node")
        builder.add_edge("summary_node", END)
        graph = builder.compile(checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": "compact-thread"}}
        original = [
            HumanMessage(content=str(index), id=str(index))
            for index in range(12)
        ]
        await graph.aupdate_state(
            config,
            {
                "messages": original,
                "summary": "",
                "is_done": True,
            },
            as_node="summary_node",
        )

        with patch("agent.graph.nodes.llm", return_value=fake):
            result = await compact_thread(graph, config, force=True)

        snapshot = await graph.aget_state(config)
        self.assertEqual(fake.calls, 1)
        self.assertEqual(result.before_count, 12)
        self.assertEqual(result.after_count, 6)
        self.assertEqual(snapshot.values["summary"], "Stored summary")
        self.assertEqual(
            [message.id for message in snapshot.values["messages"]],
            [str(index) for index in range(6, 12)],
        )

        await graph.aupdate_state(
            config,
            {"messages": [HumanMessage(content="next", id="next")]},
            as_node="summary_node",
        )
        next_snapshot = await graph.aget_state(config)
        self.assertEqual(next_snapshot.values["summary"], "Stored summary")
        self.assertEqual(
            [message.id for message in next_snapshot.values["messages"]],
            [str(index) for index in range(6, 12)] + ["next"],
        )


if __name__ == "__main__":
    unittest.main()
