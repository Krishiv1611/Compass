import unittest
import tempfile
from collections import Counter
from pathlib import Path
from unittest.mock import AsyncMock, patch

from agent.runtime.turn_context import prepare_turn_context
from tests.performance.fakes import fake_config, fake_input, services_for_counter


class TurnContextTests(unittest.IsolatedAsyncioTestCase):
    async def test_executor_rounds_share_prepared_context(self):
        calls = Counter()
        context = await prepare_turn_context(
            fake_input("fix auth"),
            fake_config(),
            services=services_for_counter(calls),
        )

        self.assertEqual(context.recalled_memory, ["fixed remembered preference"])
        self.assertEqual(context.mcp_tools, ["fixed_mcp_tool"])
        self.assertIsNotNone(context.executor_model)
        self.assertEqual(calls["memory_calls"], 1)
        self.assertEqual(calls["mcp_calls"], 1)
        self.assertEqual(calls["bind_tools"], 1)

    async def test_greeting_skips_coding_context_preparation(self):
        calls = Counter()
        context = await prepare_turn_context(
            fake_input("hello"),
            fake_config(),
            services=services_for_counter(calls),
        )

        self.assertTrue(context.direct_chat)
        self.assertEqual(calls["memory_calls"], 0)
        self.assertEqual(calls["mcp_calls"], 0)
        self.assertEqual(calls["bind_tools"], 0)

    async def test_failed_mcp_discovery_uses_negative_cache(self):
        from agent import mcp

        failing = AsyncMock(side_effect=RuntimeError("offline"))
        with (
            patch.object(mcp, "connections", {"demo": {"transport": "stdio"}}),
            patch.object(mcp.mcp_client, "get_tools", failing),
        ):
            mcp.reset_mcp_cache()
            self.assertEqual(await mcp.get_mcp_tools(), [])
            self.assertEqual(await mcp.get_mcp_tools(), [])

        self.assertEqual(failing.await_count, 1)
        mcp.reset_mcp_cache()

    async def test_project_instructions_are_prepared_once_per_turn(self):
        calls = Counter()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "COMPASS.md").write_text("Prefer readable code", encoding="utf-8")
            config = fake_config()
            config["configurable"]["workspace_context"] = {
                "root": str(root),
                "execution_target": "local",
            }

            first = await prepare_turn_context(
                fake_input("fix auth"), config, services=services_for_counter(calls)
            )
            (root / "COMPASS.md").write_text("changed later", encoding="utf-8")
            second = await prepare_turn_context(
                fake_input("fix auth"), config, services=services_for_counter(calls)
            )

        self.assertIs(first, second)
        self.assertIn("Prefer readable code", second.project_instructions)
        self.assertNotIn("changed later", second.project_instructions)


if __name__ == "__main__":
    unittest.main()
