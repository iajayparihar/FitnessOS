"""Organization membership: seats, invariants and access consequences."""

import uuid

import pytest
from sqlalchemy import select

from app.core.enums import OrganizationMemberRole, OrganizationMemberStatus
from app.modules.auth.models import User
from app.modules.tenants.models import OrganizationMembership
from tests.test_tenants.test_organizations import auth_header, create_org


async def _user_id(db_session, clerk_user_id: str) -> uuid.UUID:
    result = await db_session.execute(
        select(User.id).where(User.clerk_user_id == clerk_user_id)
    )
    return result.scalar_one()


async def _materialise_user(api_client, token: str) -> None:
    """Make a Clerk identity exist locally without giving it an organization."""
    response = await api_client.get("/api/v1/auth/me", headers=auth_header(token))
    assert response.status_code == 200


async def test_creation_leaves_exactly_one_owner_membership(
    api_client, make_clerk_token, db_session
):
    token = make_clerk_token(subject="user_owner")
    organization_id = (await create_org(api_client, token, "Owned Gym"))[
        "organization"
    ]["id"]

    response = await api_client.get(
        f"/api/v1/organizations/{organization_id}/members", headers=auth_header(token)
    )

    assert response.status_code == 200
    members = response.json()["data"]
    assert len(members) == 1
    assert members[0]["role"] == OrganizationMemberRole.OWNER.value


async def test_owner_can_add_a_member(api_client, make_clerk_token, db_session):
    owner_token = make_clerk_token(subject="user_owner")
    staff_token = make_clerk_token(subject="user_staff")
    organization_id = (await create_org(api_client, owner_token, "Staffed Gym"))[
        "organization"
    ]["id"]
    await _materialise_user(api_client, staff_token)
    staff_id = await _user_id(db_session, "user_staff")

    response = await api_client.post(
        f"/api/v1/organizations/{organization_id}/members",
        json={"user_id": str(staff_id), "role": "trainer"},
        headers=auth_header(owner_token),
    )

    assert response.status_code == 201, response.text
    assert response.json()["data"]["role"] == OrganizationMemberRole.TRAINER.value


async def test_duplicate_membership_is_rejected(
    api_client, make_clerk_token, db_session
):
    owner_token = make_clerk_token(subject="user_owner")
    staff_token = make_clerk_token(subject="user_staff")
    organization_id = (await create_org(api_client, owner_token, "Staffed Gym"))[
        "organization"
    ]["id"]
    await _materialise_user(api_client, staff_token)
    staff_id = await _user_id(db_session, "user_staff")

    body = {"user_id": str(staff_id), "role": "staff"}
    first = await api_client.post(
        f"/api/v1/organizations/{organization_id}/members",
        json=body,
        headers=auth_header(owner_token),
    )
    second = await api_client.post(
        f"/api/v1/organizations/{organization_id}/members",
        json=body,
        headers=auth_header(owner_token),
    )

    assert first.status_code == 201
    assert second.status_code == 409


async def test_duplicate_membership_is_rejected_by_the_database(
    api_client, make_clerk_token, db_session
):
    """The partial unique index is the real guarantee under concurrency."""
    owner_token = make_clerk_token(subject="user_owner")
    organization_id = uuid.UUID(
        (await create_org(api_client, owner_token, "Indexed Gym"))["organization"]["id"]
    )
    owner_id = await _user_id(db_session, "user_owner")

    db_session.add(
        OrganizationMembership(
            organization_id=organization_id,
            user_id=owner_id,
            role=OrganizationMemberRole.STAFF,
            status=OrganizationMemberStatus.ACTIVE,
        )
    )
    with pytest.raises(Exception):
        await db_session.commit()
    await db_session.rollback()


async def test_adding_an_unknown_user_is_rejected(api_client, make_clerk_token):
    owner_token = make_clerk_token(subject="user_owner")
    organization_id = (await create_org(api_client, owner_token, "Owned Gym"))[
        "organization"
    ]["id"]

    response = await api_client.post(
        f"/api/v1/organizations/{organization_id}/members",
        json={"user_id": str(uuid.uuid4()), "role": "staff"},
        headers=auth_header(owner_token),
    )

    assert response.status_code == 404


async def test_the_last_owner_cannot_be_removed(
    api_client, make_clerk_token, db_session
):
    owner_token = make_clerk_token(subject="user_owner")
    organization_id = (await create_org(api_client, owner_token, "Owned Gym"))[
        "organization"
    ]["id"]
    owner_id = await _user_id(db_session, "user_owner")

    response = await api_client.delete(
        f"/api/v1/organizations/{organization_id}/members/{owner_id}",
        headers=auth_header(owner_token),
    )

    assert response.status_code == 409
    assert "owner" in response.json()["detail"].lower()


async def test_the_last_owner_cannot_be_demoted(
    api_client, make_clerk_token, db_session
):
    owner_token = make_clerk_token(subject="user_owner")
    organization_id = (await create_org(api_client, owner_token, "Owned Gym"))[
        "organization"
    ]["id"]
    owner_id = await _user_id(db_session, "user_owner")

    response = await api_client.patch(
        f"/api/v1/organizations/{organization_id}/members/{owner_id}",
        json={"role": "staff"},
        headers=auth_header(owner_token),
    )

    assert response.status_code == 409


async def test_a_second_owner_can_be_removed(api_client, make_clerk_token, db_session):
    owner_token = make_clerk_token(subject="user_owner")
    other_token = make_clerk_token(subject="user_other")
    organization_id = (await create_org(api_client, owner_token, "Owned Gym"))[
        "organization"
    ]["id"]
    await _materialise_user(api_client, other_token)
    other_id = await _user_id(db_session, "user_other")

    await api_client.post(
        f"/api/v1/organizations/{organization_id}/members",
        json={"user_id": str(other_id), "role": "owner"},
        headers=auth_header(owner_token),
    )
    response = await api_client.delete(
        f"/api/v1/organizations/{organization_id}/members/{other_id}",
        headers=auth_header(owner_token),
    )

    assert response.status_code == 204


async def test_removing_a_member_is_a_soft_delete(
    api_client, make_clerk_token, db_session
):
    owner_token = make_clerk_token(subject="user_owner")
    staff_token = make_clerk_token(subject="user_staff")
    organization_id = uuid.UUID(
        (await create_org(api_client, owner_token, "Owned Gym"))["organization"]["id"]
    )
    await _materialise_user(api_client, staff_token)
    staff_id = await _user_id(db_session, "user_staff")
    await api_client.post(
        f"/api/v1/organizations/{organization_id}/members",
        json={"user_id": str(staff_id), "role": "staff"},
        headers=auth_header(owner_token),
    )

    await api_client.delete(
        f"/api/v1/organizations/{organization_id}/members/{staff_id}",
        headers=auth_header(owner_token),
    )

    result = await db_session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == staff_id,
        )
    )
    membership = result.scalar_one()
    assert membership.deleted_at is not None
    assert membership.status is OrganizationMemberStatus.REMOVED


async def test_a_removed_member_immediately_loses_access(
    api_client, make_clerk_token, db_session
):
    """Revoking a membership must take effect on the very next request."""
    owner_token = make_clerk_token(subject="user_owner")
    staff_token = make_clerk_token(subject="user_staff")
    organization_id = (await create_org(api_client, owner_token, "Owned Gym"))[
        "organization"
    ]["id"]
    await _materialise_user(api_client, staff_token)
    staff_id = await _user_id(db_session, "user_staff")
    await api_client.post(
        f"/api/v1/organizations/{organization_id}/members",
        json={"user_id": str(staff_id), "role": "admin"},
        headers=auth_header(owner_token),
    )

    result = await db_session.execute(select(User).where(User.id == staff_id))
    result.scalar_one().organization_id = uuid.UUID(organization_id)
    await db_session.commit()

    before = await api_client.get(
        f"/api/v1/organizations/{organization_id}", headers=auth_header(staff_token)
    )
    await api_client.delete(
        f"/api/v1/organizations/{organization_id}/members/{staff_id}",
        headers=auth_header(owner_token),
    )
    after = await api_client.get(
        f"/api/v1/organizations/{organization_id}", headers=auth_header(staff_token)
    )

    assert before.status_code in (200, 403)
    assert after.status_code == 404


async def test_a_user_with_no_membership_cannot_reach_any_organization(
    api_client, make_clerk_token
):
    token = make_clerk_token(subject="user_orphan")

    listing = await api_client.get("/api/v1/organizations", headers=auth_header(token))
    detail = await api_client.get(
        f"/api/v1/organizations/{uuid.uuid4()}", headers=auth_header(token)
    )

    assert listing.status_code == 200
    assert listing.json()["data"] == []
    assert detail.status_code == 404


async def test_a_stale_active_org_pointer_grants_nothing(
    api_client, make_clerk_token, db_session
):
    """users.organization_id is a pointer, not an entitlement."""
    victim_token = make_clerk_token(subject="user_victim")
    attacker_token = make_clerk_token(subject="user_attacker")
    organization_id = (await create_org(api_client, victim_token, "Victim Gym"))[
        "organization"
    ]["id"]
    await _materialise_user(api_client, attacker_token)

    # Forge the pointer directly in the database, with no membership behind it.
    attacker_id = await _user_id(db_session, "user_attacker")
    result = await db_session.execute(select(User).where(User.id == attacker_id))
    result.scalar_one().organization_id = uuid.UUID(organization_id)
    await db_session.commit()

    response = await api_client.get(
        f"/api/v1/organizations/{organization_id}", headers=auth_header(attacker_token)
    )

    assert response.status_code == 404


async def test_switching_requires_membership(api_client, make_clerk_token, db_session):
    victim_token = make_clerk_token(subject="user_victim")
    attacker_token = make_clerk_token(subject="user_attacker")
    victim_org = (await create_org(api_client, victim_token, "Victim Gym"))[
        "organization"
    ]["id"]
    await create_org(api_client, attacker_token, "Attacker Gym")

    response = await api_client.post(
        f"/api/v1/organizations/{victim_org}/switch",
        headers=auth_header(attacker_token),
    )

    assert response.status_code == 404


async def test_a_multi_org_user_can_switch_between_their_tenants(
    api_client, make_clerk_token, db_session
):
    owner_token = make_clerk_token(subject="user_owner")
    other_token = make_clerk_token(subject="user_other")
    first_org = (await create_org(api_client, owner_token, "First Gym"))[
        "organization"
    ]["id"]
    second_org = (await create_org(api_client, other_token, "Second Gym"))[
        "organization"
    ]["id"]

    owner_id = await _user_id(db_session, "user_owner")
    await api_client.post(
        f"/api/v1/organizations/{second_org}/members",
        json={"user_id": str(owner_id), "role": "manager"},
        headers=auth_header(other_token),
    )

    listing = await api_client.get(
        "/api/v1/organizations", headers=auth_header(owner_token)
    )
    assert {row["id"] for row in listing.json()["data"]} == {first_org, second_org}

    switched = await api_client.post(
        f"/api/v1/organizations/{second_org}/switch", headers=auth_header(owner_token)
    )
    assert switched.status_code == 200

    after_switch = await api_client.get(
        "/api/v1/organizations", headers=auth_header(owner_token)
    )
    current = {row["id"] for row in after_switch.json()["data"] if row["is_current"]}
    assert current == {second_org}

    old_org = await api_client.get(
        f"/api/v1/organizations/{first_org}", headers=auth_header(owner_token)
    )
    assert old_org.status_code == 404, "only the active tenant is addressable"


async def test_a_seat_carries_the_permissions_of_its_system_role(
    api_client, make_clerk_token, db_session
):
    """
    Membership answers "which tenant"; RBAC answers "what may you do".

    They remain separate systems, bridged at exactly one point: each seat is
    granted the same-named system role, so a manager can read the organization
    but not reach owner-only operations such as archiving it.
    """
    owner_token = make_clerk_token(subject="user_owner")
    joiner_token = make_clerk_token(subject="user_joiner")
    organization_id = (await create_org(api_client, owner_token, "Seated Gym"))[
        "organization"
    ]["id"]
    await _materialise_user(api_client, joiner_token)
    joiner_id = await _user_id(db_session, "user_joiner")

    await api_client.post(
        f"/api/v1/organizations/{organization_id}/members",
        json={"user_id": str(joiner_id), "role": "manager"},
        headers=auth_header(owner_token),
    )
    result = await db_session.execute(select(User).where(User.id == joiner_id))
    result.scalar_one().organization_id = uuid.UUID(organization_id)
    await db_session.commit()

    readable = await api_client.get(
        f"/api/v1/organizations/{organization_id}", headers=auth_header(joiner_token)
    )
    forbidden = await api_client.delete(
        f"/api/v1/organizations/{organization_id}", headers=auth_header(joiner_token)
    )

    assert readable.status_code == 200
    assert forbidden.status_code == 403, "tenants:manage is owner-only"


async def test_an_added_owner_is_immediately_functional(
    api_client, make_clerk_token, db_session
):
    """An owner seat without permissions would be a broken state, so it carries its role."""
    owner_token = make_clerk_token(subject="user_owner")
    second_token = make_clerk_token(subject="user_second_owner")
    organization_id = (await create_org(api_client, owner_token, "Co-owned Gym"))[
        "organization"
    ]["id"]
    await _materialise_user(api_client, second_token)
    second_id = await _user_id(db_session, "user_second_owner")

    added = await api_client.post(
        f"/api/v1/organizations/{organization_id}/members",
        json={"user_id": str(second_id), "role": "owner"},
        headers=auth_header(owner_token),
    )
    assert added.status_code == 201, added.text

    result = await db_session.execute(select(User).where(User.id == second_id))
    result.scalar_one().organization_id = uuid.UUID(organization_id)
    await db_session.commit()

    response = await api_client.get(
        f"/api/v1/organizations/{organization_id}", headers=auth_header(second_token)
    )

    assert response.status_code == 200
