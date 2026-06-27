from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


# ── Requests ──────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """POST /auth/register"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str | None = Field(None, max_length=100)


class LoginRequest(BaseModel):
    """POST /auth/login"""
    email: EmailStr
    password: str


# ── Responses ─────────────────────────────────────────────

class TokenResponse(BaseModel):
    """Returned after login / register / refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(
        default=900, description="Access token lifetime in seconds"
    )


class UserResponse(BaseModel):
    """GET /auth/me and embedded in other responses."""
    id: str
    email: str
    display_name: str | None = None
    avatar_url: str | None = None
    oauth_provider: str | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
