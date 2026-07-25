"""Encryption helpers for provider credentials stored by the backend."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from backend.config import settings


def _fernet() -> Fernet:
    configured = settings.credential_encryption_key
    if configured:
        try:
            return Fernet(configured.encode("ascii"))
        except (ValueError, TypeError) as exc:
            raise RuntimeError(
                "CREDENTIAL_ENCRYPTION_KEY must be a valid Fernet key"
            ) from exc

    # Development compatibility. Production deployments should provide a
    # separately rotated CREDENTIAL_ENCRYPTION_KEY.
    derived = hashlib.sha256(settings.jwt_secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_credential(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_credential(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Stored provider credential cannot be decrypted") from exc
