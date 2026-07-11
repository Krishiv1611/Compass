"""
Auth router — registration, login, token refresh, profile, OAuth.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from backend.auth.jwt import create_token_pair, decode_token
from backend.auth.passwords import hash_password, verify_password
from backend.auth.dependencies import get_current_user
from backend.auth.oauth import (
    exchange_google_code,
    exchange_github_code,
    get_or_create_oauth_user,
)
from backend.config import settings
from backend.db import get_db
from backend.models.user import User
from backend.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Create a new user account and return JWT tokens."""
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        display_name=body.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return create_token_pair(user.id)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate with email/password and return JWT tokens."""
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    return create_token_pair(user.id)


@router.post("/refresh", response_model=TokenResponse)
def refresh(token: str, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a new token pair."""
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is not a refresh token",
        )

    user_id = payload.get("sub", "")
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return create_token_pair(user.id)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the current user's profile."""
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout():
    """
    Logout (stateless).

    With stateless JWTs the server has nothing to invalidate.
    The client should discard its stored tokens.
    """
    return None


# ── OAuth Endpoints ──────────────────────────────────────────────────────────────


@router.get("/oauth/google/url")
def get_google_auth_url(redirect_uri: str):
    """Generate the Google OAuth authorization URL."""
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google OAuth is not configured on the backend (missing GOOGLE_CLIENT_ID)",
        )
    url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={settings.google_client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope=openid%20email%20profile&"
        f"state=google"
    )
    return {"url": url}


@router.get("/oauth/github/url")
def get_github_auth_url():
    """Generate the GitHub OAuth authorization URL."""
    if not settings.github_client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub OAuth is not configured on the backend (missing GITHUB_CLIENT_ID)",
        )
    url = (
        f"https://github.com/login/oauth/authorize?"
        f"client_id={settings.github_client_id}&"
        f"scope=user:email&"
        f"state=github"
    )
    return {"url": url}


@router.post("/oauth/google", response_model=TokenResponse)
async def oauth_google(code: str, redirect_uri: str, db: Session = Depends(get_db)):
    """Exchange a Google authorization code for JWT tokens."""
    try:
        info = await exchange_google_code(code, redirect_uri)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google OAuth failed: {exc}",
        )

    user = get_or_create_oauth_user(
        db,
        provider="google",
        provider_id=str(info["id"]),
        email=info["email"],
        display_name=info.get("name"),
        avatar_url=info.get("picture"),
    )
    return create_token_pair(user.id)


@router.post("/oauth/github", response_model=TokenResponse)
async def oauth_github(code: str, db: Session = Depends(get_db)):
    """Exchange a GitHub authorization code for JWT tokens."""
    try:
        info = await exchange_github_code(code)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GitHub OAuth failed: {exc}",
        )

    if not info.get("email"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub account has no public email. Please set a public email on GitHub.",
        )

    user = get_or_create_oauth_user(
        db,
        provider="github",
        provider_id=str(info["id"]),
        email=info["email"],
        display_name=info.get("name") or info.get("login"),
        avatar_url=info.get("avatar_url"),
    )
    return create_token_pair(user.id)
