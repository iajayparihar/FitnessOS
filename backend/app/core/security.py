from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config import settings

PBKDF2_ITERATIONS = 260_000


class TokenExpired(ValueError):
    """Raised when a JWT is valid but past its expiration time."""


def _raise_if_missing_jwt_secret() -> str:
    """Require a non-empty JWT secret to prevent insecure default config."""
    secret = (settings.jwt_secret_key or "").strip()
    if not secret:
        raise ValueError("JWT secret is not configured. Set JWT_SECRET_KEY.")
    return secret


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _json_dumps(value: dict[str, Any]) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _normalize_claims(payload: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, uuid.UUID):
            normalized[key] = str(value)
        elif isinstance(value, datetime):
            normalized[key] = int(value.timestamp())
        else:
            normalized[key] = value
    return normalized


def encode_jwt(payload: dict[str, Any]) -> str:
    """Sign a JWT using the configured HMAC secret."""
    if settings.jwt_algorithm != "HS256":
        raise ValueError("Only HS256 JWT signing is supported by this baseline.")

    secret = _raise_if_missing_jwt_secret()
    header = {"alg": settings.jwt_algorithm, "typ": "JWT"}
    encoded_header = _base64url_encode(_json_dumps(header))
    encoded_payload = _base64url_encode(_json_dumps(_normalize_claims(payload)))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(
        secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    return f"{encoded_header}.{encoded_payload}.{_base64url_encode(signature)}"


def decode_jwt(token: str) -> dict[str, Any]:
    """Verify and decode a JWT, raising ValueError for invalid tokens."""
    secret = _raise_if_missing_jwt_secret()
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
    except ValueError as exc:
        raise ValueError("Invalid token format.") from exc

    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    actual_signature = _base64url_decode(encoded_signature)
    if not hmac.compare_digest(actual_signature, expected_signature):
        raise ValueError("Invalid token signature.")

    payload = json.loads(_base64url_decode(encoded_payload))
    expires_at = payload.get("exp")
    if expires_at is not None and datetime.now(UTC).timestamp() >= expires_at:
        raise TokenExpired("Token has expired.")

    return payload


def create_access_token(
    *,
    subject: uuid.UUID,
    organization_id: uuid.UUID | None,
    is_superuser: bool,
    session_id: uuid.UUID,
) -> str:
    """Create a short-lived access token for a user."""
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    return encode_jwt(
        {
            "sub": subject,
            "sid": session_id,
            "organization_id": organization_id,
            "is_superuser": is_superuser,
            "iat": now,
            "exp": expires_at,
            "type": "access",
        }
    )


def create_refresh_token() -> str:
    """Create an opaque refresh token."""
    return secrets.token_urlsafe(48)


def hash_secret(value: str) -> str:
    """Hash an opaque secret for database storage."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    """Hash a password with PBKDF2-SHA256."""
    salt = secrets.token_urlsafe(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${_base64url_encode(digest)}"


def verify_password(password: str, password_hash: str | None) -> bool:
    """Verify a password against a stored PBKDF2-SHA256 hash."""
    if not password_hash:
        return False

    try:
        algorithm, iterations, salt, expected_digest = password_hash.split("$", 3)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        int(iterations),
    )
    return hmac.compare_digest(_base64url_encode(digest), expected_digest)
