import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agent.ui.commands import build_registry
from agent.ui.commands.models import CommandContext
from agent.checkpoints import create_checkpoint, list_checkpoints, seal_checkpoint


class FakeWorkflow:
    def __init__(self):
        self.updated = []

    async def aget_state(self, _config):
        return SimpleNamespace(values={"messages": [SimpleNamespace(content="one"), SimpleNamespace(content="two")]})

    async def aupdate_state(self, config, values):
        self.updated.append((config, values))


class TuiCommandTests(unittest.IsolatedAsyncioTestCase):
    def context(self, **overrides):
        values = dict(console=None, workflow=None, run_config={}, session_store=None, workspace=None, settings={})
        values.update(overrides)
        return CommandContext(**values)

    async def test_schedule_never_claims_a_task_was_queued(self):
        result = await build_registry().execute("/schedule tomorrow run tests", self.context())
        self.assertTrue(result.consumed)
        self.assertIn("not available", result.message.lower())
        self.assertNotIn("queued", result.message.lower())

    async def test_history_reads_checkpoint_messages(self):
        result = await build_registry().execute("/history", self.context(workflow=FakeWorkflow()))
        self.assertIn("one", result.message)
        self.assertIn("two", result.message)

    async def test_model_reads_active_provider_and_model(self):
        result = await build_registry().execute("/model", self.context(settings={"llm_provider": "anthropic", "model": "claude-sonnet"}))
        self.assertIn("anthropic", result.message)
        self.assertIn("claude-sonnet", result.message)

    async def test_alias_and_help_are_registered(self):
        registry = build_registry()
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            result = await registry.execute("/web", self.context())
        self.assertTrue(result.consumed)
        self.assertIn("npm run dev", result.message)
        self.assertIn("/history", registry.help_text())

    async def test_ui_opens_only_when_reachable(self):
        response = MagicMock()
        with patch("urllib.request.urlopen", return_value=response), patch("webbrowser.open") as opened:
            result = await build_registry().execute("/ui", self.context())
        self.assertIn("Opened", result.message)
        opened.assert_called_once_with("http://localhost:5173")

    async def test_doctor_reports_real_local_checks(self):
        result = await build_registry().execute("/doctor", self.context(settings={"has_llm_api_key": True}))
        self.assertIn("agent imports: ok", result.message)
        self.assertIn("provider credential: configured", result.message)

    async def test_hooks_inspects_config_without_running_it(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / ".compass").mkdir()
            (root / ".compass" / "config.toml").write_text(
                '[[hooks.after_edit]]\nname="tests"\ncommand="python -m unittest"\nrun_on=["py"]\n',
                encoding="utf-8",
            )
            result = await build_registry().execute(
                "/hooks", self.context(workspace=folder)
            )
        self.assertIn("inspection only", result.message)
        self.assertIn("python -m unittest", result.message)

    async def test_init_is_non_destructive(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "COMPASS.md"
            target.write_text("keep", encoding="utf-8")
            result = await build_registry().execute(
                "/init", self.context(workspace=folder)
            )
            self.assertIn("not changed", result.message)
            self.assertEqual(target.read_text(encoding="utf-8"), "keep")

    async def test_learn_displays_exact_addition_and_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as folder:
            context = self.context(workspace=folder)
            with patch("agent.ui.commands.context.click.confirm", return_value=False) as confirm:
                result = await build_registry().execute(
                    "/learn Prefer small functions", context
                )
            self.assertIn("unchanged", result.message)
            self.assertIn("- Prefer small functions", confirm.call_args.args[0])
            self.assertFalse((Path(folder) / "COMPASS.md").exists())

            with patch("agent.ui.commands.context.click.confirm", return_value=True):
                result = await build_registry().execute(
                    "/learn Prefer small functions", context
                )
            self.assertIn("- Prefer small functions", result.message)
            self.assertIn(
                "- Prefer small functions",
                (Path(folder) / "COMPASS.md").read_text(encoding="utf-8"),
            )
            self.assertEqual(len(list_checkpoints(folder)), 1)

    async def test_undo_restores_latest_file_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "app.py"
            target.write_text("before", encoding="utf-8")
            checkpoint = create_checkpoint(
                root, ["app.py"], workspace_id="local", thread_id="thread"
            )
            target.write_text("after", encoding="utf-8")
            seal_checkpoint(root, checkpoint.id)
            context = self.context(
                workspace=folder,
                run_config={"configurable": {"thread_id": "thread"}},
            )
            with patch("agent.ui.commands.session.click.confirm", return_value=True):
                result = await build_registry().execute("/undo", context)

            self.assertIn("Restored", result.message)
            self.assertEqual(target.read_text(encoding="utf-8"), "before")

    async def test_fork_creates_new_thread_and_reports_shared_workspace(self):
        workflow = FakeWorkflow()
        store = MagicMock()
        store.fork_session.return_value = {
            "thread_id": "fork-thread",
            "title": "Fork of current",
        }
        context = self.context(
            workflow=workflow,
            session_store=store,
            workspace="C:/workspace",
            run_config={"configurable": {"thread_id": "source-thread"}},
        )

        result = await build_registry().execute("/fork", context)

        self.assertIn("shares the current working directory", result.message)
        self.assertEqual(result.state_updates["switch_thread_id"], "fork-thread")
        store.fork_session.assert_called_once_with("source-thread")
        self.assertEqual(workflow.updated[-1][0]["configurable"]["thread_id"], "fork-thread")


if __name__ == "__main__":
    unittest.main()
