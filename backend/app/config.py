"""This module contains the configuration settings for the application."""

from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""

    app_name: str = "Fitness Business OS"
    debug: bool = False

    database_url: str
    echo: bool = False

    # Legacy password/session authentication. Clerk is the authentication
    # authority; this flag only exists to keep a migration escape hatch open and
    # defaults to off so the legacy path cannot be reached accidentally.
    legacy_password_auth_enabled: bool = False
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30

    clerk_secret_key: str = ""
    clerk_publishable_key: str = ""
    clerk_jwks_url: str | None = None
    clerk_jwt_key: str | None = None
    clerk_issuer: str | None = None
    # NoDecode keeps pydantic-settings from JSON-parsing the environment value,
    # so the documented comma-separated form reaches the validator below.
    clerk_authorized_parties: Annotated[list[str], NoDecode] = Field(
        default_factory=list
    )
    clerk_jwt_leeway_seconds: int = 5
    # Controlled one-way migration switch: link a first-time Clerk identity to an
    # existing local user that shares its verified email address. Off by default
    # because email is not a trustworthy permanent identity key.
    clerk_link_existing_users_by_email: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value):
        """Accept common environment labels for local debug configuration."""
        if isinstance(value, str) and value.lower() in {
            "release",
            "prod",
            "production",
        }:
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
