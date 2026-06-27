from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    db_uri: str = Field(..., env="DB_URI")

    # ── JWT ──────────────────────────────────────────────────
    jwt_secret: str = Field(
        default="compass-dev-secret-change-me-in-production",
        env="JWT_SECRET",
    )
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=15, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, env="REFRESH_TOKEN_EXPIRE_DAYS")

    # ── OAuth (optional — endpoints degrade gracefully if unset) ──
    google_client_id: str | None = Field(default=None, env="GOOGLE_CLIENT_ID")
    google_client_secret: str | None = Field(default=None, env="GOOGLE_CLIENT_SECRET")
    github_client_id: str | None = Field(default=None, env="GITHUB_CLIENT_ID")
    github_client_secret: str | None = Field(default=None, env="GITHUB_CLIENT_SECRET")

    # ── CORS ─────────────────────────────────────────────────
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        env="CORS_ORIGINS",
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def sqlalchemy_db_uri(self) -> str:
        # SQLAlchemy 2.0+ with psycopg3 prefers postgresql+psycopg://
        if self.db_uri.startswith("postgresql://"):
            return self.db_uri.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.db_uri


settings = Settings()
