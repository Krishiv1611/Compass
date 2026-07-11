"""
User settings router — get and update user preferences.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.auth.dependencies import get_current_user
from backend.db import get_db
from backend.models.user import User

router = APIRouter(prefix="/settings", tags=["settings"])


class UserPreferences(BaseModel):
    """User preferences schema."""

    theme: str = "dark"
    model: str = "google/gemma-4-31b-it:free"
    language: str = "en"

    model_config = {"extra": "allow"}


@router.get("", response_model=UserPreferences)
def get_settings(current_user: User = Depends(get_current_user)):
    """Return the current user's preferences."""
    prefs = getattr(current_user, "preferences", None) or {}
    return UserPreferences(**prefs)


@router.put("", response_model=UserPreferences)
def update_settings(
    body: UserPreferences,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the current user's preferences."""
    current_user.preferences = body.model_dump()
    db.commit()
    db.refresh(current_user)
    return UserPreferences(**current_user.preferences)
