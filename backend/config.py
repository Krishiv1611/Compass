from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_JWT_SECRETS = {
    "compass-dev-secret-change-me-in-production",
    "super-secret-default-key-please-change",
}


class Settings(BaseSettings):
    db_uri: str = Field(
        ...,
        validation_alias=AliasChoices("DB_URI", "db_uri"),
    )
    compass_cloud_mode: bool = Field(
        default=False,
        validation_alias=AliasChoices("COMPASS_CLOUD_MODE", "compass_cloud_mode"),
    )
    workspace_root: Path = Field(
        default_factory=lambda: Path.home() / ".compass" / "workspaces",
        validation_alias=AliasChoices("WORKSPACE_ROOT", "workspace_root"),
    )
    skills_root: Path = Field(
        default_factory=lambda: Path.home() / ".compass" / "skills",
        validation_alias=AliasChoices("SKILLS_ROOT", "skills_root"),
    )
    default_provider: str = Field(
        default="openrouter",
        validation_alias=AliasChoices("DEFAULT_PROVIDER", "default_provider"),
    )
    default_model: str = Field(
        default="google/gemma-4-31b-it:free",
        validation_alias=AliasChoices("DEFAULT_MODEL", "default_model"),
    )
    embedding_provider: str | None = Field(
        default=None,
        validation_alias=AliasChoices("EMBEDDING_PROVIDER", "embedding_provider"),
    )
    embedding_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("EMBEDDING_MODEL", "embedding_model"),
    )
    mcp_servers_file: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("MCP_SERVERS_FILE", "mcp_servers_file"),
    )

    # ── JWT ──────────────────────────────────────────────────
    jwt_secret: str = Field(
        default="compass-dev-secret-change-me-in-production",
        validation_alias=AliasChoices("JWT_SECRET", "jwt_secret"),
    )
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=15, env="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    refresh_token_expire_days: int = Field(default=7, env="REFRESH_TOKEN_EXPIRE_DAYS")

    # ── OAuth (optional — endpoints degrade gracefully if unset) ──
    google_client_id: str | None = Field(default=None, env="GOOGLE_CLIENT_ID")
    google_client_secret: str | None = Field(default=None, env="GOOGLE_CLIENT_SECRET")
    github_client_id: str | None = Field(default=None, env="GITHUB_CLIENT_ID")
    github_client_secret: str | None = Field(default=None, env="GITHUB_CLIENT_SECRET")
    credential_encryption_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "CREDENTIAL_ENCRYPTION_KEY", "credential_encryption_key"
        ),
    )
    secure_cookies: bool = Field(
        default=False,
        validation_alias=AliasChoices("SECURE_COOKIES", "secure_cookies"),
    )

    # ── CORS ─────────────────────────────────────────────────
    cors_origins: list[str] | str = Field(
        default=[
            "https://compass-web-ai.vercel.app",
            "http://localhost:5173", 
            "http://localhost:5174", 
            "http://localhost:5175", 
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
            "http://localhost:3000"
        ],
        alias="CORS_ORIGINS",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @field_validator(
        "credential_encryption_key",
        "embedding_provider",
        "embedding_model",
        "mcp_servers_file",
        mode="before",
    )
    @classmethod
    def blank_optional_value_is_unset(cls, value: Any) -> Any:
        return None if isinstance(value, str) and not value.strip() else value

    @model_validator(mode="after")
    def validate_cloud_security(self) -> "Settings":
        if not self.compass_cloud_mode:
            return self
        normalized_secret = self.jwt_secret.strip().lower()
        weak_secret = (
            self.jwt_secret in _INSECURE_JWT_SECRETS
            or len(self.jwt_secret) < 32
            or len(set(self.jwt_secret)) < 12
            or any(
                marker in normalized_secret
                for marker in ("password", "change-me", "changeme", "default-key")
            )
        )
        if weak_secret:
            raise ValueError(
                "JWT_SECRET must be a non-default secret of at least 32 characters in cloud mode"
            )
        if not self.credential_encryption_key:
            raise ValueError(
                "CREDENTIAL_ENCRYPTION_KEY is required and must be separate in cloud mode"
            )
        if self.credential_encryption_key == self.jwt_secret:
            raise ValueError(
                "CREDENTIAL_ENCRYPTION_KEY must be separate from JWT_SECRET"
            )
        try:
            Fernet(self.credential_encryption_key.encode("ascii"))
        except (ValueError, TypeError, UnicodeEncodeError) as exc:
            raise ValueError(
                "CREDENTIAL_ENCRYPTION_KEY must be a valid Fernet key"
            ) from exc
        if not self.secure_cookies:
            raise ValueError("SECURE_COOKIES must be true in cloud mode")
        return self

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def sqlalchemy_db_uri(self) -> str:
        # SQLAlchemy 2.0+ with psycopg3 prefers postgresql+psycopg://
        if self.db_uri.startswith("postgresql://"):
            return self.db_uri.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.db_uri


settings = Settings()
