import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from langchain_core.messages import AIMessage


from agent.checkpoints import (
    CheckpointConflictError,
    create_checkpoint,
    list_checkpoints,
    preview_restore,
    restore_checkpoint,
    seal_checkpoint,
)
from agent.graph.tool_node import CompassToolNode
from agent.tools.change_tracker import ChangeTracker
from agent.tools.registry import build_builtin_registry
from agent.tools.utils import resolve_workspace_path
from agent.workspace import WorkspaceContext


class FileCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_restore_removes_file_created_after_checkpoint(self):
        checkpoint = create_checkpoint(
            self.root, ["new.py"], workspace_id="w", thread_id="t"
        )
        (self.root / "new.py").write_text("created", encoding="utf-8")
        restore_checkpoint(self.root, checkpoint.id)
        self.assertFalse((self.root / "new.py").exists())

    def test_restore_recreates_deleted_file(self):
        target = self.root / "old.py"
        target.write_text("before", encoding="utf-8")
        checkpoint = create_checkpoint(
            self.root, ["old.py"], workspace_id="w", thread_id="t"
        )
        target.unlink()
        restore_checkpoint(self.root, checkpoint.id)
        self.assertEqual(target.read_text(encoding="utf-8"), "before")

    def test_restore_replaces_edited_binary_content(self):
        target = self.root / "asset.bin"
        target.write_bytes(b"\x00before\xff")
        checkpoint = create_checkpoint(
            self.root, ["asset.bin"], workspace_id="w", thread_id="t"
        )
        target.write_bytes(b"after")
        restore_checkpoint(self.root, checkpoint.id)
        self.assertEqual(target.read_bytes(), b"\x00before\xff")

    def test_sealed_checkpoint_detects_later_conflict(self):
        target = self.root / "app.py"
        target.write_text("before", encoding="utf-8")
        checkpoint = create_checkpoint(
            self.root, ["app.py"], workspace_id="w", thread_id="t"
        )
        target.write_text("expected after", encoding="utf-8")
        seal_checkpoint(self.root, checkpoint.id)
        target.write_text("external change", encoding="utf-8")

        preview = preview_restore(self.root, checkpoint.id)
        self.assertEqual(preview.conflicts, ["app.py"])
        with self.assertRaises(CheckpointConflictError):
            restore_checkpoint(self.root, checkpoint.id)
        restore_checkpoint(self.root, checkpoint.id, force=True)
        self.assertEqual(target.read_text(encoding="utf-8"), "before")

    def test_paths_cannot_escape_workspace(self):
        with self.assertRaises(ValueError):
            create_checkpoint(
                self.root, ["../outside.txt"], workspace_id="w", thread_id="t"
            )

    def test_agent_tools_cannot_read_checkpoint_storage(self):
        workspace = WorkspaceContext(root=self.root, execution_target="local")
        with self.assertRaises(PermissionError):
            resolve_workspace_path(
                workspace, ".compass/checkpoints/abc/manifest.json"
            )

    def test_list_is_newest_first_and_manifest_has_identity(self):
        first = create_checkpoint(
            self.root, ["a.py"], workspace_id="w", thread_id="t", label="first"
        )
        second = create_checkpoint(
            self.root, ["b.py"], workspace_id="w", thread_id="t", label="second"
        )
        values = list_checkpoints(self.root, workspace_id="w", thread_id="t")
        self.assertEqual([item.id for item in values], [second.id, first.id])
        self.assertEqual(values[0].workspace_id, "w")

    def test_change_tracker_undo_removes_a_new_file(self):
        target = self.root / "new.py"
        tracker = ChangeTracker()
        before = tracker.snapshot_before_write(str(target))
        target.write_text("created", encoding="utf-8")
        tracker.record_change(str(target), before or "", "created", "write_to_file")

        tracker.undo_last()

        self.assertFalse(target.exists())


class CheckpointToolBatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_batch_creates_one_checkpoint_before_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "app.py"
            target.write_text("before", encoding="utf-8")

            class FakeToolNode:
                def __init__(self, _tools):
                    pass

                async def ainvoke(self, _state, _config):
                    target.write_text("after", encoding="utf-8")
                    return {"messages": []}

            call = AIMessage(content="", tool_calls=[{
                "id": "edit-1", "name": "edit_file", "args": {"path": "app.py"}
            }])
            config = {"configurable": {
                "thread_id": "thread",
                "execution_target": "local",
                "workspace_context": {
                    "root": str(root),
                    "execution_target": "local",
                    "workspace_id": "workspace",
                },
            }}
            with patch("agent.graph.tool_node.ToolNode", FakeToolNode):
                await CompassToolNode(build_builtin_registry())(
                    {"messages": [call]}, config
                )
            values = list_checkpoints(root, workspace_id="workspace", thread_id="thread")
            restore_checkpoint(root, values[0].id)

            self.assertEqual(len(values), 1)
            self.assertEqual(target.read_text(encoding="utf-8"), "before")


if __name__ == "__main__":
    unittest.main()
