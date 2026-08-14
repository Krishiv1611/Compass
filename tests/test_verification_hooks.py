import tempfile
import unittest
from pathlib import Path
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


from agent.hooks import (
    HookConfiguration,
    build_hook_run_requests,
    load_verification_hooks,
    select_verification_hooks,
    changed_files_from_messages,
    hook_result_status,
    redact_hook_output,
)
from agent.graph.nodes import verification_hooks_node


FIXTURE = """
[[hooks.after_edit]]
name = "python tests"
command = "python -m unittest discover -s tests -v"
cwd = "."
timeout_seconds = 120
run_on = ["py"]

[[hooks.after_edit]]
name = "frontend lint"
command = "npm run lint"
cwd = "frontend"
timeout_seconds = 180
run_on = ["ts", "tsx"]
"""


class VerificationHookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / ".compass").mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def write_config(self, content: str = FIXTURE):
        (self.root / ".compass" / "config.toml").write_text(content, encoding="utf-8")

    def test_only_matching_hooks_are_selected_once(self):
        self.write_config()
        config = load_verification_hooks(self.root)

        selected = select_verification_hooks(
            config.hooks, ["agent/main.py", "frontend/src/App.tsx", "more.py"]
        )

        self.assertEqual([hook.name for hook in selected], ["python tests", "frontend lint"])

    def test_timeout_is_clamped_to_600_seconds(self):
        self.write_config(FIXTURE.replace("timeout_seconds = 120", "timeout_seconds = 5000"))
        config = load_verification_hooks(self.root)
        self.assertEqual(config.hooks[0].timeout_seconds, 600)

    def test_traversal_cwd_is_rejected_without_losing_valid_hooks(self):
        self.write_config(FIXTURE + """
[[hooks.after_edit]]
name = "escape"
command = "echo no"
cwd = "../outside"
timeout_seconds = 30
run_on = ["py"]
""")

        config = load_verification_hooks(self.root)

        self.assertEqual(len(config.hooks), 2)
        self.assertTrue(any("outside workspace" in error for error in config.errors))

    def test_selection_builds_approval_requests_not_subprocesses(self):
        self.write_config()
        selected = select_verification_hooks(
            load_verification_hooks(self.root).hooks, ["src/app.py"]
        )

        requests = build_hook_run_requests(selected)

        self.assertEqual(len(requests), 1)
        self.assertTrue(requests[0].requires_approval)
        self.assertEqual(requests[0].tool_name, "shell_execute")
        self.assertEqual(requests[0].arguments["timeout"], 120)
        self.assertEqual(requests[0].arguments["cwd"], ".")

    def test_missing_or_malformed_config_is_inspectable(self):
        self.assertEqual(load_verification_hooks(self.root), HookConfiguration())
        self.write_config("[[hooks.after_edit]\n")
        config = load_verification_hooks(self.root)
        self.assertEqual(config.hooks, [])
        self.assertEqual(len(config.errors), 1)

    def test_changed_files_only_include_successful_main_writes(self):
        messages = [
            HumanMessage(content="edit"),
            AIMessage(content="", tool_calls=[
                {"id": "ok", "name": "edit_file", "args": {"path": "src/app.py"}},
                {"id": "bad", "name": "write_to_file", "args": {"path": "bad.py"}},
            ]),
            ToolMessage(
                content="Successfully edited src/app.py",
                tool_call_id="ok",
                name="edit_file",
            ),
            ToolMessage(
                content="Error: denied",
                tool_call_id="bad",
                name="write_to_file",
                status="error",
            ),
            AIMessage(content="", tool_calls=[
                {"id": "proposal", "name": "edit_file", "args": {"path": "pending.py"}},
            ]),
            ToolMessage(
                content="Proposed edit to pending.py",
                tool_call_id="proposal",
                name="edit_file",
            ),
        ]
        self.assertEqual(changed_files_from_messages(messages), ["src/app.py"])

    def test_hook_result_is_redacted_and_denial_is_skipped(self):
        self.assertEqual(hook_result_status("Command: test\nExit code: 0"), "passed")
        self.assertEqual(hook_result_status("Command: test\nExit code: 1"), "failed")
        self.assertEqual(hook_result_status("Error: User denied permission", "error"), "skipped")
        self.assertNotIn(
            "secret-value",
            redact_hook_output("API_KEY=secret-value\nBearer token-value"),
        )


class VerificationHookNodeTests(unittest.IsolatedAsyncioTestCase):
    async def test_node_creates_shell_calls_but_never_executes_them(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / ".compass").mkdir()
            (root / ".compass" / "config.toml").write_text(FIXTURE, encoding="utf-8")
            messages = [
                HumanMessage(content="edit"),
                AIMessage(content="", tool_calls=[
                    {"id": "edit", "name": "edit_file", "args": {"path": "app.py"}},
                ]),
                ToolMessage(
                    content="Successfully edited app.py",
                    tool_call_id="edit",
                    name="edit_file",
                ),
                AIMessage(content="done"),
            ]
            result = await verification_hooks_node(
                {"messages": messages},
                {"configurable": {"workspace_context": {
                    "root": str(root), "execution_target": "local"
                }}},
            )

        self.assertTrue(result["verification_hooks_scheduled"])
        self.assertEqual(result["pending_tool_calls"][0]["name"], "shell_execute")
        self.assertTrue(result["pending_tool_calls"][0]["args"]["verification_hook"])


if __name__ == "__main__":
    unittest.main()
