from pathlib import Path

from fastapi import HTTPException

from backend.models.patch import WorkspacePatch
from backend.services.ownership import (
    owned_patch,
    owned_session,
    owned_workspace,
    safe_workspace_target,
)
from tests.backend.support import DatabaseTestCase


class WorkspaceBoundaryTests(DatabaseTestCase):
    def test_workspace_root_targets_are_rejected(self):
        for value in ("", "."):
            with self.subTest(value=value), self.assertRaises(HTTPException) as error:
                safe_workspace_target(self.root, value)
            self.assertEqual(error.exception.status_code, 400)

    def test_child_target_is_allowed(self):
        result = safe_workspace_target(self.root, "src/app.py")

        self.assertEqual(result, (self.root / "src" / "app.py").resolve())

    def test_parent_traversal_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            safe_workspace_target(self.root, "../outside.txt")

        self.assertEqual(error.exception.status_code, 400)


class OwnedResourceTests(DatabaseTestCase):
    def test_cross_user_session_and_workspace_are_hidden(self):
        other_workspace = self.workspace(
            user=self.other_user,
            session=self.other_session,
        )
        self.db.commit()

        for lookup in (
            lambda: owned_session(self.db, self.other_session.id, self.user.id),
            lambda: owned_workspace(self.db, other_workspace.id, self.user.id),
        ):
            with self.subTest(lookup=lookup), self.assertRaises(HTTPException) as error:
                lookup()
            self.assertEqual(error.exception.status_code, 404)

    def test_patch_must_belong_to_the_requested_owned_workspace(self):
        workspace_a = self.workspace()
        workspace_b = self.workspace()
        patch_a = WorkspacePatch(
            workspace_id=workspace_a.id,
            status="pending",
            changes=[],
        )
        self.db.add(patch_a)
        self.db.commit()

        with self.assertRaises(HTTPException) as error:
            owned_patch(self.db, workspace_b.id, patch_a.id, self.user.id)

        self.assertEqual(error.exception.status_code, 404)

    def test_owned_resources_are_returned(self):
        workspace = self.workspace()
        patch = WorkspacePatch(
            workspace_id=workspace.id,
            status="pending",
            changes=[],
        )
        self.db.add(patch)
        self.db.commit()

        self.assertEqual(
            owned_session(self.db, self.session.id, self.user.id).id,
            self.session.id,
        )
        self.assertEqual(
            owned_workspace(self.db, workspace.id, self.user.id).id,
            workspace.id,
        )
        self.assertEqual(
            owned_patch(self.db, workspace.id, patch.id, self.user.id).id,
            patch.id,
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
