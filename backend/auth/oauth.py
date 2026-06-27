"""
OAuth2 helpers for Google and GitHub login.

Each provider flow:
  1. Frontend redirects user to provider's consent screen.
  2. Provider redirects back with an authorization `code`.
  3. Backend exchanges `code` for user info.
  4. Backend upserts a User row and returns JWT tokens.
"""

import httpx
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.user import User


async def exchange_google_code(code: str, redirect_uri: str) -> dict:
    """Exchange a Google OAuth2 authorization code for user info."""
    if not settings.google_client_id or not settings.google_client_secret:
        raise ValueError("Google OAuth is not configured (missing GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET)")

    async with httpx.AsyncClient() as client:
        # Exchange code for tokens
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        tokens = token_resp.json()

        # Fetch user info
        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        userinfo_resp.raise_for_status()
        return userinfo_resp.json()


async def exchange_github_code(code: str) -> dict:
    """Exchange a GitHub OAuth2 authorization code for user info."""
    if not settings.github_client_id or not settings.github_client_secret:
        raise ValueError("GitHub OAuth is not configured (missing GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET)")

    async with httpx.AsyncClient() as client:
        # Exchange code for access token
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
            },
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        # Fetch user profile
        user_resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_resp.raise_for_status()
        profile = user_resp.json()

        # Fetch primary email (may not be public)
        email_resp = await client.get(
            "https://api.github.com/user/emails",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        email_resp.raise_for_status()
        emails = email_resp.json()
        primary = next((e for e in emails if e.get("primary")), emails[0] if emails else None)
        profile["email"] = primary["email"] if primary else None

        return profile


def get_or_create_oauth_user(
    db: Session,
    *,
    provider: str,
    provider_id: str,
    email: str,
    display_name: str | None = None,
    avatar_url: str | None = None,
) -> User:
    """
    Find an existing user by OAuth provider ID, or create a new one.

    If a user with the same email already exists (e.g. registered via password),
    link the OAuth provider to that account.
    """
    # 1. Try to find by provider + provider_id
    user = (
        db.query(User)
        .filter(User.oauth_provider == provider, User.oauth_provider_id == provider_id)
        .first()
    )
    if user:
        return user

    # 2. Try to find by email (link OAuth to existing email-based account)
    user = db.query(User).filter(User.email == email).first()
    if user:
        user.oauth_provider = provider
        user.oauth_provider_id = provider_id
        if avatar_url and not user.avatar_url:
            user.avatar_url = avatar_url
        db.commit()
        db.refresh(user)
        return user

    # 3. Create new user
    user = User(
        email=email,
        display_name=display_name,
        avatar_url=avatar_url,
        oauth_provider=provider,
        oauth_provider_id=provider_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
