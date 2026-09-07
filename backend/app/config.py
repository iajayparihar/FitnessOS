"""This module contains the configuration settings for the application."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    """Application configuration settings."""

    app_name: str = "Fitness Business OS"
    debug: bool = False

    database_url: str
    echo: bool = False
    jwt_secret_key: str = "change-this-local-development-secret"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30
    clerk_secret_key: str = ""
    clerk_publishable_key: str = ""
    clerk_jwks_url: str | None = None
    clerk_jwt_key: str | None = None
    clerk_issuer: str | None = None
    clerk_authorized_parties: list[str] = []
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

    @field_validator("clerk_authorized_parties", mode="before")
    @classmethod
    def parse_clerk_authorized_parties(cls, value):
        """Normalize the comma-delimited Clerk authorized parties setting."""
        if value in (None, ""):
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


settings = Settings()
