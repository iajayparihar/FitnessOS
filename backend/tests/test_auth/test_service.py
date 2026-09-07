import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.config import settings
from app.core.security import (
    TokenExpired,
    create_access_token,
    decode_jwt,
    encode_jwt,
    hash_password,
    verify_password,
)
from app.integrations.clerk.client import ClerkClient
from app.integrations.clerk.exceptions import ClerkAuthenticationError, ClerkConfigurationError
from app.modules.auth.dependencies import get_current_user


@pytest.fixture(autouse=True)
def configure_runtime_settings(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret_key", "test-secret-key-for-auth-tests")
    monkeypatch.setattr(settings, "clerk_jwt_key", None)
    monkeypatch.setattr(settings, "clerk_jwks_url", None)
    monkeypatch.setattr(settings, "clerk_issuer", "https://example.clerk.accounts.dev")
    monkeypatch.setattr(settings, "clerk_authorized_parties", ["https://example.com"])


def test_password_hash_round_trip():
    password_hash = hash_password("correct horse battery staple")

    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong password", password_hash)


def test_access_token_round_trip():
    user_id = uuid.uuid4()
    organization_id = uuid.uuid4()

    token = create_access_token(
        subject=user_id,
        organization_id=organization_id,
        is_superuser=False,
        session_id=uuid.uuid4(),
    )
    payload = decode_jwt(token)

    assert payload["sub"] == str(user_id)
    assert payload["organization_id"] == str(organization_id)
    assert "sid" in payload
    assert payload["type"] == "access"


def test_decode_jwt_rejects_tampered_signature():
    token = create_access_token(
        subject=uuid.uuid4(),
        organization_id=None,
        is_superuser=False,
        session_id=uuid.uuid4(),
    )
    header, payload, signature = token.split(".")

    with pytest.raises(ValueError):
        decode_jwt(f"{header}.{payload}.{signature[:-2]}xx")


def test_decode_jwt_rejects_expired_token_with_specific_error():
    token = encode_jwt(
        {
            "sub": uuid.uuid4(),
            "sid": uuid.uuid4(),
            "type": "access",
            "iat": datetime.now(UTC) - timedelta(minutes=30),
            "exp": datetime.now(UTC) - timedelta(minutes=15),
        }
    )

    with pytest.raises(TokenExpired):
        decode_jwt(token)


def test_get_current_user_reports_expired_access_token():
    token = encode_jwt(
        {
            "sub": uuid.uuid4(),
            "sid": uuid.uuid4(),
            "type": "access",
            "iat": datetime.now(UTC) - timedelta(minutes=30),
            "exp": datetime.now(UTC) - timedelta(minutes=15),
        }
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(HTTPException) as exc:
        import asyncio

        asyncio.run(get_current_user(credentials=credentials, db=None))

    assert exc.value.status_code == 401
    assert exc.value.detail == "Access token has expired."


def test_create_access_token_requires_configured_secret(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret_key", "")

    with pytest.raises(ValueError, match="JWT secret is not configured"):
        create_access_token(
            subject=uuid.uuid4(),
            organization_id=None,
            is_superuser=False,
            session_id=uuid.uuid4(),
        )


def test_clerk_client_requires_configured_authorized_parties(monkeypatch):
    monkeypatch.setattr(settings, "clerk_issuer", "https://example.clerk.accounts.dev")
    monkeypatch.setattr(settings, "clerk_authorized_parties", [])
    monkeypatch.setattr(settings, "clerk_jwks_url", None)
    monkeypatch.setattr(settings, "clerk_jwt_key", None)

    with pytest.raises(ClerkConfigurationError, match="authorized parties"):
        ClerkClient().verify_session_token("token")


def test_clerk_client_rejects_malformed_token(monkeypatch):
    monkeypatch.setattr(settings, "clerk_issuer", "https://example.clerk.accounts.dev")
    monkeypatch.setattr(settings, "clerk_authorized_parties", ["https://example.com"])
    monkeypatch.setattr(settings, "clerk_jwt_key", "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEArandomvalue\n-----END PUBLIC KEY-----")

    with pytest.raises(ClerkAuthenticationError, match="Invalid Clerk token"):
        ClerkClient().verify_session_token("not-a-valid-jwt")
