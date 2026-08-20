"""Regression coverage for auth revocation and process-local WS limits."""

from __future__ import annotations

import asyncio
import unittest
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException, Response
from sqlalchemy.exc import IntegrityError

from backend.auth.jwt import create_refresh_token
from backend.auth.oauth import get_or_create_oauth_user
from backend.middleware.rate_limit import _TokenBucket
from backend.models.run import AgentRun
from backend.routers import auth, chat
from backend.schemas.chat import WsClientMessage
from backend.services import session_manager
from backend.services.run_context import RunContextSnapshot
from backend.services.ws_limits import WebSocketLimits
from tests.backend.support import DatabaseTestCase


class RefreshRevocationTests(DatabaseTestCase):
    """A refresh token must be single-use and invalid after logout."""

    def test_logout_invalidates_the_issued_refresh_token(self):
        token = create_refresh_token(self.user.id, self.user.refresh_version)

        auth.logout(Response(), current_user=self.user, db=self.db)

        with self.assertRaises(HTTPException) as rejected:
            auth.refresh(Response(), auth.RefreshRequest(token=token), None, self.db)
        self.assertEqual(rejected.exception.status_code, 401)

    def test_refresh_rotation_rejects_replay_of_the_old_token(self):
        token = create_refresh_token(self.user.id, self.user.refresh_version)

        auth.refresh(Response(), auth.RefreshRequest(token=token), None, self.db)

        with self.assertRaises(HTTPException) as rejected:
            auth.refresh(Response(), auth.RefreshRequest(token=token), None, self.db)
        self.assertEqual(rejected.exception.status_code, 401)

    def test_second_conditional_rotation_loses_the_replay_race(self):
        token = create_refresh_token(self.user.id, self.user.refresh_version)

        auth.refresh(Response(), auth.RefreshRequest(token=token), None, self.db)

        with self.assertRaises(HTTPException) as rejected:
            auth.refresh(Response(), auth.RefreshRequest(token=token), None, self.db)
        self.assertEqual(rejected.exception.status_code, 401)


class OAuthIdentityTests(DatabaseTestCase):
    """OAuth identities must be verified, canonical, and conflict-safe."""

    def test_unverified_email_is_rejected_before_creating_an_account(self):
        with self.assertRaises(HTTPException) as rejected:
            get_or_create_oauth_user(
                self.db,
                provider="google",
                provider_id="google-1",
                email="person@example.test",
                email_verified=False,
            )
        self.assertEqual(rejected.exception.status_code, 400)

    def test_verified_mixed_case_email_resolves_to_one_canonical_account(self):
        first = get_or_create_oauth_user(
            self.db,
            provider="google",
            provider_id="google-1",
            email=" Person@Example.Test ",
            email_verified=True,
        )
        second = get_or_create_oauth_user(
            self.db,
            provider="google",
            provider_id="google-1",
            email="person@example.test",
            email_verified=True,
        )

        self.assertEqual(first.id, second.id)
        self.assertEqual(first.email, "person@example.test")

    def test_provider_identity_insert_race_becomes_conflict(self):
        original_commit = self.db.commit

        def collide_once():
            self.db.commit = original_commit
            raise IntegrityError("insert", {}, Exception("unique"))

        self.db.commit = collide_once
        with self.assertRaises(HTTPException) as rejected:
            get_or_create_oauth_user(
                self.db,
                provider="github",
                provider_id="github-1",
                email="person@example.test",
                email_verified=True,
            )
        self.assertEqual(rejected.exception.status_code, 409)

    def test_google_v2_verified_email_claim_is_accepted(self):
        async def exercise():
            with (
                patch.object(auth, "decode_oauth_state", return_value={"redirect_uri": "https://app.test/callback"}),
                patch.object(
                    auth,
                    "exchange_google_code",
                    return_value={
                        "id": "google-1",
                        "email": "person@example.test",
                        "verified_email": True,
                    },
                ),
                patch.object(auth, "get_or_create_oauth_user", return_value=self.user) as create_user,
            ):
                await auth.oauth_google(
                    "code", "https://app.test/callback", "state", Response(), self.db
                )
            self.assertTrue(create_user.call_args.kwargs["email_verified"])

        asyncio.run(exercise())


class ProcessLocalLimitsTests(unittest.IsolatedAsyncioTestCase):
    """The limiter bounds cost and releases state as connections/runs finish."""

    async def test_sixth_connection_is_closed_with_policy_code(self):
        limits = WebSocketLimits()

        class Socket:
            def __init__(self):
                self.close = AsyncMock()

        sockets = [Socket() for _ in range(6)]

        for socket in sockets[:5]:
            self.assertTrue(await limits.acquire_connection("user-1", socket))
        self.assertFalse(await limits.acquire_connection("user-1", sockets[5]))
        sockets[5].close.assert_awaited_once_with(code=1008, reason="Connection limit exceeded")

    async def test_65_kib_message_is_closed_as_too_large(self):
        limits = WebSocketLimits()
        socket = SimpleNamespace(close=AsyncMock())

        self.assertFalse(await limits.validate_message(socket, "x" * (65 * 1024)))
        socket.close.assert_awaited_once_with(code=1009, reason="Message too large")

    def test_third_active_run_is_rejected_without_starting_model_work(self):
        limits = WebSocketLimits()

        self.assertTrue(limits.acquire_run("user-1", "run-1"))
        self.assertTrue(limits.acquire_run("user-1", "run-2"))
        self.assertFalse(limits.acquire_run("user-1", "run-3"))

    async def test_run_cap_rejects_before_agent_model_work_starts(self):
        limits = WebSocketLimits()
        limits.acquire_run("user-1", "run-1")
        limits.acquire_run("user-1", "run-2")
        snapshot = RunContextSnapshot(
            user_id="user-1", session_id="session-1", thread_id="thread-1",
            workspace_id="workspace-1", workspace_path=".", project_id="project-1",
            context_version="version-1", session_context_version="version-1", preferences={},
        )

        with (
            patch.object(chat, "ws_limits", limits),
            patch.object(chat.agent_runner, "run_agent_stream") as run_agent,
            self.assertRaises(HTTPException) as rejected,
        ):
            [
                event async for event in chat._stream_agent_turn(
                    snapshot, WsClientMessage(type="message", content="hello")
                )
            ]

        self.assertEqual(rejected.exception.status_code, 429)
        run_agent.assert_not_called()

    async def test_braced_uppercase_run_id_releases_the_canonical_quota_key(self):
        limits = WebSocketLimits()
        canonical_run_id = "12345678-1234-1234-1234-123456789abc"
        snapshot = RunContextSnapshot(
            user_id="user-1", session_id="session-1", thread_id="thread-1",
            workspace_id="workspace-1", workspace_path=".", project_id="project-1",
            context_version="version-1", session_context_version="version-1", preferences={},
        )

        class DbContext:
            def __enter__(self):
                return object()

            def __exit__(self, *_args):
                return False

        async def runner(**_kwargs):
            yield chat.StreamEvent(type=chat.StreamEventType.DONE, data={"status": "completed"})

        with (
            patch.object(chat, "ws_limits", limits),
            patch.object(chat, "_claim_run_record", return_value=canonical_run_id),
            patch.object(chat.agent_runner, "run_agent_stream", runner),
            patch.object(chat, "SessionLocal", return_value=DbContext()),
            patch.object(chat, "persist_run_events"),
            patch.object(chat, "_end_run_record"),
        ):
            [
                event async for event in chat._stream_agent_turn(
                    snapshot,
                    WsClientMessage(type="message", content="hello", run_id="{12345678-1234-1234-1234-123456789ABC}"),
                )
            ]

        self.assertFalse(limits._active_runs)

    async def test_connect_failure_releases_connection_quota(self):
        limits = WebSocketLimits()

        class Socket:
            def __init__(self):
                self.headers = {"sec-websocket-protocol": "compass.v1, compass.jwt.token"}
                self.query_params = {}
                self.close = AsyncMock()

        class Query:
            def filter(self, *_args):
                return self

            def first(self):
                return SimpleNamespace(id="user-1", is_active=True)

        class Db:
            def query(self, *_args):
                return Query()

            def close(self):
                pass

        with (
            patch.object(chat, "SessionLocal", return_value=Db()),
            patch.object(chat, "decode_token", return_value={"type": "access", "sub": "user-1"}),
            patch.object(chat, "ws_limits", limits),
            patch.object(chat.manager, "connect", side_effect=RuntimeError("accept failed")),
        ):
            await chat.websocket_chat(Socket(), "session-1")

        self.assertFalse(limits._connections)

    def test_start_window_rejects_the_eleventh_run_and_prunes_old_starts(self):
        now = datetime.now(UTC)
        limits = WebSocketLimits(clock=lambda: now)

        for index in range(10):
            self.assertTrue(limits.record_run_start("user-1"))
        self.assertFalse(limits.record_run_start("user-1"))
        limits.clock = lambda: now + timedelta(minutes=1, seconds=1)
        self.assertTrue(limits.record_run_start("user-1"))


class HttpRateLimitTests(unittest.TestCase):
    def test_expired_empty_bucket_is_removed(self):
        now = [0.0]
        bucket = _TokenBucket(clock=lambda: now[0])
        self.assertTrue(bucket.is_allowed("client"))

        now[0] = 61.0
        self.assertEqual(bucket.remaining("client"), 60)
        self.assertNotIn("client", bucket._buckets)

    def test_import_consumes_more_quota_than_a_health_read(self):
        bucket = _TokenBucket()
        self.assertTrue(bucket.is_allowed("client", weight=1))
        after_read = bucket.remaining("client")
        self.assertTrue(bucket.is_allowed("client", weight=5))
        self.assertLess(bucket.remaining("client"), after_read - 1)


class SessionCleanupTests(DatabaseTestCase):
    def test_soft_delete_cancels_runs_and_disconnects_sockets_before_commit(self):
        run = AgentRun(id=str(uuid.uuid4()), session_id=self.session.id, status="running")
        self.db.add(run)
        self.db.commit()
        events: list[str] = []

        def commit():
            events.append("commit")

        with (
            patch.object(session_manager, "cancel_agent_run", side_effect=lambda _id: events.append("cancel")),
            patch.object(session_manager.manager, "disconnect_session", new=AsyncMock(side_effect=lambda _id: events.append("disconnect"))),
            patch.object(self.db, "commit", side_effect=commit),
        ):
            self.assertTrue(asyncio.run(session_manager.delete_session(self.db, self.user.id, self.session.id)))

        self.assertEqual(events, ["cancel", "disconnect", "commit"])

    def test_deleting_session_blocks_new_run_and_socket_admission_before_commit(self):
        async def exercise():
            limits = WebSocketLimits()
            entered_disconnect = asyncio.Event()
            release_disconnect = asyncio.Event()

            async def disconnect(_session_id):
                entered_disconnect.set()
                await release_disconnect.wait()

            class Socket:
                def __init__(self):
                    self.close = AsyncMock()

            with (
                patch.object(session_manager, "ws_limits", limits),
                patch.object(session_manager.manager, "disconnect_session", side_effect=disconnect),
            ):
                deleting = asyncio.create_task(
                    session_manager.delete_session(self.db, self.user.id, self.session.id)
                )
                await entered_disconnect.wait()
                self.assertFalse(limits.begin_run(self.user.id, "run-1", session_id=self.session.id))
                self.assertFalse(
                    await limits.acquire_connection(self.user.id, Socket(), session_id=self.session.id)
                )
                release_disconnect.set()
                self.assertTrue(await deleting)

        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
