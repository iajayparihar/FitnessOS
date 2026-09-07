from __future__ import annotations

from typing import Any

import jwt
from jwt import InvalidTokenError, PyJWKClient

from app.config import settings
from app.integrations.clerk.exceptions import (
    ClerkAuthenticationError,
    ClerkConfigurationError,
)


class ClerkClient:
    """Validate Clerk-issued JWTs using the configured public key or JWKS."""

    def verify_session_token(self, token: str) -> dict[str, Any]:
        if not token or not str(token).strip():
            raise ClerkAuthenticationError("Missing Clerk session token.")

        if not settings.clerk_issuer:
            raise ClerkConfigurationError(
                "Clerk issuer is not configured. Set CLERK_ISSUER."
            )

        if not settings.clerk_authorized_parties:
            raise ClerkConfigurationError(
                "Clerk authorized parties are not configured. Set CLERK_AUTHORIZED_PARTIES."
            )

        if settings.clerk_jwt_key:
            public_key = settings.clerk_jwt_key
            try:
                return jwt.decode(
                    token,
                    key=public_key,
                    algorithms=["RS256"],
                    options={"require": ["exp", "sub"]},
                    issuer=settings.clerk_issuer,
                    audience=settings.clerk_authorized_parties,
                )
            except InvalidTokenError as exc:
                raise ClerkAuthenticationError("Invalid Clerk token.") from exc

        if not settings.clerk_jwks_url:
            raise ClerkConfigurationError(
                "Clerk is not configured. Set CLERK_JWT_KEY or CLERK_JWKS_URL."
            )

        try:
            signing_key = PyJWKClient(settings.clerk_jwks_url).get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                key=signing_key.key,
                algorithms=[signing_key.algorithm],
                options={"require": ["exp", "sub"]},
                issuer=settings.clerk_issuer,
                audience=settings.clerk_authorized_parties,
            )
        except InvalidTokenError as exc:
            raise ClerkAuthenticationError("Invalid Clerk token.") from exc
        except Exception as exc:  # pragma: no cover - defensive guard for JWKS/network issues.
            raise ClerkAuthenticationError(
                "Clerk token validation is unavailable right now."
            ) from exc


clerk_client = ClerkClient()
