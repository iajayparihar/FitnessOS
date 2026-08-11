import uuid

import pytest

from app.core.security import (
    create_access_token,
    decode_jwt,
    hash_password,
    verify_password,
)


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
    )
    payload = decode_jwt(token)

    assert payload["sub"] == str(user_id)
    assert payload["organization_id"] == str(organization_id)
    assert payload["type"] == "access"


def test_decode_jwt_rejects_tampered_signature():
    token = create_access_token(
        subject=uuid.uuid4(),
        organization_id=None,
        is_superuser=False,
    )
    header, payload, signature = token.split(".")

    with pytest.raises(ValueError):
        decode_jwt(f"{header}.{payload}.{signature[:-2]}xx")
