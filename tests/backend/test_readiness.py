import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from backend.auth.credentials import _fernet
from backend.config import Settings
from backend.main import app
from backend.services.readiness import (
    ReadinessServices,
    _checkpointer_probe,
    build_readiness_report,
    get_readiness_report,
)
from backend.services.workspace import create_workspace_record


class CloudConfigurationTests(unittest.TestCase):
    def test_cloud_rejects_known_default_jwt_secrets(self):
        for secret in (
            "compass-dev-secret-change-me-in-production",
            "super-secret-default-key-please-change",
            "j" * 32,
        ):
            with self.subTest(secret=secret), self.assertRaisesRegex(
                ValueError, "JWT_SECRET"
            ):
                Settings(
                    DB_URI="postgresql://user:pass@db/compass",
                    COMPASS_CLOUD_MODE=True,
                    JWT_SECRET=secret,
                    CREDENTIAL_ENCRYPTION_KEY=Fernet.generate_key().decode(),
                    SECURE_COOKIES=True,
                )

    def test_cloud_requires_separate_encryption_key_and_secure_cookies(self):
        secure_jwt = "M3adow!Quartz-7River$Orbit#2026-Key"
        with self.assertRaisesRegex(ValueError, "CREDENTIAL_ENCRYPTION_KEY"):
            Settings(
                DB_URI="postgresql://user:pass@db/compass",
                COMPASS_CLOUD_MODE=True,
                JWT_SECRET=secure_jwt,
                SECURE_COOKIES=True,
            )

        with self.assertRaisesRegex(ValueError, "SECURE_COOKIES"):
            Settings(
                DB_URI="postgresql://user:pass@db/compass",
                COMPASS_CLOUD_MODE=True,
                JWT_SECRET=secure_jwt,
                CREDENTIAL_ENCRYPTION_KEY=Fernet.generate_key().decode(),
                SECURE_COOKIES=False,
            )

    def test_cloud_accepts_independent_secrets_with_secure_cookies(self):
        configured = Settings(
            DB_URI="postgresql://user:pass@db/compass",
            COMPASS_CLOUD_MODE=True,
            JWT_SECRET="M3adow!Quartz-7River$Orbit#2026-Key",
            CREDENTIAL_ENCRYPTION_KEY=Fernet.generate_key().decode(),
            SECURE_COOKIES=True,
        )

        self.assertTrue(configured.compass_cloud_mode)

    def test_blank_optional_capabilities_are_unconfigured(self):
        configured = Settings(
            DB_URI="postgresql://user:pass@db/compass",
            MCP_SERVERS_FILE="",
            EMBEDDING_PROVIDER="",
            EMBEDDING_MODEL="",
        )

        self.assertIsNone(configured.mcp_servers_file)
        self.assertIsNone(configured.embedding_provider)
        self.assertIsNone(configured.embedding_model)

    def test_credential_derivation_is_disabled_in_cloud_mode(self):
        unsafe_settings = SimpleNamespace(
            compass_cloud_mode=True,
            credential_encryption_key=None,
            jwt_secret="j" * 32,
        )
        with patch(
            "backend.auth.credentials.settings", unsafe_settings
        ), self.assertRaisesRegex(RuntimeError, "CREDENTIAL_ENCRYPTION_KEY"):
            _fernet()


def healthy_services(**overrides):
    probes = {
        "database": lambda: True,
        "checkpointer": lambda: True,
        "workspace": lambda: True,
        "memory_store": lambda: True,
        "embeddings": lambda: True,
        "mcp": lambda: None,
    }
    probes.update(overrides)
    return ReadinessServices(**probes)


class ReadinessTests(unittest.TestCase):
    def test_checkpointer_probe_reads_the_durable_table_without_workflow_loop(self):
        statements = []

        class FakeConnection:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def execute(self, statement):
                statements.append(str(statement))

        class FakeEngine:
            def connect(self):
                return FakeConnection()

        with patch("backend.db.engine", FakeEngine()), patch(
            "agent.graph.workflow.get_workflow",
            side_effect=AssertionError("workflow must stay on the application loop"),
        ):
            self.assertTrue(_checkpointer_probe())

        self.assertEqual(statements, ["SELECT 1 FROM checkpoints LIMIT 1"])

    def test_database_failure_makes_service_unready(self):
        def fail_database():
            raise RuntimeError("postgresql://alice:secret@private-db/compass")

        report = build_readiness_report(
            healthy_services(database=fail_database)
        )

        self.assertFalse(report.ready)
        self.assertEqual(report.components["database"].status, "failed")
        self.assertNotIn("alice", str(report.model_dump()))
        self.assertNotIn("private-db", str(report.model_dump()))

    def test_missing_embedding_is_degraded_not_unready(self):
        report = build_readiness_report(
            healthy_services(embeddings=lambda: None)
        )

        self.assertTrue(report.ready)
        self.assertEqual(report.components["embeddings"].status, "unavailable")

    def test_required_probe_is_bounded_by_timeout(self):
        report = build_readiness_report(
            healthy_services(database=lambda: time.sleep(0.2) or True),
            timeout_seconds=0.02,
        )

        self.assertFalse(report.ready)
        self.assertEqual(report.components["database"].status, "failed")

    def test_timed_out_probe_is_reused_instead_of_queued_again(self):
        release = Event()
        calls = 0

        def blocked_database():
            nonlocal calls
            calls += 1
            release.wait()
            return True

        services = healthy_services(database=blocked_database)
        try:
            build_readiness_report(services, timeout_seconds=0.01)
            build_readiness_report(services, timeout_seconds=0.01)
            self.assertEqual(calls, 1)
        finally:
            release.set()

    def test_readiness_result_is_cached_for_five_seconds(self):
        calls = 0

        def database():
            nonlocal calls
            calls += 1
            return True

        services = healthy_services(database=database)
        first = get_readiness_report(services=services)
        second = get_readiness_report(services=services)

        self.assertIs(first, second)
        self.assertEqual(calls, 1)

    def test_ready_returns_503_but_health_stays_live_on_dependency_failure(self):
        app.state.readiness_services = healthy_services(database=lambda: False)
        try:
            client = TestClient(app)
            ready_response = client.get("/ready")
            health_response = client.get("/health")
        finally:
            del app.state.readiness_services

        self.assertEqual(ready_response.status_code, 503)
        self.assertFalse(ready_response.json()["ready"])
        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(
            health_response.json(),
            {"status": "ok", "service": "compass-api"},
        )


class WorkspaceRootTests(unittest.TestCase):
    def test_workspace_creation_uses_the_configured_storage_root(self):
        class FakeSession:
            def add(self, value):
                self.value = value

            def commit(self):
                pass

            def refresh(self, value):
                pass

        with TemporaryDirectory() as temp_dir, patch(
            "backend.services.workspace.settings.workspace_root", Path(temp_dir)
        ):
            workspace = create_workspace_record(
                FakeSession(), "user-1", "session-1", "Demo"
            )

        self.assertEqual(Path(workspace.storage_path).parents[1], Path(temp_dir))


if __name__ == "__main__":
    unittest.main()
