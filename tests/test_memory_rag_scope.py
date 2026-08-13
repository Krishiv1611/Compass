import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.rag.indexer import index_workspace, should_index_path
from agent.rag.loaders import extract_text
from agent.tools.memory_tool import memory_namespace


class MemoryRagScopeTests(unittest.TestCase):
    def test_categorized_save_can_be_found_in_same_category(self):
        namespace = memory_namespace(
            "u1",
            "project",
            "p1",
            "preference",
        )
        self.assertEqual(
            namespace,
            ("memories", "u1", "project", "p1", "preference"),
        )

    def test_secret_like_files_are_not_indexed(self):
        for path in (
            ".env",
            "secrets.env",
            "config/credentials.json",
            ".git/config",
            "id_rsa",
            ".compass/checkpoints/state.json",
            "node_modules/pkg/index.js",
            "dist/bundle.js",
        ):
            with self.subTest(path=path):
                self.assertFalse(should_index_path(Path(path)))

    def test_normal_source_is_indexed(self):
        self.assertTrue(should_index_path(Path("src/app.py")))

    def test_index_requires_stable_project_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "project_id"):
                index_workspace(
                    directory,
                    project_id="",
                    context_version="content:test",
                )

    def test_notebook_support_is_reachable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "notes.ipynb"
            path.write_text(
                '{"cells":[{"source":["print(1)\\n"]}]}',
                encoding="utf-8",
            )
            self.assertEqual(extract_text(path).strip(), "print(1)")


if __name__ == "__main__":
    unittest.main()
