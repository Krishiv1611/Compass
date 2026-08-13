import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend.services.patch_manager import apply_patch, create_patch
from backend.models.run import AgentRun, RunEvent
from tests.backend.support import DatabaseTestCase


class PatchAtomicityTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.workspace_record = self.workspace(status="ready")
        self.first = Path(self.workspace_record.storage_path) / "first.txt"
        self.second = Path(self.workspace_record.storage_path) / "second.txt"
        self.first.write_text("first-before", encoding="utf-8")
        self.second.write_text("second-before", encoding="utf-8")
        self.patch_record = create_patch(
            self.db,
            self.workspace_record.id,
            None,
            [
                {"type": "edit", "path": "first.txt", "content": "first-after"},
                {"type": "edit", "path": "second.txt", "content": "second-after"},
            ],
        )

    def test_second_replace_failure_restores_both_targets(self):
        from backend.services import patch_manager

        real_replace = patch_manager.os.replace
        target_replacements = 0

        def fail_second_target(source, target):
            nonlocal target_replacements
            if Path(target) in {self.first, self.second}:
                target_replacements += 1
                if target_replacements == 2:
                    raise OSError("injected replacement failure")
            return real_replace(source, target)

        with patch.object(patch_manager.os, "replace", side_effect=fail_second_target):
            with self.assertRaises(OSError):
                apply_patch(
                    self.db,
                    self.patch_record.id,
                    self.user.id,
                    expected_version=1,
                )

        self.db.expire_all()
        self.assertEqual(self.first.read_text(encoding="utf-8"), "first-before")
        self.assertEqual(self.second.read_text(encoding="utf-8"), "second-before")
        self.assertEqual(self.patch_record.status, "pending")
        self.assertEqual(self.patch_record.version, 1)

    def test_stale_expected_version_is_rejected(self):
        applied = apply_patch(
            self.db,
            self.patch_record.id,
            self.user.id,
            expected_version=1,
        )
        self.assertEqual(applied.version, 2)

        with self.assertRaises(HTTPException) as stale:
            apply_patch(
                self.db,
                self.patch_record.id,
                self.user.id,
                expected_version=1,
            )
        self.assertEqual(stale.exception.status_code, 409)

    def test_patch_creation_records_workspace_patch_event(self):
        run = AgentRun(
            session_id=self.session.id,
            workspace_id=self.workspace_record.id,
            status="running",
        )
        self.db.add(run)
        self.db.commit()

        created = create_patch(
            self.db,
            self.workspace_record.id,
            run.id,
            [{"type": "edit", "path": "first.txt", "content": "next"}],
        )

        event = (
            self.db.query(RunEvent)
            .filter(
                RunEvent.run_id == run.id,
                RunEvent.event_type == "workspace_patch",
            )
            .one()
        )
        self.assertEqual(event.content["patch_id"], created.id)
        self.assertEqual(event.content["workspace_id"], self.workspace_record.id)
        self.assertEqual(event.content["session_id"], self.session.id)


if __name__ == "__main__":
    unittest.main()
