from __future__ import annotations

import jwt
from jwt import PyJWKClient

from app.config import settings


class ClerkAuthError(Exception):
    """Raised when a Clerk session token is missing, invalid, or expired."""


_jwks_client: PyJWKClient | None = None


def _signing_key(token: str) -> str:
    """Resolve the RS256 verification key from a configured PEM or Clerk JWKS."""
    if settings.clerk_jwt_public_key:
        return settings.clerk_jwt_public_key
    if settings.clerk_jwks_url:
        global _jwks_client
        if _jwks_client is None:
            _jwks_client = PyJWKClient(settings.clerk_jwks_url)
        return _jwks_client.get_signing_key_from_jwt(token).key
    raise ClerkAuthError("Clerk verification is not configured.")


def verify_clerk_token(token: str) -> dict:
    """Verify a Clerk session JWT and return its claims.

    Validates the RS256 signature, expiry, issuer (when configured), and the
    authorized party (``azp``) claim. Raises :class:`ClerkAuthError` on any
    failure.

    """
    try:
        claims = jwt.decode(
            token,
            _signing_key(token),
            algorithms=["RS256"],
            issuer=settings.clerk_issuer or None,
            options={"require": ["exp", "sub"], "verify_aud": False},
        )
    except ClerkAuthError:
        raise
    except jwt.PyJWTError as exc:
        raise ClerkAuthError(str(exc)) from exc

    authorized_parties = settings.clerk_authorized_parties
    if authorized_parties and claims.get("azp") not in authorized_parties:
        raise ClerkAuthError("Unauthorized party.")

    return claims
