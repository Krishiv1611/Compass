import unittest

from fastapi import BackgroundTasks, HTTPException

from agent.checkpoints import create_checkpoint
from backend.routers.checkpoints import (
    RestoreCheckpointRequest,
    get_checkpoint_restore_preview,
    get_workspace_checkpoints,
    restore_workspace_checkpoint,
)
from tests.backend.support import DatabaseTestCase


class CheckpointEndpointTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.workspace_record = self.workspace()
        self.target = self.root / self.workspace_record.id / "app.py"
        self.target.write_text("before", encoding="utf-8")
        self.checkpoint = create_checkpoint(
            self.workspace_record.storage_path,
            ["app.py"],
            workspace_id=self.workspace_record.id,
            thread_id=self.session.thread_id,
        )
        self.target.write_text("after", encoding="utf-8")

    def test_owner_can_list_preview_and_restore(self):
        values = get_workspace_checkpoints(
            self.workspace_record.id, current_user=self.user, db=self.db
        )
        preview = get_checkpoint_restore_preview(
            self.workspace_record.id,
            self.checkpoint.id,
            current_user=self.user,
            db=self.db,
        )
        restored = restore_workspace_checkpoint(
            self.workspace_record.id,
            self.checkpoint.id,
            RestoreCheckpointRequest(),
            BackgroundTasks(),
            current_user=self.user,
            db=self.db,
        )

        self.assertEqual(values[0]["id"], self.checkpoint.id)
        self.assertEqual(preview["changes"], ["app.py"])
        self.assertEqual(restored["affected_files"], ["app.py"])
        self.assertEqual(self.target.read_text(encoding="utf-8"), "before")

    def test_another_user_cannot_access_workspace_checkpoints(self):
        with self.assertRaises(HTTPException) as denied:
            get_workspace_checkpoints(
                self.workspace_record.id,
                current_user=self.other_user,
                db=self.db,
            )
        self.assertEqual(denied.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
