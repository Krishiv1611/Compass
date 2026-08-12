import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.tools import tool

from agent import mcp
from agent.graph import workflow
from agent.graph.nodes import linter_node
from agent.skills.manager import SkillManagerAgent
from agent.skills.models import SkillDefinition
from agent.skills.subagent_factory import SubAgentFactory
from agent.tools.directory_tools import find_files
from agent.workspace import WorkspaceContext


class RoutingAndSkillRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_skill_takes_precedence_at_start(self):
        state = {
            "active_skill": {"name": "review"},
            "mode": "edit",
            "messages": [],
        }
        self.assertEqual(workflow._route_start(state), "skill_manager")

    async def test_invalid_skill_returns_error_and_resumes_executor(self):
        class EmptyRegistry:
            @staticmethod
            def get(name):
                return None

        manager = SkillManagerAgent(object(), EmptyRegistry())
        result = await manager(
            {
                "active_skill": {"name": "missing", "arguments": "src"},
                "messages": [],
                "mode": "edit",
            },
            {"configurable": {}},
        )

        self.assertEqual(result["skill_result"]["status"], "error")
        self.assertIn("missing", result["skill_result"]["error"])
        self.assertIsInstance(result["messages"][0], SystemMessage)
        self.assertEqual(
            await workflow._route_after_skill_manager(result),
            "executor",
        )


class FileAndMcpRegressionTests(unittest.TestCase):
    def test_find_files_returns_structured_workspace_matches(self):
        workspace = Path.cwd()
        with tempfile.TemporaryDirectory(dir=workspace) as root:
            root_path = Path(root)
            (root_path / "sample.py").write_text("pass\n", encoding="utf-8")
            config = {
                "configurable": {
                    "workspace_context": WorkspaceContext(
                        root=workspace,
                        execution_target="local",
                    ).to_config()
                }
            }

            result = find_files.invoke(
                {"pattern": "*.py", "path": str(root_path)},
                config=config,
            )

        self.assertEqual(result["matches"], ["sample.py"])
        self.assertEqual(result["total"], 1)

    def test_runtime_mcp_config_name_is_stable(self):
        self.assertEqual(mcp.runtime_mcp_config_name(), "mcp_servers.json")


class SubagentRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_last_turn_tool_call_becomes_bounded_error(self):
        @tool
        def echo(value: str) -> str:
            """Return a supplied value."""

            return value

        class ToolCallingModel:
            def bind_tools(self, tools):
                return self

            async def ainvoke(self, messages):
                return AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "call-last",
                            "name": "echo",
                            "args": {"value": "again"},
                            "type": "tool_call",
                        }
                    ],
                )

        skill = SkillDefinition(
            name="bounded",
            description="Bounded skill",
            system_prompt="Use tools.",
            allowed_tools=["echo"],
            model=None,
            max_turns=1,
            source_path="SKILL.md",
        )
        graph = SubAgentFactory([echo]).build(skill, "")
        initial = {
            "messages": [],
            "turn_count": 0,
            "is_done": False,
            "mode": "edit",
            "approval_status": None,
            "approved_operations": [],
            "pending_tool_calls": [],
        }

        with patch(
            "agent.skills.subagent_factory.llm",
            return_value=ToolCallingModel(),
        ):
            result = await graph.ainvoke(
                initial,
                config={"configurable": {}},
            )

        last = result["messages"][-1]
        self.assertEqual(getattr(last, "tool_calls", []), [])
        self.assertIn("maximum", str(last.content).lower())
        self.assertTrue(result["is_done"])


class GoalValidationRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_typescript_validation_requests_approved_shell_tool(self):
        with tempfile.TemporaryDirectory() as root:
            workspace = Path(root)
            (workspace / "tsconfig.json").write_text("{}", encoding="utf-8")
            config = {
                "configurable": {
                    "workspace_context": WorkspaceContext(
                        root=workspace,
                        execution_target="local",
                    ).to_config()
                }
            }
            with patch(
                "subprocess.run",
                return_value=SimpleNamespace(
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
            ):
                result = await linter_node(
                    {
                        "messages": [],
                        "syntax_checked": False,
                        "pending_tool_calls": [],
                    },
                    config,
                )

        call = result["pending_tool_calls"][0]
        self.assertEqual(call["name"], "shell_execute")
        self.assertEqual(call["args"]["command"], "npx tsc --noEmit")
        self.assertEqual(
            await workflow._route_after_linter(result),
            "check_safety",
        )


if __name__ == "__main__":
    unittest.main()
