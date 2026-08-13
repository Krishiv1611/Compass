import io
import asyncio
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from jose import JWTError

from backend.auth.jwt import create_oauth_state, decode_oauth_state
from backend.models.github_connection import GitHubConnection
from backend.schemas.workspace import WorkspaceResponse
from backend.services.github import MAX_EXPANDED_BYTES, validate_repository_archive
from backend.services import github as github_service
from backend.routers.workspaces import get_workspace_tree, upload_workspace
from tests.backend.support import DatabaseTestCase


class GitHubStateTests(unittest.TestCase):
    def test_connect_state_is_bound_to_authenticated_user(self):
        state = create_oauth_state(
            "github",
            intent="connect_github",
            user_id="user-a",
        )
        decoded = decode_oauth_state(
            state,
            "github",
            expected_user_id="user-a",
        )
        self.assertEqual(decoded["user_id"], "user-a")
        with self.assertRaises(JWTError):
            decode_oauth_state(
                state,
                "github",
                expected_user_id="user-b",
            )


class GitHubArchiveTests(unittest.TestCase):
    def test_declared_expanded_size_is_rejected_before_extraction(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("repo/file.txt", "small")
        archive.seek(0)
        with zipfile.ZipFile(archive) as bundle:
            info = bundle.infolist()[0]
            info.file_size = MAX_EXPANDED_BYTES + 1
            with self.assertRaises(HTTPException) as oversized:
                validate_repository_archive(bundle)
        self.assertEqual(oversized.exception.status_code, 413)

    def test_one_http_client_is_reused_for_an_operation(self):
        clients = []

        class FakeClient:
            def __init__(self, **_kwargs):
                self.requests = []
                clients.append(self)

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def request(self, method, path, **_kwargs):
                self.requests.append((method, path))
                return SimpleNamespace(status_code=200)

        @github_service.github_operation
        def two_requests():
            github_service._token_request("secret", "GET", "/one")
            github_service._token_request("secret", "GET", "/two")

        with patch.object(github_service.httpx, "Client", FakeClient):
            two_requests()

        self.assertEqual(len(clients), 1)
        self.assertEqual(
            clients[0].requests,
            [("GET", "/one"), ("GET", "/two")],
        )
    def test_traversal_and_symlink_members_are_rejected(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("../outside.txt", "bad")
        archive.seek(0)
        with zipfile.ZipFile(archive) as bundle:
            with self.assertRaises(HTTPException):
                validate_repository_archive(bundle)


class GitHubConnectionTests(DatabaseTestCase):
    def test_repository_connection_does_not_replace_login_identity(self):
        self.user.oauth_provider = "google"
        self.user.oauth_provider_id = "google-123"
        self.user.oauth_token_encrypted = "google-login-token"
        self.user.oauth_scopes = "openid,email"
        connection = GitHubConnection(
            user_id=self.user.id,
            provider_user_id="github-456",
            token_encrypted="github-token",
            scopes="repo",
        )
        self.db.add(connection)
        self.db.commit()

        self.assertEqual(self.user.oauth_provider, "google")
        self.assertEqual(self.user.oauth_provider_id, "google-123")
        self.assertEqual(self.user.oauth_token_encrypted, "google-login-token")
        self.assertEqual(self.user.oauth_scopes, "openid,email")

    def test_oauth_repository_connect_preserves_google_login_fields(self):
        self.user.oauth_provider = "google"
        self.user.oauth_provider_id = "google-123"
        self.user.oauth_token_encrypted = "google-login-token"
        self.user.oauth_scopes = "openid,email"
        response = SimpleNamespace(
            status_code=200,
            json=lambda: {"login": "octocat", "avatar_url": None},
            headers={},
        )
        with patch.object(github_service, "_token_request", return_value=response):
            github_service.connect_oauth_token(
                self.db,
                self.user,
                "github-secret",
                "github-456",
                "octocat",
                None,
                "repo",
            )

        self.assertEqual(self.user.oauth_provider, "google")
        self.assertEqual(self.user.oauth_provider_id, "google-123")
        self.assertEqual(self.user.oauth_token_encrypted, "google-login-token")
        self.assertEqual(self.user.oauth_scopes, "openid,email")

    def test_public_workspace_response_hides_storage_path(self):
        workspace = self.workspace(status="ready")
        response = WorkspaceResponse.model_validate(workspace)
        payload = response.model_dump()
        self.assertNotIn("storage_path", payload)
        self.assertEqual(payload["id"], workspace.id)

    def test_aggregate_upload_and_legacy_tree_are_bounded(self):
        too_many = [SimpleNamespace(filename=None) for _ in range(2001)]
        with self.assertRaises(HTTPException) as upload_error:
            asyncio.run(
                upload_workspace(
                    self.session.id,
                    too_many,
                    current_user=self.user,
                    db=self.db,
                )
            )
        self.assertEqual(upload_error.exception.status_code, 413)

        workspace = self.workspace(status="ready")
        root = self.root / workspace.id
        for index in range(2001):
            (root / f"{index}.txt").write_text("x", encoding="utf-8")
        with self.assertRaises(HTTPException) as tree_error:
            get_workspace_tree(
                workspace.id,
                current_user=self.user,
                db=self.db,
            )
        self.assertEqual(tree_error.exception.status_code, 413)


if __name__ == "__main__":
    unittest.main()
