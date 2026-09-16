import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from app.config import settings
from app.core.clerk import ClerkAuthError, verify_clerk_token
from app.modules.analytics.models import AuditLog
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.exceptions import AlreadyOnboarded, InviteInvalid
from app.modules.auth.models import AuthProvider, Invite, User, UserAuthMethod
from app.modules.auth.schemas import OnboardingRequest
from app.modules.auth.service import (
    accept_invite,
    get_or_create_user_from_clerk,
    onboard_organization,
)
from app.modules.rbac.models import Permission, Role, UserRole
from app.modules.rbac.service import DEFAULT_PERMISSIONS
from app.modules.tenants.models import Organization
from app.modules.tenants.schemas import OrgCreate

import asyncio


# --- fake async session (mirrors the RBAC test idiom) --------------------------


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        if isinstance(self.value, list):
            return iter(self.value)
        if self.value is None:
            return iter(())
        return iter((self.value,))


class FakeSession:
    def __init__(self, results=()):
        self.results = list(results)
        self.added = []
        self.committed = False
        self.refreshed = []

    async def execute(self, statement):
        return _Result(self.results.pop(0))

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        for value in self.added:
            if hasattr(value, "id") and getattr(value, "id", None) is None:
                value.id = uuid.uuid4()

    async def commit(self):
        self.committed = True

    async def refresh(self, value):
        self.refreshed.append(value)


def _default_permissions():
    return [
        Permission(id=uuid.uuid4(), code=code, category=category, is_active=True)
        for code, _description, category in DEFAULT_PERMISSIONS
    ]


# --- Clerk token verification --------------------------------------------------


@pytest.fixture(scope="module")
def rsa_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


@pytest.fixture
def clerk_configured(rsa_keys, monkeypatch):
    _private_pem, public_pem = rsa_keys
    monkeypatch.setattr(settings, "clerk_jwt_public_key", public_pem)
    monkeypatch.setattr(settings, "clerk_jwks_url", None)
    monkeypatch.setattr(settings, "clerk_issuer", None)
    monkeypatch.setattr(settings, "clerk_authorized_parties", [])
    return rsa_keys


def _mint(private_pem, **overrides):
    now = datetime.now(UTC)
    payload = {
        "sub": "user_clerk_abc",
        "email": "owner@example.com",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    payload.update(overrides)
    return jwt.encode(payload, private_pem, algorithm="RS256")


def test_verify_clerk_token_accepts_valid_token(clerk_configured):
    private_pem, _public_pem = clerk_configured
    claims = verify_clerk_token(_mint(private_pem))

    assert claims["sub"] == "user_clerk_abc"
    assert claims["email"] == "owner@example.com"


def test_verify_clerk_token_rejects_expired_token(clerk_configured):
    private_pem, _public_pem = clerk_configured
    token = _mint(
        private_pem,
        iat=datetime.now(UTC) - timedelta(minutes=30),
        exp=datetime.now(UTC) - timedelta(minutes=10),
    )

    with pytest.raises(ClerkAuthError):
        verify_clerk_token(token)


def test_verify_clerk_token_rejects_bad_signature(clerk_configured):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pem = other_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    with pytest.raises(ClerkAuthError):
        verify_clerk_token(_mint(other_pem))


def test_verify_clerk_token_rejects_unauthorized_party(clerk_configured, monkeypatch):
    private_pem, _public_pem = clerk_configured
    monkeypatch.setattr(settings, "clerk_authorized_parties", ["https://app.example.com"])

    with pytest.raises(ClerkAuthError):
        verify_clerk_token(_mint(private_pem, azp="https://evil.example.com"))


def test_verify_clerk_token_unconfigured_raises(monkeypatch, rsa_keys):
    private_pem, _public_pem = rsa_keys
    monkeypatch.setattr(settings, "clerk_jwt_public_key", None)
    monkeypatch.setattr(settings, "clerk_jwks_url", None)

    with pytest.raises(ClerkAuthError):
        verify_clerk_token(_mint(private_pem))


def test_get_current_user_rejects_invalid_token(clerk_configured):
    from fastapi.security import HTTPAuthorizationCredentials

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not-a-jwt")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_current_user(credentials=credentials, db=FakeSession()))

    assert exc.value.status_code == 401


def test_get_current_user_requires_credentials():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_current_user(credentials=None, db=FakeSession()))

    assert exc.value.status_code == 401
    assert exc.value.detail == "Authentication required."


# --- JIT provisioning ----------------------------------------------------------


def test_get_or_create_user_provisions_new_user():
    db = FakeSession(results=[None])

    user = asyncio.run(
        get_or_create_user_from_clerk(
            db,
            claims={
                "sub": "user_clerk_abc",
                "email": "Owner@Example.com",
                "first_name": "Ada",
                "last_name": "Lovelace",
            },
        )
    )

    assert user in db.added
    assert user.email == "owner@example.com"
    assert db.committed is True
    method = user.auth_methods[0]
    assert method.provider == AuthProvider.CLERK
    assert method.provider_uid == "user_clerk_abc"
    assert user.profile.first_name == "Ada"


def test_get_or_create_user_returns_existing_user():
    existing = User(
        id=uuid.uuid4(),
        email="owner@example.com",
        is_active=True,
        is_superuser=False,
    )
    method = UserAuthMethod(
        provider=AuthProvider.CLERK,
        provider_uid="user_clerk_abc",
        is_primary=True,
    )
    method.user = existing
    db = FakeSession(results=[method])

    resolved = asyncio.run(
        get_or_create_user_from_clerk(db, claims={"sub": "user_clerk_abc"})
    )

    assert resolved is existing
    assert existing not in db.added
    # Hot path (verified every request) must not write.
    assert db.committed is False


# --- onboarding ----------------------------------------------------------------


def test_onboard_organization_creates_org_and_owner():
    user = User(
        id=uuid.uuid4(),
        email="owner@example.com",
        is_active=True,
        is_superuser=False,
    )
    user.organization_id = None
    permissions = _default_permissions()
    owner_role_seed = Role(
        id=uuid.uuid4(),
        name="Owner",
        slug="owner",
        is_active=True,
    )
    db = FakeSession(results=[None, permissions, None, [], owner_role_seed, user.id, None])

    result_user, organization = asyncio.run(
        onboard_organization(
            db,
            user=user,
            payload=OnboardingRequest(organization=OrgCreate(name="Acme Gym")),
        )
    )

    assert result_user.organization_id == organization.id
    assert db.committed is True
    assert any(isinstance(value, Organization) for value in db.added)
    assert any(isinstance(value, Role) for value in db.added)
    assert any(isinstance(value, UserRole) for value in db.added)
    assert any(isinstance(value, AuditLog) for value in db.added)


def test_onboard_organization_rejects_already_onboarded():
    user = User(id=uuid.uuid4(), email="owner@example.com", is_active=True)
    user.organization_id = uuid.uuid4()

    with pytest.raises(AlreadyOnboarded):
        asyncio.run(
            onboard_organization(
                FakeSession(),
                user=user,
                payload=OnboardingRequest(organization=OrgCreate(name="Acme Gym")),
            )
        )


# --- invite acceptance ---------------------------------------------------------


def test_accept_invite_joins_org_and_assigns_role():
    organization_id = uuid.uuid4()
    role_id = uuid.uuid4()
    user = User(id=uuid.uuid4(), email="member@example.com", is_active=True)
    user.organization_id = None
    invite = Invite(
        id=uuid.uuid4(),
        organization_id=organization_id,
        email="Member@Example.com",
        token="invite-token",
        role_id=role_id,
        invited_by=uuid.uuid4(),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    role_seed = Role(id=role_id, organization_id=organization_id, name="Coach", slug="coach", is_active=True)
    org_seed = Organization(id=organization_id, name="Acme", slug="acme")
    db = FakeSession(results=[invite, role_seed, user.id, None, org_seed])

    result_user, organization = asyncio.run(
        accept_invite(db, user=user, token="invite-token")
    )

    assert result_user.organization_id == organization_id
    assert organization is org_seed
    assert invite.accepted_at is not None
    assert any(isinstance(value, UserRole) for value in db.added)
    assert db.committed is True


def test_accept_invite_rejects_unknown_token():
    user = User(id=uuid.uuid4(), email="member@example.com", is_active=True)
    user.organization_id = None

    with pytest.raises(InviteInvalid):
        asyncio.run(accept_invite(FakeSession(results=[None]), user=user, token="nope"))


def test_accept_invite_rejects_email_mismatch():
    user = User(id=uuid.uuid4(), email="member@example.com", is_active=True)
    user.organization_id = None
    invite = Invite(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        email="someone-else@example.com",
        token="invite-token",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )

    with pytest.raises(InviteInvalid):
        asyncio.run(
            accept_invite(FakeSession(results=[invite]), user=user, token="invite-token")
        )


def test_accept_invite_rejects_already_onboarded():
    user = User(id=uuid.uuid4(), email="member@example.com", is_active=True)
    user.organization_id = uuid.uuid4()

    with pytest.raises(AlreadyOnboarded):
        asyncio.run(accept_invite(FakeSession(), user=user, token="invite-token"))
