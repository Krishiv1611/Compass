import unittest

from backend.services.workspace_changes import FileChange, apply_workspace_metadata_delta
from tests.backend.support import stub_workspace


class WorkspaceChangeTests(unittest.TestCase):
    def test_create_updates_count_and_size_without_scan(self):
        workspace = stub_workspace(file_count=2, size_bytes=20)
        apply_workspace_metadata_delta(
            workspace,
            [FileChange("a.py", 0, 12, "create")],
        )
        self.assertEqual((workspace.file_count, workspace.size_bytes), (3, 32))

    def test_edit_updates_only_size(self):
        workspace = stub_workspace(file_count=2, size_bytes=20)
        apply_workspace_metadata_delta(
            workspace,
            [FileChange("a.py", 5, 8, "edit")],
        )
        self.assertEqual((workspace.file_count, workspace.size_bytes), (2, 23))

    def test_delete_and_rename_keep_totals_valid(self):
        workspace = stub_workspace(file_count=2, size_bytes=20)
        apply_workspace_metadata_delta(
            workspace,
            [
                FileChange("a.py", 5, 0, "delete"),
                FileChange("b.py", 15, 15, "rename"),
            ],
        )
        self.assertEqual((workspace.file_count, workspace.size_bytes), (1, 15))


if __name__ == "__main__":
    unittest.main()
