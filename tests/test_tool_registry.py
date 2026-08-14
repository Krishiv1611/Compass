import unittest
from unittest.mock import patch
from langchain_core.messages import AIMessage

from agent.graph.tool_node import CompassToolNode
from agent.tools.registry import build_builtin_registry


class ToolRegistryTests(unittest.TestCase):
    def test_web_excludes_shell_and_skill_creation(self):
        registry = build_builtin_registry()
        names = {tool.name for tool in registry.tools_for("web")}
        self.assertNotIn("shell_execute", names)
        self.assertNotIn("create_skill", names)

    def test_workers_receive_read_only_tools(self):
        registry = build_builtin_registry()
        specs = registry.specs_for("worker")
        self.assertTrue(specs)
        self.assertTrue(
            all(not spec.policy.mutates_workspace for spec in specs)
        )

    def test_duplicate_tool_names_are_rejected(self):
        registry = build_builtin_registry()
        with self.assertRaisesRegex(ValueError, "Duplicate tool name"):
            registry.register(registry.get("read_file"))


class HookToolPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def test_web_adds_shell_only_for_internal_hook_calls(self):
        captured = []

        class FakeToolNode:
            def __init__(self, tools):
                captured.append({tool.name for tool in tools})

            async def ainvoke(self, state, config):
                return {"messages": []}

        registry = build_builtin_registry()
        node = CompassToolNode(registry)
        hook = AIMessage(content="", tool_calls=[{
            "id": "hook-1", "name": "shell_execute",
            "args": {"command": "test", "verification_hook": True},
        }])
        ordinary = AIMessage(content="", tool_calls=[{
            "id": "read-1", "name": "read_file", "args": {"path": "a.py"},
        }])
        with patch("agent.graph.tool_node.ToolNode", FakeToolNode):
            await node({"messages": [hook]}, {"configurable": {"execution_target": "web"}})
            await node({"messages": [ordinary]}, {"configurable": {"execution_target": "web"}})

        self.assertIn("shell_execute", captured[0])
        self.assertNotIn("shell_execute", captured[1])


if __name__ == "__main__":
    unittest.main()
