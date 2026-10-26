import asyncio
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool

from agent.graph.tool_node import CompassToolNode
from agent.rag.retriever import codebase_search
from agent.tools.registry import build_builtin_registry


@tool
def sample_healthy_tool(arg: str) -> str:
    """A healthy tool."""
    return f"healthy: {arg}"


class OptionalDependencyDegradationTests(unittest.IsolatedAsyncioTestCase):
    def test_codebase_search_degrades_gracefully_when_embeddings_offline(self):
        with patch("agent.rag.retriever.get_vector_store", return_value=None):
            result = codebase_search.invoke({"query": "authentication flow"}, config={})
            self.assertIn("grep_search", result)
            self.assertIn("find_files", result)
            self.assertIn("unavailable", result.lower())

    async def test_mcp_discovery_isolates_offline_server_and_loads_healthy_server(self):
        from agent import mcp

        async def fake_get_tools(*, server_name=None):
            if server_name == "offline_server":
                raise ConnectionRefusedError("Connection refused by target machine")
            if server_name == "healthy_server":
                return [sample_healthy_tool]
            return [sample_healthy_tool]

        client_mock = MagicMock()
        client_mock.get_tools = AsyncMock(side_effect=fake_get_tools)

        with (
            patch.object(
                mcp,
                "connections",
                {"healthy_server": {"transport": "sse"}, "offline_server": {"transport": "sse"}},
            ),
            patch.object(mcp, "mcp_client", client_mock),
        ):
            mcp.reset_mcp_cache()
            tools = await mcp.get_mcp_tools()
            names = [getattr(t, "name", str(t)) for t in tools]
            self.assertIn("sample_healthy_tool", names)
            mcp.reset_mcp_cache()

    async def test_mcp_discovery_bounds_hanging_server_by_timeout(self):
        from agent import mcp

        async def hanging_get_tools(*, server_name=None):
            await asyncio.sleep(10.0)
            return []

        client_mock = MagicMock()
        client_mock.get_tools = AsyncMock(side_effect=hanging_get_tools)

        with (
            patch.object(
                mcp,
                "connections",
                {"hanging_server": {"transport": "sse"}},
            ),
            patch.object(mcp, "mcp_client", client_mock),
        ):
            mcp.reset_mcp_cache()
            t0 = time.monotonic()
            tools = await mcp.get_mcp_tools()
            elapsed = time.monotonic() - t0
            self.assertEqual(tools, [])
            self.assertLess(elapsed, 3.5)
            mcp.reset_mcp_cache()

    async def test_compass_tool_node_handles_offline_or_missing_mcp_tool_gracefully(self):
        registry = build_builtin_registry()
        node = CompassToolNode(registry)
        tool_call_msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "call-offline-1",
                    "name": "offline_mcp_tool",
                    "args": {"query": "something"},
                }
            ],
        )

        state = {"messages": [tool_call_msg]}
        config = {"configurable": {"execution_target": "tui"}}

        result = await node(state, config)
        messages = result.get("messages", [])
        self.assertEqual(len(messages), 1)
        tool_msg = messages[0]
        self.assertIsInstance(tool_msg, ToolMessage)
        self.assertEqual(tool_msg.tool_call_id, "call-offline-1")
        self.assertIn("unavailable", tool_msg.content.lower())
        self.assertIn("offline_mcp_tool", tool_msg.content)

    def test_memory_search_degrades_to_text_when_embeddings_unconfigured(self):
        from agent.tools.memory_tool import memory

        class FakeItem:
            key = "mem-1"
            value = {"content": "Use tabs for indentation in this project", "enabled": True}

        class FakeStore:
            def search(self, namespace, query=None, limit=5):
                if query:
                    raise RuntimeError("Semantic search requires embedding key")
                return [FakeItem()]

        with patch("agent.tools.memory_tool.get_memory_store", return_value=FakeStore()):
            result = memory.invoke(
                {"action": "search", "content": "tabs"},
                config={"configurable": {"execution_target": "web"}},
            )
            self.assertIn("tabs for indentation", result)
            self.assertIn("mem-1", result)

    def test_index_workspace_records_error_when_vector_store_fails(self):
        from agent.rag.indexer import index_workspace
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("agent.rag.indexer.get_vector_store", side_effect=RuntimeError("PGVector offline")):
                stats = index_workspace(tmp_dir, project_id="proj-1", context_version="v1")
                self.assertTrue(any("PGVector offline" in err or "Vector store unavailable" in err for err in stats.errors))


if __name__ == "__main__":
    unittest.main()
