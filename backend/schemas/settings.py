"""Public settings request and response schemas."""

from pydantic import BaseModel, Field

from backend.services.provider_credentials import VALID_PROVIDERS


class UserPreferences(BaseModel):
    theme: str = "dark"
    model: str = "google/gemma-4-31b-it:free"
    llm_provider: str = "openrouter"
    language: str = "en"
    safe_mode: bool = False
    fast_mode: bool = False
    has_llm_api_key: bool = False
    credential_providers: list[str] = Field(default_factory=list)
    model_config = {"extra": "ignore"}


class UserPreferencesUpdate(BaseModel):
    theme: str = "dark"
    model: str = "google/gemma-4-31b-it:free"
    llm_provider: str = "openrouter"
    llm_api_key: str | None = None
    language: str = "en"
    safe_mode: bool = False
    fast_mode: bool = False


class ProviderTestRequest(BaseModel):
    provider: str
    model: str
    api_key: str | None = None


class ProviderTestResponse(BaseModel):
    provider: str
    model: str
    success: bool
    latency_ms: float
    error: str | None = None


def public_preferences(preferences: dict) -> UserPreferences:
    slots = preferences.get("llm_credentials_encrypted") or {}
    providers = sorted(provider for provider in slots if provider in VALID_PROVIDERS)
    selected = str(preferences.get("llm_provider") or "openrouter")
    return UserPreferences(
        **preferences,
        credential_providers=providers,
        has_llm_api_key=selected in providers,
    )
