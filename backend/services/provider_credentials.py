"""Provider-bound BYOK credential storage and resolution."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from backend.auth.credentials import decrypt_credential, encrypt_credential

VALID_PROVIDERS = frozenset({"openrouter", "openai", "anthropic", "google", "litellm"})
EMBEDDING_PROVIDERS = frozenset({"openrouter", "openai", "google", "litellm"})


@dataclass(frozen=True, slots=True)
class ResolvedProviderConfig:
    provider: str
    model: str
    api_key: str
    embedding_provider: str | None = None
    embedding_model: str | None = None
    embedding_api_key: str | None = None

    def to_config(self) -> dict[str, str | None]:
        return {
            "provider": self.provider,
            "model": self.model,
            "api_key": self.api_key,
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model,
            "embedding_api_key": self.embedding_api_key,
        }


def validate_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized not in VALID_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")
    return normalized


def validate_provider_model(provider: str, model: str) -> tuple[str, str]:
    normalized = validate_provider(provider)
    model_name = model.strip()
    if not model_name:
        raise ValueError("Model is required")

    unqualified = model_name.split("/", 1)[-1]
    valid = {
        "openrouter": "/" in model_name,
        "openai": unqualified.startswith(("gpt-", "o1", "o3", "o4")),
        "anthropic": unqualified.startswith("claude-"),
        "google": unqualified.startswith(("gemini-", "gemma-")),
        "litellm": True,
    }[normalized]
    if not valid:
        raise ValueError(
            f"Model {model_name!r} is not valid for provider {normalized}"
        )
    return normalized, model_name


def _credential_slots(preferences: dict) -> dict[str, str]:
    slots = preferences.get("llm_credentials_encrypted") or {}
    return {
        str(provider): str(ciphertext)
        for provider, ciphertext in slots.items()
        if provider in VALID_PROVIDERS and ciphertext
    }


def migrate_legacy_credential(preferences: dict) -> dict:
    """Bind the old single slot to its recorded provider without reusing it."""
    result = deepcopy(preferences)
    legacy = result.pop("llm_api_key_encrypted", None)
    if legacy:
        provider = result.get("llm_provider")
        if provider in VALID_PROVIDERS:
            slots = _credential_slots(result)
            slots.setdefault(provider, legacy)
            result["llm_credentials_encrypted"] = slots
    return result


def store_provider_credential(
    preferences: dict,
    provider: str,
    api_key: str,
) -> dict:
    normalized = validate_provider(provider)
    value = api_key.strip()
    if not value:
        raise ValueError("Provider credential cannot be empty")
    result = migrate_legacy_credential(preferences)
    slots = _credential_slots(result)
    slots[normalized] = encrypt_credential(value)
    result["llm_credentials_encrypted"] = slots
    return result


def remove_provider_credential(preferences: dict, provider: str) -> dict:
    normalized = validate_provider(provider)
    result = migrate_legacy_credential(preferences)
    slots = _credential_slots(result)
    slots.pop(normalized, None)
    result["llm_credentials_encrypted"] = slots
    return result


def resolve_provider_config(preferences: dict) -> ResolvedProviderConfig:
    migrated = migrate_legacy_credential(preferences)
    provider, model = validate_provider_model(
        str(migrated.get("llm_provider") or "openrouter"),
        str(migrated.get("model") or ""),
    )
    slots = _credential_slots(migrated)
    encrypted_key = slots.get(provider)
    if not encrypted_key:
        raise ValueError(f"No credential stored for {provider}")
    api_key = decrypt_credential(encrypted_key)
    if not api_key:
        raise ValueError(f"No credential stored for {provider}")

    embedding_provider_value = migrated.get("embedding_provider")
    if not embedding_provider_value:
        return ResolvedProviderConfig(provider=provider, model=model, api_key=api_key)

    embedding_provider = validate_provider(str(embedding_provider_value))
    if embedding_provider not in EMBEDDING_PROVIDERS:
        raise ValueError(
            f"Embedding provider {embedding_provider!r} is not supported"
        )
    embedding_model = str(migrated.get("embedding_model") or "").strip()
    if not embedding_model:
        raise ValueError("Embedding model is required")
    embedding_ciphertext = slots.get(embedding_provider)
    if not embedding_ciphertext:
        raise ValueError(
            f"No embedding credential stored for {embedding_provider}"
        )
    embedding_api_key = decrypt_credential(embedding_ciphertext)
    if not embedding_api_key:
        raise ValueError(
            f"No embedding credential stored for {embedding_provider}"
        )
    return ResolvedProviderConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        embedding_api_key=embedding_api_key,
    )
