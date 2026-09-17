"""Development-only token issuer.

Mints RS256 tokens signed by a locally generated key so the app can be exercised
without a live Clerk account. Verification goes through the normal Clerk path
(``verify_clerk_token``) — this only stands in for Clerk's *signing* side. Gated
behind ``settings.dev_auth_enabled`` and must never be enabled in production.

"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

_private_pem: str | None = None
_public_pem: str | None = None


def _ensure_keys() -> tuple[str, str]:
    global _private_pem, _public_pem
    if _private_pem is None:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        _private_pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()
        _public_pem = (
            key.public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode()
        )
    return _private_pem, _public_pem


def dev_public_key() -> str:
    """Return the PEM public key used to verify dev-issued tokens."""
    return _ensure_keys()[1]


def mint_dev_token(
    *,
    email: str,
    first_name: str | None = None,
    last_name: str | None = None,
) -> str:
    """Mint a Clerk-shaped session token for local testing.

    ``sub`` is derived deterministically from the email so the same address maps
    to the same provisioned user across logins.

    """
    private_pem, _ = _ensure_keys()
    normalized = email.strip().lower()
    sub = "dev_" + hashlib.sha256(normalized.encode()).hexdigest()[:24]
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": sub,
            "email": normalized,
            "first_name": first_name,
            "last_name": last_name,
            "iat": now,
            "exp": now + timedelta(hours=12),
        },
        private_pem,
        algorithm="RS256",
    )
