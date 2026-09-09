"""Organization creation, retrieval, update and lifecycle over HTTP."""

import uuid

import pytest
from sqlalchemy import func, select

from app.core.enums import (
    BusinessType,
    OrganizationMemberRole,
    OrganizationMemberStatus,
    OrganizationStatus,
)
from app.modules.auth.models import User
from app.modules.tenants.models import (
    Organization,
    OrganizationBranch,
    OrganizationMembership,
    OrganizationSetting,
)
from app.modules.tenants.service import allocate_slug, make_slug


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def create_org(api_client, token: str, name: str, **extra) -> dict:
    response = await api_client.post(
        "/api/v1/organizations",
        json={"name": name, **extra},
        headers=auth_header(token),
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


# --------------------------------------------------------------------------- #
# Authentication
# --------------------------------------------------------------------------- #


async def test_unauthenticated_creation_is_rejected(api_client):
    response = await api_client.post("/api/v1/organizations", json={"name": "Anon Gym"})

    assert response.status_code == 401


async def test_authenticated_user_can_create_an_organization(
    api_client, make_clerk_token
):
    token = make_clerk_token(subject="user_owner")

    data = await create_org(api_client, token, "Iron House Gym")

    assert data["organization"]["name"] == "Iron House Gym"
    assert data["organization"]["slug"] == "iron-house-gym"
    assert data["organization"]["status"] == OrganizationStatus.ACTIVE.value


# --------------------------------------------------------------------------- #
# Provisioning completeness
# --------------------------------------------------------------------------- #


async def test_creation_produces_owner_membership_branch_and_settings(
    api_client, make_clerk_token, db_session
):
    token = make_clerk_token(subject="user_owner")

    data = await create_org(
        api_client, token, "Full Gym", business_type="crossfit", timezone="Asia/Kolkata"
    )
    organization_id = uuid.UUID(data["organization"]["id"])

    assert data["membership"]["role"] == OrganizationMemberRole.OWNER.value
    assert data["membership"]["status"] == OrganizationMemberStatus.ACTIVE.value
    assert data["main_branch"]["is_main"] is True
    assert data["organization"]["business_type"] == BusinessType.CROSSFIT.value

    settings = await db_session.execute(
        select(OrganizationSetting.key).where(
            OrganizationSetting.organization_id == organization_id
        )
    )
    assert set(settings.scalars()) == {"locale", "business_hours", "notifications"}

    locale = await db_session.execute(
        select(OrganizationSetting.value).where(
            OrganizationSetting.organization_id == organization_id,
            OrganizationSetting.key == "locale",
        )
    )
    assert locale.scalar_one()["timezone"] == "Asia/Kolkata"


async def test_creation_assigns_the_owner_rbac_role(api_client, make_clerk_token):
    token = make_clerk_token(subject="user_owner")
    data = await create_org(api_client, token, "RBAC Gym")
    organization_id = data["organization"]["id"]

    context = await api_client.get("/api/v1/auth/context", headers=auth_header(token))

    assert context.json()["data"]["role_slugs"] == ["owner"]
    assert "tenants:manage" in context.json()["data"]["permissions"]
    assert context.json()["data"]["organization"]["id"] == organization_id


async def test_creation_is_atomic(
    api_client, make_clerk_token, db_session, monkeypatch
):
    """A failure after the organization row must leave no trace of the tenant."""
    from app.modules.tenants import service as tenant_service

    async def explode(*args, **kwargs):
        raise RuntimeError("branch initialisation failed")

    monkeypatch.setattr(tenant_service, "_seed_default_settings", explode)

    token = make_clerk_token(subject="user_atomic")
    with pytest.raises(RuntimeError, match="branch initialisation failed"):
        await api_client.post(
            "/api/v1/organizations",
            json={"name": "Doomed Gym"},
            headers=auth_header(token),
        )

    # db_session is a separate connection, so it observes committed state only.
    for model in (Organization, OrganizationMembership, OrganizationBranch):
        count = await db_session.execute(select(func.count()).select_from(model))
        assert count.scalar_one() == 0, f"{model.__name__} rows survived the rollback"

    user = await db_session.execute(
        select(User).where(User.clerk_user_id == "user_atomic")
    )
    resolved = user.scalar_one_or_none()
    assert resolved is None or resolved.organization_id is None


async def test_second_organization_is_refused(api_client, make_clerk_token):
    token = make_clerk_token(subject="user_owner")
    await create_org(api_client, token, "First Gym")

    response = await api_client.post(
        "/api/v1/organizations",
        json={"name": "Second Gym"},
        headers=auth_header(token),
    )

    assert response.status_code == 409


# --------------------------------------------------------------------------- #
# Slugs
# --------------------------------------------------------------------------- #


def test_slug_is_normalised():
    assert make_slug("Ajay Fitness Studio") == "ajay-fitness-studio"
    assert make_slug("  CrossFit  BOX #1 ") == "crossfit-box-1"
    assert make_slug("!!!") == "organization"


async def test_duplicate_names_get_suffixed_slugs(api_client, make_clerk_token):
    first = await create_org(
        api_client, make_clerk_token(subject="user_a"), "Ajay Fitness Studio"
    )
    second = await create_org(
        api_client, make_clerk_token(subject="user_b"), "Ajay Fitness Studio"
    )
    third = await create_org(
        api_client, make_clerk_token(subject="user_c"), "Ajay Fitness Studio"
    )

    assert first["organization"]["slug"] == "ajay-fitness-studio"
    assert second["organization"]["slug"] == "ajay-fitness-studio-2"
    assert third["organization"]["slug"] == "ajay-fitness-studio-3"


async def test_slug_uniqueness_is_enforced_by_the_database(db_session):
    """Application-level allocation is a convenience; the index is the guarantee."""
    db_session.add(Organization(name="Dup", slug="dup-gym"))
    await db_session.commit()

    db_session.add(Organization(name="Dup Again", slug="dup-gym"))
    with pytest.raises(Exception):
        await db_session.commit()
    await db_session.rollback()


async def test_soft_deleted_slug_can_be_reused(db_session):
    """The unique index is partial, so archived tenants do not hold slugs forever."""
    archived = Organization(name="Old", slug="reusable", deleted_at=func.now())
    db_session.add(archived)
    await db_session.commit()

    assert await allocate_slug(db_session, preferred="Reusable") == "reusable"


# --------------------------------------------------------------------------- #
# Read / update / archive
# --------------------------------------------------------------------------- #


async def test_organization_can_be_retrieved_and_listed(api_client, make_clerk_token):
    token = make_clerk_token(subject="user_owner")
    data = await create_org(api_client, token, "Readable Gym")
    organization_id = data["organization"]["id"]

    detail = await api_client.get(
        f"/api/v1/organizations/{organization_id}", headers=auth_header(token)
    )
    listing = await api_client.get("/api/v1/organizations", headers=auth_header(token))

    assert detail.status_code == 200
    assert detail.json()["data"]["name"] == "Readable Gym"
    assert listing.status_code == 200
    rows = listing.json()["data"]
    assert len(rows) == 1
    assert rows[0]["role"] == OrganizationMemberRole.OWNER.value
    assert rows[0]["is_current"] is True


async def test_organization_can_be_updated(api_client, make_clerk_token):
    token = make_clerk_token(subject="user_owner")
    organization_id = (await create_org(api_client, token, "Old Name"))["organization"][
        "id"
    ]

    response = await api_client.patch(
        f"/api/v1/organizations/{organization_id}",
        json={"name": "New Name", "business_type": "yoga", "phone": "+91 99999 11111"},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "New Name"
    assert data["business_type"] == BusinessType.YOGA.value
    assert data["phone"] == "+91 99999 11111"
    assert data["slug"] == "old-name", "slug is stable across renames"


async def test_archived_organization_is_soft_deleted_and_frozen(
    api_client, make_clerk_token, db_session
):
    token = make_clerk_token(subject="user_owner")
    organization_id = (await create_org(api_client, token, "Doomed Gym"))[
        "organization"
    ]["id"]

    deleted = await api_client.delete(
        f"/api/v1/organizations/{organization_id}", headers=auth_header(token)
    )
    assert deleted.status_code == 204

    row = await db_session.execute(
        select(Organization).where(Organization.id == uuid.UUID(organization_id))
    )
    organization = row.scalar_one()
    assert organization.deleted_at is not None, "row must be retained, not dropped"
    assert organization.status is OrganizationStatus.ARCHIVED

    follow_up = await api_client.get(
        f"/api/v1/organizations/{organization_id}", headers=auth_header(token)
    )
    assert follow_up.status_code == 404


async def test_suspended_organization_cannot_operate(
    api_client, make_clerk_token, db_session
):
    token = make_clerk_token(subject="user_owner")
    organization_id = (await create_org(api_client, token, "Suspended Gym"))[
        "organization"
    ]["id"]

    row = await db_session.execute(
        select(Organization).where(Organization.id == uuid.UUID(organization_id))
    )
    row.scalar_one().status = OrganizationStatus.SUSPENDED
    await db_session.commit()

    response = await api_client.get(
        f"/api/v1/organizations/{organization_id}", headers=auth_header(token)
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Organization is not active."


async def test_organization_id_is_never_taken_from_the_request_body(
    api_client, make_clerk_token, db_session
):
    """A client-supplied organization_id must be ignored, not honoured."""
    victim_token = make_clerk_token(subject="user_victim")
    victim = await create_org(api_client, victim_token, "Victim Gym")

    attacker_token = make_clerk_token(subject="user_attacker")
    response = await api_client.post(
        "/api/v1/organizations",
        json={
            "name": "Attacker Gym",
            "organization_id": victim["organization"]["id"],
            "id": victim["organization"]["id"],
        },
        headers=auth_header(attacker_token),
    )

    assert response.status_code == 201
    assert response.json()["data"]["organization"]["id"] != victim["organization"]["id"]


async def test_provisioning_service_is_reused_by_clerk_onboarding(
    api_client, make_clerk_token, db_session
):
    """/auth/onboarding must produce the same fully-initialised tenant."""
    token = make_clerk_token(subject="user_onboard")

    response = await api_client.post(
        "/api/v1/auth/onboarding",
        json={"organization": {"name": "Onboarded Gym"}},
        headers=auth_header(token),
    )
    assert response.status_code == 201, response.text
    organization_id = uuid.UUID(response.json()["data"]["organization"]["id"])

    branches = await db_session.execute(
        select(func.count())
        .select_from(OrganizationBranch)
        .where(OrganizationBranch.organization_id == organization_id)
    )
    memberships = await db_session.execute(
        select(func.count())
        .select_from(OrganizationMembership)
        .where(OrganizationMembership.organization_id == organization_id)
    )
    assert branches.scalar_one() == 1
    assert memberships.scalar_one() == 1
