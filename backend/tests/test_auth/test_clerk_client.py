"""Clerk session-token verification: signature, claims, issuer, authorized party."""

import base64
import json
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.integrations.clerk.client import ClerkClient
from app.integrations.clerk.exceptions import (
    ClerkAuthenticationError,
    ClerkConfigurationError,
)
from tests.conftest import TEST_AUTHORIZED_PARTY, TEST_ISSUER


def test_accepts_a_realistic_clerk_session_token(clerk_settings, make_clerk_token):
    """A default-shaped Clerk token carries azp and no aud, and must verify."""
    token = make_clerk_token(subject="user_2abc")

    claims = ClerkClient().verify_session_token(token)

    assert claims["sub"] == "user_2abc"
    assert claims["azp"] == TEST_AUTHORIZED_PARTY
    assert "aud" not in claims


def test_rejects_expired_token(clerk_settings, make_clerk_token):
    token = make_clerk_token(
        issued_at=datetime.now(UTC) - timedelta(hours=1),
        expires_in=timedelta(minutes=1),
    )

    with pytest.raises(ClerkAuthenticationError):
        ClerkClient().verify_session_token(token)


def test_rejects_token_signed_by_a_different_key(clerk_settings, make_clerk_token):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pem = other_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    token = make_clerk_token(key=other_pem)

    with pytest.raises(ClerkAuthenticationError):
        ClerkClient().verify_session_token(token)


def test_rejects_tampered_payload(clerk_settings, make_clerk_token):
    header, payload, signature = make_clerk_token().split(".")
    tampered = f"{header}.{payload[:-4]}AAAA.{signature}"

    with pytest.raises(ClerkAuthenticationError):
        ClerkClient().verify_session_token(tampered)


def test_rejects_unsigned_token(clerk_settings, make_clerk_token):
    """An alg=none style token must never be accepted."""
    signed = make_clerk_token()
    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        .rstrip(b"=")
        .decode()
    )
    token = f"{header}.{signed.split('.')[1]}."

    with pytest.raises(ClerkAuthenticationError):
        ClerkClient().verify_session_token(token)


def test_rejects_symmetric_algorithm_downgrade(clerk_settings, make_clerk_token):
    token = make_clerk_token(key="shared-secret", algorithm="HS256")

    with pytest.raises(ClerkAuthenticationError):
        ClerkClient().verify_session_token(token)


def test_rejects_wrong_issuer(clerk_settings, make_clerk_token):
    token = make_clerk_token(issuer="https://attacker.clerk.accounts.dev")

    with pytest.raises(ClerkAuthenticationError):
        ClerkClient().verify_session_token(token)


def test_rejects_unauthorized_party(clerk_settings, make_clerk_token):
    token = make_clerk_token(authorized_party="https://phishing.example.com")

    with pytest.raises(ClerkAuthenticationError, match="unauthorized party"):
        ClerkClient().verify_session_token(token)


def test_rejects_token_without_authorized_party(clerk_settings, make_clerk_token):
    token = make_clerk_token(authorized_party=None)

    with pytest.raises(ClerkAuthenticationError):
        ClerkClient().verify_session_token(token)


def test_rejects_token_without_subject(clerk_settings, make_clerk_token):
    token = make_clerk_token(drop_claims=("sub",))

    with pytest.raises(ClerkAuthenticationError):
        ClerkClient().verify_session_token(token)


def test_rejects_token_without_expiry(clerk_settings, make_clerk_token):
    token = make_clerk_token(drop_claims=("exp",))

    with pytest.raises(ClerkAuthenticationError):
        ClerkClient().verify_session_token(token)


@pytest.mark.parametrize("token", ["", "   ", "not-a-jwt", "a.b", "a.b.c.d"])
def test_rejects_missing_and_malformed_tokens(clerk_settings, token):
    with pytest.raises(ClerkAuthenticationError):
        ClerkClient().verify_session_token(token)


def test_requires_issuer_configuration(clerk_settings, monkeypatch, make_clerk_token):
    token = make_clerk_token()
    monkeypatch.setattr(clerk_settings, "clerk_issuer", None)

    with pytest.raises(ClerkConfigurationError, match="issuer"):
        ClerkClient().verify_session_token(token)


def test_requires_authorized_parties_configuration(
    clerk_settings, monkeypatch, make_clerk_token
):
    token = make_clerk_token()
    monkeypatch.setattr(clerk_settings, "clerk_authorized_parties", [])

    with pytest.raises(ClerkConfigurationError, match="authorized parties"):
        ClerkClient().verify_session_token(token)


def test_requires_a_signing_key_source(clerk_settings, monkeypatch, make_clerk_token):
    token = make_clerk_token()
    monkeypatch.setattr(clerk_settings, "clerk_jwt_key", None)
    monkeypatch.setattr(clerk_settings, "clerk_jwks_url", None)

    with pytest.raises(ClerkConfigurationError, match="not configured"):
        ClerkClient().verify_session_token(token)


def test_tolerates_small_clock_skew(clerk_settings, make_clerk_token):
    """A token issued a couple of seconds in the future must still verify."""
    token = make_clerk_token(issued_at=datetime.now(UTC) + timedelta(seconds=2))

    assert ClerkClient().verify_session_token(token)["iss"] == TEST_ISSUER
