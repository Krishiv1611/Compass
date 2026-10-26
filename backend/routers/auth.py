"""
Auth router — registration, login, token refresh, profile, OAuth.
"""

from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.orm import Session

from backend.auth.dependencies import get_current_user
from backend.auth.jwt import (
    create_oauth_state,
    create_token_pair,
    decode_oauth_state,
    decode_token,
)
from backend.auth.oauth import (
    exchange_github_code,
    exchange_google_code,
    get_or_create_oauth_user,
    normalize_email,
)
from backend.auth.passwords import hash_password, verify_password
from backend.config import settings
from backend.db import get_db
from backend.models.user import User
from backend.schemas.auth import (
    BrowserTokenResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)


class RefreshRequest(BaseModel):
    """Refresh token request body."""
    token: str | None = None


router = APIRouter(prefix="/auth", tags=["auth"])


def _browser_tokens(response: Response, pair: TokenResponse) -> BrowserTokenResponse:
    response.set_cookie(
        "compass_refresh",
        pair.refresh_token,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/api/auth",
    )
    return BrowserTokenResponse(
        access_token=pair.access_token,
        expires_in=pair.expires_in,
    )


@router.post(
    "/register", response_model=BrowserTokenResponse, status_code=status.HTTP_201_CREATED
)
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    """Create a new user account and return JWT tokens."""
    email = normalize_email(body.email)
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=email,
        hashed_password=hash_password(body.password),
        display_name=body.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return _browser_tokens(response, create_token_pair(user.id, user.refresh_version))


@router.post("/login", response_model=BrowserTokenResponse)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """Authenticate with email/password and return JWT tokens."""
    user = db.query(User).filter(User.email == normalize_email(body.email)).first()
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

    return _browser_tokens(response, create_token_pair(user.id, user.refresh_version))


@router.post("/refresh", response_model=BrowserTokenResponse)
def refresh(
    response: Response,
    body: RefreshRequest | None = None,
    compass_refresh: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    """Exchange a valid refresh token for a new token pair."""
    try:
        payload = decode_token(compass_refresh or (body.token if body else ""))
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
    refresh_version = payload.get("rv")
    next_refresh_version = db.execute(
        update(User)
        .where(
            User.id == user_id,
            User.is_active.is_(True),
            User.refresh_version == refresh_version,
        )
        .values(refresh_version=User.refresh_version + 1)
        .returning(User.refresh_version)
    ).scalar_one_or_none()
    if next_refresh_version is None:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked, expired, or belongs to an inactive user",
        )

    db.commit()
    return _browser_tokens(response, create_token_pair(user_id, next_refresh_version))


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the current user's profile."""
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke the current refresh-token generation and clear the browser cookie."""
    db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(refresh_version=User.refresh_version + 1)
    )
    db.commit()
    response.delete_cookie("compass_refresh", path="/api/auth")


# ── OAuth Endpoints ──────────────────────────────────────────────────────────────


@router.get("/oauth/google/url")
def get_google_auth_url(
    redirect_uri: str,
    intent: str = "login",
    return_to: str = "/chat",
):
    """Generate the Google OAuth authorization URL."""
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google OAuth is not configured on the backend (missing GOOGLE_CLIENT_ID)",
        )
    oauth_state = create_oauth_state(
        "google", redirect_uri=redirect_uri, intent=intent, return_to=return_to
    )
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": oauth_state,
        }
    )
    return {"url": url}


@router.get("/oauth/github/url")
def get_github_auth_url(intent: str = "login", return_to: str = "/chat"):
    """Generate the GitHub OAuth authorization URL."""
    if not settings.github_client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub OAuth is not configured on the backend (missing GITHUB_CLIENT_ID)",
        )
    oauth_state = create_oauth_state(
        "github", intent=intent, return_to=return_to
    )
    url = "https://github.com/login/oauth/authorize?" + urlencode(
        {
            "client_id": settings.github_client_id,
            "scope": "read:user user:email repo",
            "state": oauth_state,
        }
    )
    return {"url": url}


@router.post("/oauth/google", response_model=BrowserTokenResponse)
async def oauth_google(
    code: str,
    redirect_uri: str,
    state: str,
    response: Response,
    db: Session = Depends(get_db),
):
    """Exchange a Google authorization code for JWT tokens."""
    try:
        state_payload = decode_oauth_state(state, "google")
        if state_payload.get("redirect_uri") != redirect_uri:
            raise JWTError("OAuth redirect URI does not match state")
        info = await exchange_google_code(code, redirect_uri)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google OAuth failed: {exc}",
        )

    if not info.get("email") or not info.get("verified_email"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account must provide a verified email address",
        )

    user = get_or_create_oauth_user(
        db,
        provider="google",
        provider_id=str(info["id"]),
        email=info["email"],
        email_verified=bool(info.get("verified_email")),
        display_name=info.get("name"),
        avatar_url=info.get("picture"),
    )
    return _browser_tokens(response, create_token_pair(user.id, user.refresh_version))


@router.post("/oauth/github", response_model=BrowserTokenResponse)
async def oauth_github(code: str, state: str, response: Response, db: Session = Depends(get_db)):
    """Exchange a GitHub authorization code for JWT tokens."""
    try:
        decode_oauth_state(state, "github")
        info = await exchange_github_code(code)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GitHub OAuth failed: {exc}",
        )

    if not info.get("email") or not info.get("email_verified"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub account must provide a verified email address.",
        )

    user = get_or_create_oauth_user(
        db,
        provider="github",
        provider_id=str(info["id"]),
        email=info["email"],
        email_verified=bool(info.get("email_verified")),
        display_name=info.get("name") or info.get("login"),
        avatar_url=info.get("avatar_url"),
    )
    return _browser_tokens(response, create_token_pair(user.id, user.refresh_version))

