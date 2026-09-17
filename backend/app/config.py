"""This module contains the configuration settings for the application."""

from typing import Annotated

from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    """Application configuration settings."""

    app_name: str = "Fitness Business OS"
    debug: bool = False

    database_url: str
    echo: bool = False

    # Clerk identity provider. All optional so the app boots without live keys;
    # requests are only authenticated once verification is configured.
    clerk_secret_key: str | None = None
    clerk_publishable_key: str | None = None
    clerk_jwks_url: str | None = None
    clerk_jwt_public_key: str | None = None
    clerk_issuer: str | None = None
    clerk_authorized_parties: Annotated[list[str], NoDecode] = []

    # Rate limiting. Falls back to in-process memory storage when Redis is unset.
    redis_url: str | None = None
    rate_limit_default: str = "100/minute"
    rate_limit_sensitive: str = "10/minute"

    log_level: str = "INFO"

    # CORS allowed origins for the browser frontend (comma-separated in env).
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    # Local development only: enables a dev token issuer at /auth/dev/login.
    # NEVER enable in production — it mints valid session tokens without Clerk.
    dev_auth_enabled: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value):
        """Accept common environment labels for local debug configuration."""
        if isinstance(value, str) and value.lower() in {"release", "prod", "production"}:
            return False
        return value

    @field_validator("clerk_authorized_parties", "cors_origins", mode="before")
    @classmethod
    def split_csv(cls, value):
        """Accept a comma-separated list from the environment."""
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("clerk_jwt_public_key", mode="before")
    @classmethod
    def normalize_public_key(cls, value):
        """Restore PEM newlines when the key is supplied as a single-line env var."""
        if isinstance(value, str) and "\\n" in value:
            return value.replace("\\n", "\n")
        return value


settings = Settings()
