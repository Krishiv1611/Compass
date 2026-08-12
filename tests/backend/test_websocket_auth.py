import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from jose import JWTError

from backend.routers import chat


class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args):
        return self

    def first(self):
        return self._result


class _FakeDatabase:
    def __init__(self, user):
        self.user = user
        self.queried_models = []
        self.closed = False

    def query(self, model):
        self.queried_models.append(model)
        return _FakeQuery(self.user)

    def close(self):
        self.closed = True


class WebSocketAuthenticationTests(unittest.TestCase):
    def test_valid_protocol_authenticates_an_active_user(self):
        database = _FakeDatabase(
            SimpleNamespace(id="user-123", is_active=True),
        )

        with patch.object(
            chat,
            "decode_token",
            return_value={"type": "access", "sub": "user-123"},
        ):
            user_id = chat.authenticate_websocket_user(
                "compass.v1, compass.jwt.signed-token",
                None,
                database,
            )

        self.assertEqual(user_id, "user-123")
        self.assertEqual(database.queried_models, [chat.User])

    def test_missing_protocol_credentials_are_rejected(self):
        with self.assertRaisesRegex(chat.WebSocketAuthError, "Missing credentials"):
            chat.extract_websocket_access_token(None, None)

    def test_query_string_credentials_are_rejected(self):
        with self.assertRaisesRegex(
            chat.WebSocketAuthError,
            "Query string credentials are not accepted",
        ):
            chat.extract_websocket_access_token(
                "compass.v1, compass.jwt.header-token",
                "query-token",
            )

    def test_malformed_token_is_rejected(self):
        with patch.object(chat, "decode_token", side_effect=JWTError("invalid")):
            with self.assertRaisesRegex(
                chat.WebSocketAuthError,
                "Invalid or expired token",
            ):
                chat.authenticate_websocket_user(
                    "compass.v1, compass.jwt.bad-token",
                    None,
                    _FakeDatabase(None),
                )

    def test_inactive_user_is_rejected(self):
        database = _FakeDatabase(
            SimpleNamespace(id="user-123", is_active=False),
        )

        with patch.object(
            chat,
            "decode_token",
            return_value={"type": "access", "sub": "user-123"},
        ):
            with self.assertRaisesRegex(chat.WebSocketAuthError, "Inactive user"):
                chat.authenticate_websocket_user(
                    "compass.v1, compass.jwt.signed-token",
                    None,
                    database,
                )


class WebSocketEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_query_credentials_are_closed_before_session_or_model_work(self):
        database = _FakeDatabase(None)
        websocket = SimpleNamespace(
            headers={
                "sec-websocket-protocol": (
                    "compass.v1, compass.jwt.header-token"
                ),
            },
            query_params={"token": "query-token"},
            close=AsyncMock(),
        )

        with (
            patch.object(chat, "SessionLocal", return_value=database),
            patch.object(chat.agent_runner, "run_agent_stream") as run_agent,
        ):
            await chat.websocket_chat(websocket, "session-123")

        websocket.close.assert_awaited_once_with(
            code=4001,
            reason="Query string credentials are not accepted",
        )
        self.assertEqual(database.queried_models, [])
        self.assertTrue(database.closed)
        run_agent.assert_not_called()


if __name__ == "__main__":
    unittest.main()
