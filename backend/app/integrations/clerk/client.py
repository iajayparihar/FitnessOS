from __future__ import annotations

import threading
from typing import Any

import jwt
from jwt import InvalidTokenError, PyJWKClient

from app.config import settings
from app.integrations.clerk.exceptions import (
    ClerkAuthenticationError,
    ClerkConfigurationError,
)

# Clerk signs session tokens with RS256. Pinning the algorithm prevents an
# attacker from downgrading verification to a symmetric algorithm.
CLERK_SIGNING_ALGORITHMS = ["RS256"]

# `azp` (authorized party) is the claim Clerk uses to identify the frontend
# origin that requested the token; it is validated against
# CLERK_AUTHORIZED_PARTIES rather than through JWT audience validation, because
# Clerk session tokens do not carry an `aud` claim.
REQUIRED_CLAIMS = ["exp", "iat", "sub", "azp"]

JWKS_CACHE_LIFESPAN_SECONDS = 3600

_jwks_clients: dict[str, PyJWKClient] = {}
_jwks_lock = threading.Lock()


def _get_jwks_client(jwks_url: str) -> PyJWKClient:
    """Return a process-wide JWKS client so keys are fetched once, not per request."""
    client = _jwks_clients.get(jwks_url)
    if client is not None:
        return client

    with _jwks_lock:
        client = _jwks_clients.get(jwks_url)
        if client is None:
            client = PyJWKClient(
                jwks_url,
                cache_keys=True,
                lifespan=JWKS_CACHE_LIFESPAN_SECONDS,
            )
            _jwks_clients[jwks_url] = client
        return client


def reset_jwks_cache() -> None:
    """Drop cached JWKS clients; used by tests and key-rotation tooling."""
    with _jwks_lock:
        _jwks_clients.clear()


class ClerkClient:
    """Validate Clerk-issued session tokens without calling the Clerk API."""

    def verify_session_token(self, token: str) -> dict[str, Any]:
        """
        Verify a Clerk session token and return its claims.

        Raises ClerkConfigurationError when the integration is not configured and
        ClerkAuthenticationError when the token is missing, malformed, expired,
        wrongly issued, or presented by an unauthorized party.
        """
        if not token or not str(token).strip():
            raise ClerkAuthenticationError("Missing Clerk session token.")

        issuer = (settings.clerk_issuer or "").strip()
        if not issuer:
            raise ClerkConfigurationError(
                "Clerk issuer is not configured. Set CLERK_ISSUER."
            )

        if not settings.clerk_authorized_parties:
            raise ClerkConfigurationError(
                "Clerk authorized parties are not configured. "
                "Set CLERK_AUTHORIZED_PARTIES."
            )

        claims = self._decode(token, issuer=issuer)
        self._verify_authorized_party(claims)
        return claims

    def _decode(self, token: str, *, issuer: str) -> dict[str, Any]:
        """Verify the token signature and registered claims against Clerk's key."""
        key = self._resolve_signing_key(token)
        try:
            return jwt.decode(
                token,
                key=key,
                algorithms=CLERK_SIGNING_ALGORITHMS,
                issuer=issuer,
                leeway=settings.clerk_jwt_leeway_seconds,
                options={
                    "require": REQUIRED_CLAIMS,
                    # Clerk session tokens carry no `aud`; the authorized party is
                    # checked separately against CLERK_AUTHORIZED_PARTIES.
                    "verify_aud": False,
                },
            )
        except InvalidTokenError as exc:
            raise ClerkAuthenticationError("Invalid Clerk token.") from exc

    def _resolve_signing_key(self, token: str) -> Any:
        """Return the configured public key, or the JWKS key matching the token kid."""
        if settings.clerk_jwt_key:
            return settings.clerk_jwt_key

        if not settings.clerk_jwks_url:
            raise ClerkConfigurationError(
                "Clerk is not configured. Set CLERK_JWT_KEY or CLERK_JWKS_URL."
            )

        try:
            signing_key = _get_jwks_client(
                settings.clerk_jwks_url
            ).get_signing_key_from_jwt(token)
        except InvalidTokenError as exc:
            raise ClerkAuthenticationError("Invalid Clerk token.") from exc
        except Exception as exc:  # pragma: no cover - JWKS transport failures.
            raise ClerkAuthenticationError(
                "Clerk token validation is unavailable right now."
            ) from exc
        return signing_key.key

    def _verify_authorized_party(self, claims: dict[str, Any]) -> None:
        """Reject tokens minted for a frontend origin this backend does not serve."""
        authorized_party = claims.get("azp")
        if authorized_party not in settings.clerk_authorized_parties:
            raise ClerkAuthenticationError(
                "Clerk token was issued to an unauthorized party."
            )


clerk_client = ClerkClient()
