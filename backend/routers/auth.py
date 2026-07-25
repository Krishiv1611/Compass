"""
Auth router â€” registration, login, token refresh, profile, OAuth.
"""

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.auth.jwt import (
    create_oauth_state,
    create_token_pair,
    decode_oauth_state,
    decode_token,
)
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
    BrowserTokenResponse,
    UserResponse,
)
from urllib.parse import urlencode

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

    return _browser_tokens(response, create_token_pair(user.id))


@router.post("/login", response_model=BrowserTokenResponse)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
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

    return _browser_tokens(response, create_token_pair(user.id))


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
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return _browser_tokens(response, create_token_pair(user.id))


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the current user's profile."""
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    """
    Logout (stateless).

    With stateless JWTs the server has nothing to invalidate.
    The client should discard its stored tokens.
    """
    response.delete_cookie("compass_refresh", path="/api/auth")
    return None


# â”€â”€ OAuth Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


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

    user = get_or_create_oauth_user(
        db,
        provider="google",
        provider_id=str(info["id"]),
        email=info["email"],
        display_name=info.get("name"),
        avatar_url=info.get("picture"),
    )
    return _browser_tokens(response, create_token_pair(user.id))


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
        access_token=info.get("_access_token"),
        scopes=info.get("_scopes"),
    )
    return _browser_tokens(response, create_token_pair(user.id))

