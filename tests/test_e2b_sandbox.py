"""Unit tests for the E2B Cloud Sandbox Adapter."""

import unittest
from agent.sandbox.e2b_adapter import E2BCloudSandbox, CommandResult


class E2BSandboxTests(unittest.IsolatedAsyncioTestCase):
    async def test_fallback_mode_when_no_api_key(self):
        sandbox = E2BCloudSandbox(api_key=None)
        self.assertFalse(sandbox.is_configured)
        started = await sandbox.start()
        self.assertTrue(started)
        self.assertEqual(sandbox.sandbox_id, "mock-sandbox")

        res = await sandbox.run_command("echo 'hello from compass'")
        self.assertTrue(res.success)
        self.assertEqual(res.exit_code, 0)
        self.assertIn("echo 'hello from compass'", res.stdout)

        wrote = await sandbox.write_file("test.txt", "content")
        self.assertTrue(wrote)

        read = await sandbox.read_file("test.txt")
        self.assertEqual(read, "")

        await sandbox.close()

    async def test_context_manager_lifecycle(self):
        async with E2BCloudSandbox() as sandbox:
            res = await sandbox.run_command("ls -la")
            self.assertTrue(res.success)


if __name__ == "__main__":
    unittest.main()
