from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException

from backend.services import workspace as workspace_service
from backend.services.session_manager import list_sessions
from tests.backend.support import DatabaseTestCase


class ActiveWorkspaceTests(DatabaseTestCase):
    def test_newest_failed_workspace_does_not_shadow_active_workspace(self):
        active = self.workspace(status="ready", project_id="project-stable")
        failed = self.workspace(status="failed", project_id="failed-project")
        active.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        failed.created_at = active.created_at + timedelta(minutes=1)
        self.session.active_workspace_id = active.id
        self.db.commit()

        selected = workspace_service.get_workspace_by_session(
            self.db,
            self.session.id,
            self.user.id,
        )

        self.assertEqual(selected.id, active.id)
        self.assertNotEqual(selected.id, failed.id)

    def test_attach_requires_a_ready_workspace_from_the_same_owned_session(self):
        ready = self.workspace(status="ready")
        failed = self.workspace(status="failed")
        other = self.workspace(
            user=self.other_user,
            session=self.other_session,
        )
        self.db.commit()

        attached = workspace_service.attach_active_workspace(
            self.db,
            self.session.id,
            ready.id,
            self.user.id,
        )
        self.assertEqual(attached.id, ready.id)
        self.assertEqual(self.session.active_workspace_id, ready.id)

        for workspace_id in (failed.id, other.id):
            with self.subTest(workspace_id=workspace_id), self.assertRaises(
                HTTPException
            ):
                workspace_service.attach_active_workspace(
                    self.db,
                    self.session.id,
                    workspace_id,
                    self.user.id,
                )

    def test_missing_active_workspace_is_not_replaced_by_latest_row(self):
        self.workspace(status="ready")
        self.db.commit()

        with self.assertRaises(HTTPException) as error:
            workspace_service.get_workspace_by_session(
                self.db,
                self.session.id,
                self.user.id,
            )

        self.assertEqual(error.exception.status_code, 404)

    def test_stats_refresh_preserves_github_binding(self):
        workspace = self.github_workspace()
        Path(workspace.storage_path, "README.md").write_text(
            "# Test repository\n",
            encoding="utf-8",
        )
        before = (workspace.project_id, workspace.git_remote, workspace.git_branch)

        workspace_service.update_workspace_stats(self.db, workspace)

        self.assertEqual(
            (workspace.project_id, workspace.git_remote, workspace.git_branch),
            before,
        )

    def test_session_count_is_not_multiplied_by_workspaces(self):
        active = self.workspace(status="ready", project_id="active")
        self.session.active_workspace_id = active.id
        self.add_messages(2)
        self.workspace(status="ready", project_id="second")
        self.db.commit()

        item = list_sessions(self.db, self.user.id)[0]

        self.assertEqual(item.message_count, 2)
        self.assertEqual(item.workspace_name, active.name)


if __name__ == "__main__":
    import unittest

    unittest.main()
