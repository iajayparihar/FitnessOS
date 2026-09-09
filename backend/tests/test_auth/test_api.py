"""End-to-end authentication, onboarding, RBAC and tenant-isolation over HTTP."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.modules.auth.models import User
from app.modules.rbac.schemas import RoleCreate
from app.modules.rbac.service import (
    assign_role_to_user,
    create_role,
)


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def org_payload(name: str) -> dict:
    return {"organization": {"name": name}}


async def onboard(api_client, token: str, name: str) -> dict:
    response = await api_client.post(
        "/api/v1/auth/onboarding", json=org_payload(name), headers=auth_header(token)
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


# --------------------------------------------------------------------------- #
# Authentication.
# --------------------------------------------------------------------------- #


async def test_me_requires_credentials(api_client):
    response = await api_client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required."


async def test_me_rejects_a_malformed_token(api_client):
    response = await api_client.get(
        "/api/v1/auth/me", headers=auth_header("not-a-token")
    )

    assert response.status_code == 401


async def test_me_rejects_an_expired_token(api_client, make_clerk_token):
    token = make_clerk_token(
        issued_at=datetime.now(UTC) - timedelta(hours=2),
        expires_in=timedelta(minutes=1),
    )

    response = await api_client.get("/api/v1/auth/me", headers=auth_header(token))

    assert response.status_code == 401


async def test_me_rejects_a_token_from_another_issuer(api_client, make_clerk_token):
    token = make_clerk_token(issuer="https://evil.clerk.accounts.dev")

    response = await api_client.get("/api/v1/auth/me", headers=auth_header(token))

    assert response.status_code == 401


async def test_me_rejects_an_unauthorized_party(api_client, make_clerk_token):
    token = make_clerk_token(authorized_party="https://evil.example.com")

    response = await api_client.get("/api/v1/auth/me", headers=auth_header(token))

    assert response.status_code == 401


async def test_me_provisions_and_returns_the_local_user(api_client, make_clerk_token):
    token = make_clerk_token(
        subject="user_me", extra_claims={"email": "me@example.com"}
    )

    response = await api_client.get("/api/v1/auth/me", headers=auth_header(token))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["clerk_user_id"] == "user_me"
    assert data["email"] == "me@example.com"
    assert data["organization_id"] is None


async def test_me_is_stable_across_requests(api_client, make_clerk_token):
    """Repeated authentication must not create a second local user."""
    token = make_clerk_token(subject="user_stable")

    first = await api_client.get("/api/v1/auth/me", headers=auth_header(token))
    second = await api_client.get("/api/v1/auth/me", headers=auth_header(token))

    assert first.json()["data"]["id"] == second.json()["data"]["id"]


async def test_never_echoes_the_token(api_client, make_clerk_token):
    token = make_clerk_token(subject="user_leak")

    response = await api_client.get("/api/v1/auth/me", headers=auth_header(token))

    assert token not in response.text


# --------------------------------------------------------------------------- #
# Onboarding.
# --------------------------------------------------------------------------- #


async def test_onboarding_creates_a_tenant_and_owner_role(api_client, make_clerk_token):
    token = make_clerk_token(subject="user_owner")

    data = await onboard(api_client, token, "Iron House Gym")

    assert data["organization"]["name"] == "Iron House Gym"
    assert data["user"]["organization_id"] == data["organization"]["id"]

    context = await api_client.get("/api/v1/auth/context", headers=auth_header(token))
    assert context.status_code == 200
    context_data = context.json()["data"]
    assert context_data["role_slugs"] == ["owner"]
    assert "billing:manage" in context_data["permissions"]


async def test_onboarding_is_rejected_twice(api_client, make_clerk_token):
    token = make_clerk_token(subject="user_owner")
    await onboard(api_client, token, "First Gym")

    response = await api_client.post(
        "/api/v1/auth/onboarding",
        json=org_payload("Second Gym"),
        headers=auth_header(token),
    )

    assert response.status_code == 409


async def test_onboarding_requires_authentication(api_client):
    response = await api_client.post(
        "/api/v1/auth/onboarding", json=org_payload("Anon Gym")
    )

    assert response.status_code == 401


async def test_onboarding_rejects_a_duplicate_slug(api_client, make_clerk_token):
    await onboard(api_client, make_clerk_token(subject="user_a"), "Shared Name")

    response = await api_client.post(
        "/api/v1/auth/onboarding",
        json=org_payload("Shared Name"),
        headers=auth_header(make_clerk_token(subject="user_b")),
    )

    assert response.status_code == 409


async def test_organization_creation_requires_authentication(api_client):
    """Tenant creation must never be reachable anonymously."""
    response = await api_client.post("/api/v1/tenants", json={"name": "Anon Gym"})

    assert response.status_code == 401


async def test_organization_creation_denied_once_onboarded(
    api_client, make_clerk_token
):
    token = make_clerk_token(subject="user_owner")
    await onboard(api_client, token, "Owned Gym")

    response = await api_client.post(
        "/api/v1/tenants", json={"name": "Extra Gym"}, headers=auth_header(token)
    )

    assert response.status_code == 403


# --------------------------------------------------------------------------- #
# Tenant isolation.
# --------------------------------------------------------------------------- #


async def test_each_tenant_sees_only_its_own_organization(api_client, make_clerk_token):
    token_a = make_clerk_token(subject="user_org_a")
    token_b = make_clerk_token(subject="user_org_b")
    org_a = await onboard(api_client, token_a, "Gym A")
    org_b = await onboard(api_client, token_b, "Gym B")

    assert org_a["organization"]["id"] != org_b["organization"]["id"]

    current_a = await api_client.get(
        "/api/v1/tenants/current", headers=auth_header(token_a)
    )
    current_b = await api_client.get(
        "/api/v1/tenants/current", headers=auth_header(token_b)
    )

    assert current_a.json()["data"]["id"] == org_a["organization"]["id"]
    assert current_b.json()["data"]["id"] == org_b["organization"]["id"]


async def test_a_users_context_never_leaks_another_tenant(api_client, make_clerk_token):
    token_a = make_clerk_token(subject="user_org_a")
    token_b = make_clerk_token(subject="user_org_b")
    org_a = await onboard(api_client, token_a, "Gym A")
    await onboard(api_client, token_b, "Gym B")

    context_b = await api_client.get(
        "/api/v1/auth/context", headers=auth_header(token_b)
    )

    assert context_b.json()["data"]["organization"]["id"] != org_a["organization"]["id"]


async def test_roles_are_scoped_to_the_callers_tenant(api_client, make_clerk_token):
    """Listing roles must return the caller's tenant roles, never another's."""
    token_a = make_clerk_token(subject="user_org_a")
    token_b = make_clerk_token(subject="user_org_b")
    await onboard(api_client, token_a, "Gym A")
    await onboard(api_client, token_b, "Gym B")

    created = await api_client.post(
        "/api/v1/rbac/roles",
        json={"name": "Front Desk A", "permission_codes": ["users:read"]},
        headers=auth_header(token_a),
    )
    assert created.status_code == 201, created.text

    roles_b = await api_client.get("/api/v1/rbac/roles", headers=auth_header(token_b))
    assert roles_b.status_code == 200
    names = {role["name"] for role in roles_b.json()["data"]}
    assert "Front Desk A" not in names


async def test_a_role_from_another_tenant_cannot_be_assigned(
    api_client, make_clerk_token, db_session
):
    """Cross-tenant role assignment must fail even with a valid role UUID."""
    token_a = make_clerk_token(subject="user_org_a")
    token_b = make_clerk_token(subject="user_org_b")
    await onboard(api_client, token_a, "Gym A")
    await onboard(api_client, token_b, "Gym B")

    created = await api_client.post(
        "/api/v1/rbac/roles",
        json={"name": "Trainer A", "permission_codes": ["attendance:manage"]},
        headers=auth_header(token_a),
    )
    role_a_id = created.json()["data"]["id"]

    result = await db_session.execute(
        select(User).where(User.clerk_user_id == "user_org_b")
    )
    user_b = result.scalar_one()

    response = await api_client.post(
        f"/api/v1/rbac/users/{user_b.id}/roles",
        json={"role_id": role_a_id},
        headers=auth_header(token_b),
    )

    assert response.status_code in (403, 404), response.text


# --------------------------------------------------------------------------- #
# RBAC.
# --------------------------------------------------------------------------- #


async def test_a_user_without_a_tenant_is_denied_permissions(
    api_client, make_clerk_token
):
    token = make_clerk_token(subject="user_no_org")

    response = await api_client.get("/api/v1/rbac/roles", headers=auth_header(token))

    assert response.status_code == 403


async def test_owner_is_granted_managed_permissions(api_client, make_clerk_token):
    token = make_clerk_token(subject="user_owner")
    await onboard(api_client, token, "Permissioned Gym")

    response = await api_client.get("/api/v1/rbac/roles", headers=auth_header(token))

    assert response.status_code == 200


async def test_a_role_without_the_permission_is_denied(
    api_client, make_clerk_token, db_session
):
    """A member holding only a read role must not reach a manage-only endpoint."""
    owner_token = make_clerk_token(subject="user_owner")
    staff_token = make_clerk_token(subject="user_staff")
    org = await onboard(api_client, owner_token, "Staffed Gym")
    organization_id = org["organization"]["id"]

    # Bring the staff user into existence, then place them in the same tenant
    # with a role that grants reads only.
    await api_client.get("/api/v1/auth/me", headers=auth_header(staff_token))
    result = await db_session.execute(
        select(User).where(User.clerk_user_id == "user_staff")
    )
    staff = result.scalar_one()
    staff.organization_id = uuid.UUID(organization_id)
    await db_session.commit()

    role = await create_role(
        db_session,
        payload=RoleCreate(name="Read Only", permission_codes=["rbac:read"]),
        organization_id=uuid.UUID(organization_id),
    )
    await assign_role_to_user(
        db_session,
        user_id=staff.id,
        role_id=role.id,
        organization_id=uuid.UUID(organization_id),
    )
    await db_session.commit()

    allowed = await api_client.get(
        "/api/v1/rbac/roles", headers=auth_header(staff_token)
    )
    denied = await api_client.post(
        "/api/v1/rbac/roles",
        json={"name": "Escalated", "permission_codes": ["rbac:manage"]},
        headers=auth_header(staff_token),
    )

    assert allowed.status_code == 200
    assert denied.status_code == 403


# --------------------------------------------------------------------------- #
# Legacy password authentication.
# --------------------------------------------------------------------------- #


async def test_legacy_endpoints_are_disabled_by_default(api_client):
    for path, payload in (
        ("/api/v1/auth/register", {}),
        ("/api/v1/auth/login", {}),
        ("/api/v1/auth/refresh", {}),
        ("/api/v1/auth/logout", {}),
    ):
        response = await api_client.post(path, json=payload)
        assert response.status_code == 404, f"{path} -> {response.status_code}"


async def test_legacy_register_and_login_work_when_enabled(
    api_client, monkeypatch, clerk_settings
):
    monkeypatch.setattr(clerk_settings, "legacy_password_auth_enabled", True)
    monkeypatch.setattr(clerk_settings, "jwt_secret_key", "legacy-test-secret-key")

    registered = await api_client.post(
        "/api/v1/auth/register",
        json={
            "organization": {"name": "Legacy Gym"},
            "email": "legacy@example.com",
            "password": "correct horse battery",
        },
    )
    assert registered.status_code == 201, registered.text
    access_token = registered.json()["data"]["access_token"]

    me = await api_client.get("/api/v1/auth/me", headers=auth_header(access_token))

    assert me.status_code == 200
    assert me.json()["data"]["email"] == "legacy@example.com"


async def test_legacy_token_is_rejected_when_the_flag_is_off(
    api_client, monkeypatch, clerk_settings
):
    """Turning the flag off must invalidate legacy tokens, not fall through."""
    monkeypatch.setattr(clerk_settings, "legacy_password_auth_enabled", True)
    monkeypatch.setattr(clerk_settings, "jwt_secret_key", "legacy-test-secret-key")
    registered = await api_client.post(
        "/api/v1/auth/register",
        json={
            "organization": {"name": "Legacy Gym"},
            "email": "legacy@example.com",
            "password": "correct horse battery",
        },
    )
    access_token = registered.json()["data"]["access_token"]

    monkeypatch.setattr(clerk_settings, "legacy_password_auth_enabled", False)
    response = await api_client.get(
        "/api/v1/auth/me", headers=auth_header(access_token)
    )

    assert response.status_code == 401


# --------------------------------------------------------------------------- #
# Rate limiting.
# --------------------------------------------------------------------------- #


async def test_onboarding_is_rate_limited(api_client, make_clerk_token):
    from app.modules.auth.router import onboarding_rate_limit

    onboarding_rate_limit.limiter.reset()
    statuses = []
    for index in range(12):
        response = await api_client.post(
            "/api/v1/auth/onboarding",
            json=org_payload(f"Gym {index}"),
            headers=auth_header(make_clerk_token(subject=f"user_rl_{index}")),
        )
        statuses.append(response.status_code)
    onboarding_rate_limit.limiter.reset()

    assert 429 in statuses, statuses
    assert statuses.count(201) == 10, statuses
