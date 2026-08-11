import unittest

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


if __name__ == "__main__":
    unittest.main()
