import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from agent.graph.nodes import call_model, planner_node
from agent.graph.workflow import builder
from agent.runtime.turn_context import TurnContext
from agent.tools.file_tools import edit_file, read_file, write_to_file
from agent.workspace import WorkspaceContext, discover_local_workspace


class HarnessFixesTests(unittest.IsolatedAsyncioTestCase):
    def test_nine_node_lean_stategraph(self):
        """Graph contains exactly the 9 lean nodes specified in the redesign."""
        expected_nodes = {
            "direct_chat",
            "planner",
            "plan_approval",
            "skill_manager",
            "coordinator",
            "executor",
            "check_safety",
            "tools",
            "summary_node",
        }
        self.assertEqual(set(builder.nodes.keys()), expected_nodes)
        self.assertEqual(len(builder.nodes), 9)

    async def test_single_agent_planner_skips_execution_plan_when_orchestration_disabled(self):
        """Planner node makes 1 LLM call when orchestration is disabled."""
        context = TurnContext(
            user_query="Single agent query",
            model_clients={"planner": SimpleNamespace(ainvoke=AsyncMock(return_value=AIMessage(content="Plan 1.")))},
        )
        config = {"configurable": {"_turn_context": context}}

        with patch("agent.graph.nodes.settings.get", side_effect=lambda key, default=None: False if key == "orchestration.enabled" else default):
            with patch("agent.graph.nodes.create_execution_plan", new=AsyncMock()) as mock_create_plan:
                update = await planner_node({"messages": [HumanMessage(content="Hello")]}, config)
                mock_create_plan.assert_not_called()
                self.assertFalse(update["orchestration_enabled"])
                self.assertIsNone(update["execution_plan"])

    def test_file_tools_return_relative_paths_and_ast_warnings(self):
        """File tools return workspace-relative paths and inline AST warnings for syntax errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            config = {
                "configurable": {
                    "workspace_context": WorkspaceContext(
                        root=root,
                        execution_target="local",
                    ).to_config()
                }
            }

            # 1. Invalid Python code writes with syntax warning
            bad_code = "def broken(\n"
            result = write_to_file.invoke({"path": "bad.py", "content": bad_code}, config=config)
            self.assertIn("Successfully wrote", result)
            self.assertIn("bad.py", result)
            self.assertNotIn(str(root), result)
            self.assertIn("Warning: Python SyntaxError", result)

            # 2. Valid Python code writes cleanly without warning
            good_code = "def valid():\n    return 42\n"
            result = write_to_file.invoke({"path": "good.py", "content": good_code}, config=config)
            self.assertIn("Successfully wrote", result)
            self.assertIn("good.py", result)
            self.assertNotIn(str(root), result)
            self.assertNotIn("Warning: Python SyntaxError", result)

            # 3. Read file returns relative header
            read_res = read_file.invoke({"path": "good.py"}, config=config)
            self.assertIn("good.py", read_res)
            self.assertNotIn(str(root), read_res)

            # 4. Edit file introduces syntax error -> warning
            edit_res = edit_file.invoke(
                {
                    "path": "good.py",
                    "old_content": "    return 42\n",
                    "new_content": "    return (\n",
                },
                config=config,
            )
            self.assertIn("Successfully edited good.py", edit_res)
            self.assertNotIn(str(root), edit_res)
            self.assertIn("Warning: Python SyntaxError", edit_res)

    def test_discover_local_workspace_with_disabled_parent_git(self):
        """discover_local_workspace with allow_parent_git=False avoids parent git repo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            ws = discover_local_workspace(target, allow_parent_git=False)
            self.assertEqual(ws.root, target.resolve())
            self.assertIsNone(ws.git_branch)


    async def test_call_model_loop_detection_strips_tool_calls_and_resets_is_done(self):
        """When a tool loop is detected, tool calls are stripped and is_done is False."""
        mock_response = AIMessage(
            content="Trying again",
            tool_calls=[{"name": "read_file", "args": {"path": "loop.txt"}, "id": "tc-1"}],
        )
        context = TurnContext(
            user_query="Run loop",
            model_clients={"executor": SimpleNamespace(
                bind_tools=lambda _tools: SimpleNamespace(ainvoke=AsyncMock(return_value=mock_response))
            )},
        )
        config = {"configurable": {"_turn_context": context}}
        state = {
            "messages": [HumanMessage(content="run")],
            "loop_count": 2,
        }

        with patch("agent.graph.nodes.is_looping", return_value=True):
            result = await call_model(state, config)
            self.assertTrue(result["loop_detected"])
            self.assertEqual(result["pending_tool_calls"], [])
            self.assertFalse(result["is_done"])
            self.assertEqual(mock_response.tool_calls, [])

    def test_apply_workspace_metadata_delta_syncs_session_context_version(self):
        """Workspace delta updates context_version on both workspace and its active session."""
        from backend.services.workspace_changes import FileChange, apply_workspace_metadata_delta

        class MockSession:
            def __init__(self, ws_id):
                self.active_workspace_id = ws_id
                self.context_version = "v1"

        class MockWorkspace:
            def __init__(self, ws_id):
                self.id = ws_id
                self.file_count = 10
                self.size_bytes = 1000
                self.context_version = "v1"
                self.session = MockSession(ws_id)

        ws = MockWorkspace("ws-123")
        changes = [FileChange(path="test.py", before_size=0, after_size=50, operation="create")]
        apply_workspace_metadata_delta(ws, changes)

        self.assertNotEqual(ws.context_version, "v1")
        self.assertEqual(ws.context_version, ws.session.context_version)
        self.assertEqual(ws.file_count, 11)
        self.assertEqual(ws.size_bytes, 1050)


if __name__ == "__main__":
    unittest.main()
