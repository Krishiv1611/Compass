"""Unit tests for the E2B Cloud Sandbox Adapter."""

import os
import tempfile
import unittest
from agent.sandbox.e2b_adapter import E2BCloudSandbox, CommandResult


class E2BSandboxTests(unittest.IsolatedAsyncioTestCase):
    async def test_fallback_mode_when_no_api_key_runs_real_local_execution(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            sandbox = E2BCloudSandbox(api_key=None)
            self.assertFalse(sandbox.is_configured)
            started = await sandbox.start()
            self.assertTrue(started)

            # 1. Real command execution
            res = await sandbox.run_command("echo compass-local-runner", cwd=tmp_dir)
            self.assertTrue(res.success)
            self.assertEqual(res.exit_code, 0)
            self.assertIn("compass-local-runner", res.stdout)
            self.assertNotIn("[compass-sandbox-fallback]", res.stdout)

            # 2. Real file writing
            test_file = os.path.join(tmp_dir, "test.txt")
            wrote = await sandbox.write_file(test_file, "actual real content")
            self.assertTrue(wrote)

            # 3. Real file reading
            read = await sandbox.read_file(test_file)
            self.assertEqual(read, "actual real content")

            await sandbox.close()

    async def test_context_manager_lifecycle(self):
        async with E2BCloudSandbox() as sandbox:
            res = await sandbox.run_command("echo lifecycle test")
            self.assertTrue(res.success)
            self.assertIn("lifecycle test", res.stdout)


if __name__ == "__main__":
    unittest.main()
