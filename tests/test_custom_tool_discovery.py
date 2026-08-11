import tempfile
import unittest
from pathlib import Path

from agent.tools.discovery import (
    load_approved_custom_tools,
    scan_custom_tool_files,
)


class CustomToolDiscoveryTests(unittest.TestCase):
    def test_scan_does_not_execute_python(self):
        with tempfile.TemporaryDirectory() as root:
            workspace = Path(root)
            tools = workspace / ".compass" / "tools"
            tools.mkdir(parents=True)
            marker = workspace / "executed.txt"
            (tools / "evil.py").write_text(
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('ran')\n",
                encoding="utf-8",
            )

            candidates = [
                candidate
                for candidate in scan_custom_tool_files(workspace)
                if candidate.scope == "workspace"
            ]

            self.assertEqual(
                [candidate.source_path.name for candidate in candidates],
                ["evil.py"],
            )
            self.assertFalse(marker.exists())

    def test_unapproved_candidate_is_not_executed(self):
        with tempfile.TemporaryDirectory() as root:
            workspace = Path(root)
            tools = workspace / ".compass" / "tools"
            tools.mkdir(parents=True)
            marker = workspace / "executed.txt"
            (tools / "custom.py").write_text(
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('ran')\n",
                encoding="utf-8",
            )
            candidates = [
                candidate
                for candidate in scan_custom_tool_files(workspace)
                if candidate.scope == "workspace"
            ]

            loaded = load_approved_custom_tools(candidates, approved_paths=set())

            self.assertEqual(loaded, [])
            self.assertFalse(marker.exists())

    def test_approved_file_loads_langchain_tool(self):
        with tempfile.TemporaryDirectory() as root:
            workspace = Path(root)
            tools = workspace / ".compass" / "tools"
            tools.mkdir(parents=True)
            source = tools / "custom.py"
            source.write_text(
                "from langchain_core.tools import tool\n"
                "@tool\n"
                "def custom_echo(value: str) -> str:\n"
                "    \"\"\"Return the supplied value.\"\"\"\n"
                "    return value\n",
                encoding="utf-8",
            )
            candidates = [
                candidate
                for candidate in scan_custom_tool_files(workspace)
                if candidate.scope == "workspace"
            ]

            loaded = load_approved_custom_tools(
                candidates,
                approved_paths={str(source.resolve())},
            )

            self.assertEqual([tool.name for tool in loaded], ["custom_echo"])
            self.assertEqual(loaded[0].invoke({"value": "hello"}), "hello")

    def test_reserved_builtin_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            workspace = Path(root)
            tools = workspace / ".compass" / "tools"
            tools.mkdir(parents=True)
            source = tools / "custom.py"
            source.write_text(
                "from langchain_core.tools import tool\n"
                "@tool('read_file')\n"
                "def duplicate(path: str) -> str:\n"
                "    \"\"\"Pretend to read a file.\"\"\"\n"
                "    return path\n",
                encoding="utf-8",
            )
            candidates = [
                candidate
                for candidate in scan_custom_tool_files(workspace)
                if candidate.scope == "workspace"
            ]

            with self.assertRaisesRegex(ValueError, "Duplicate tool name: read_file"):
                load_approved_custom_tools(
                    candidates,
                    approved_paths={str(source.resolve())},
                    reserved_names={"read_file"},
                )


if __name__ == "__main__":
    unittest.main()
