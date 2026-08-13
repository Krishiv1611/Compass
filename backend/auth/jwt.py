"""
JWT token creation and verification.

Access tokens (short-lived) and refresh tokens (long-lived).
"""

from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

from jose import JWTError, jwt

from backend.config import settings
from backend.schemas.auth import TokenResponse


def create_access_token(user_id: str) -> str:
    """Create a short-lived access token."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived refresh token."""
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT.

    Returns the payload dict on success.
    Raises JWTError on invalid/expired tokens.
    """
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def create_token_pair(user_id: str) -> TokenResponse:
    """Create both access and refresh tokens, returned as a TokenResponse."""
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
        expires_in=settings.access_token_expire_minutes * 60,
    )


def create_oauth_state(
    provider: str,
    *,
    redirect_uri: str = "",
    intent: str = "login",
    return_to: str = "/chat",
    user_id: str | None = None,
) -> str:
    """Create a short-lived signed OAuth state value owned by the backend."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=10)
    payload = {
        "type": "oauth_state",
        "provider": provider,
        "redirect_uri": redirect_uri,
        "intent": intent,
        "return_to": return_to if return_to.startswith("/") else "/chat",
        "nonce": token_urlsafe(24),
        "exp": expire,
    }
    if user_id:
        payload["user_id"] = user_id
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_oauth_state(
    state: str,
    expected_provider: str,
    *,
    expected_user_id: str | None = None,
) -> dict:
    """Validate a signed OAuth state and its intended provider."""
    payload = decode_token(state)
    if payload.get("type") != "oauth_state" or payload.get("provider") != expected_provider:
        raise JWTError("Invalid OAuth state")
    if expected_user_id is not None and payload.get("user_id") != expected_user_id:
        raise JWTError("OAuth state belongs to another user")
    return payload
