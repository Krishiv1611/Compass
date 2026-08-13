import unittest

from backend.auth.credentials import decrypt_credential, encrypt_credential
from backend.services.provider_credentials import (
    remove_provider_credential,
    resolve_provider_config,
    store_provider_credential,
    validate_provider_model,
)
from backend.services.session_manager import deterministic_title


def encrypted_preferences(slots: dict[str, str], selected: str) -> dict:
    return {
        "llm_provider": selected,
        "model": {
            "openrouter": "google/gemma-4-31b-it:free",
            "openai": "gpt-4.1-mini",
            "anthropic": "claude-3-5-haiku-latest",
            "google": "gemini-2.0-flash",
        }.get(selected, "test-model"),
        "llm_credentials_encrypted": {
            provider: encrypt_credential(value)
            for provider, value in slots.items()
        },
    }


def decrypt_slots(preferences: dict) -> dict[str, str]:
    return {
        provider: decrypt_credential(ciphertext) or ""
        for provider, ciphertext in preferences.get(
            "llm_credentials_encrypted",
            {},
        ).items()
    }


class ProviderCredentialTests(unittest.TestCase):
    def test_openai_key_is_not_reused_for_openrouter(self):
        preferences = encrypted_preferences(
            {"openai": "sk-openai"},
            selected="openrouter",
        )
        with self.assertRaisesRegex(
            ValueError,
            "No credential stored for openrouter",
        ):
            resolve_provider_config(preferences)

    def test_delete_removes_only_selected_provider(self):
        preferences = encrypted_preferences(
            {"openai": "a", "anthropic": "b"},
            selected="openai",
        )
        result = remove_provider_credential(preferences, "openai")
        self.assertNotIn("openai", decrypt_slots(result))
        self.assertEqual(decrypt_slots(result)["anthropic"], "b")

    def test_store_updates_only_the_requested_provider(self):
        preferences = encrypted_preferences(
            {"openai": "old", "anthropic": "keep"},
            selected="openai",
        )
        result = store_provider_credential(preferences, "openai", "new")
        self.assertEqual(
            decrypt_slots(result),
            {"openai": "new", "anthropic": "keep"},
        )

    def test_unknown_provider_and_mismatched_model_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported provider"):
            validate_provider_model("groq", "llama")
        with self.assertRaisesRegex(ValueError, "not valid for provider openai"):
            validate_provider_model("openai", "claude-3-haiku")

    def test_embedding_requires_an_explicit_provider_credential(self):
        preferences = encrypted_preferences(
            {"openai": "chat-key"},
            selected="openai",
        )
        preferences["embedding_provider"] = "google"
        preferences["embedding_model"] = "text-embedding-004"

        with self.assertRaisesRegex(
            ValueError,
            "No embedding credential stored for google",
        ):
            resolve_provider_config(preferences)

    def test_no_embedding_selection_discloses_disabled_capability(self):
        preferences = encrypted_preferences(
            {"openai": "chat-key"},
            selected="openai",
        )
        resolved = resolve_provider_config(preferences)
        self.assertIsNone(resolved.embedding_provider)
        self.assertIsNone(resolved.embedding_api_key)

    def test_title_is_deterministic_and_bounded(self):
        title = deterministic_title(
            "  Please   refactor the entire workspace service without changing behavior today  "
        )
        self.assertEqual(
            title,
            "Please refactor the entire workspace service without changing",
        )
        self.assertLessEqual(len(title.split()), 8)
        self.assertLessEqual(len(title), 80)


if __name__ == "__main__":
    unittest.main()
