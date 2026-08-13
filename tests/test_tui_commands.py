import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agent.ui.commands import build_registry
from agent.ui.commands.models import CommandContext


class FakeWorkflow:
    async def aget_state(self, _config):
        return SimpleNamespace(values={"messages": [SimpleNamespace(content="one"), SimpleNamespace(content="two")]})


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


if __name__ == "__main__":
    unittest.main()
