from app.config import settings
from app.core.clerk import verify_clerk_token
from app.core.dev_auth import dev_public_key, mint_dev_token


def test_dev_token_verifies_through_clerk_path(monkeypatch):
    monkeypatch.setattr(settings, "clerk_jwt_public_key", dev_public_key())
    monkeypatch.setattr(settings, "clerk_jwks_url", None)
    monkeypatch.setattr(settings, "clerk_issuer", None)
    monkeypatch.setattr(settings, "clerk_authorized_parties", [])

    token = mint_dev_token(email="Owner@Example.com", first_name="Ada")
    claims = verify_clerk_token(token)

    assert claims["email"] == "owner@example.com"
    assert claims["first_name"] == "Ada"
    assert claims["sub"].startswith("dev_")


def test_dev_token_sub_is_stable_per_email():
    a = mint_dev_token(email="same@example.com")
    b = mint_dev_token(email="SAME@example.com")
    import jwt

    sub_a = jwt.decode(a, options={"verify_signature": False})["sub"]
    sub_b = jwt.decode(b, options={"verify_signature": False})["sub"]
    assert sub_a == sub_b
