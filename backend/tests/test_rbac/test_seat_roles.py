"""
Seat-to-role auto-assignment.

Membership answers "which tenant"; RBAC answers "what may you do". This is the
one bridge between them: every seat carries the same-named system role, so a new
member is usable the moment they are added.
"""

import uuid

import pytest
from sqlalchemy import func, select

from app.modules.auth.models import User
from app.modules.rbac.models import Role, UserRole
from app.modules.rbac.service import (
    SYSTEM_ROLE_BY_SLUG,
    user_has_permission,
)
from tests.test_tenants.test_organizations import auth_header, create_org


async def _user_id(db_session, clerk_user_id: str) -> uuid.UUID:
    result = await db_session.execute(
        select(User.id).where(User.clerk_user_id == clerk_user_id)
    )
    return result.scalar_one()


async def _materialise(api_client, token: str) -> None:
    assert (
        await api_client.get("/api/v1/auth/me", headers=auth_header(token))
    ).status_code == 200


async def _seat_roles(db_session, *, user_id, organization_id) -> set[str]:
    result = await db_session.execute(
        select(Role.slug)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.user_id == user_id,
            UserRole.organization_id == organization_id,
            Role.is_system.is_(True),
        )
    )
    return set(result.scalars())


@pytest.fixture
async def gym(api_client, make_clerk_token, db_session):
    """An organization with an owner and a second user available to be seated."""
    owner_token = make_clerk_token(subject="user_owner")
    joiner_token = make_clerk_token(subject="user_joiner")
    data = await create_org(api_client, owner_token, "Catalogue Gym")
    await _materialise(api_client, joiner_token)

    return {
        "owner_token": owner_token,
        "joiner_token": joiner_token,
        "org": data["organization"]["id"],
        "owner_id": await _user_id(db_session, "user_owner"),
        "joiner_id": await _user_id(db_session, "user_joiner"),
    }


async def _add_member(api_client, gym, seat: str):
    return await api_client.post(
        f"/api/v1/organizations/{gym['org']}/members",
        json={"user_id": str(gym["joiner_id"]), "role": seat},
        headers=auth_header(gym["owner_token"]),
    )


# --------------------------------------------------------------------------- #
# Assignment
# --------------------------------------------------------------------------- #


async def test_provisioning_grants_the_owner_seat_role(gym, db_session):
    roles = await _seat_roles(
        db_session, user_id=gym["owner_id"], organization_id=uuid.UUID(gym["org"])
    )

    assert roles == {"owner"}


@pytest.mark.parametrize("seat", ["admin", "manager", "trainer", "staff", "member"])
async def test_adding_a_member_grants_the_matching_role(
    gym, api_client, db_session, seat
):
    response = await _add_member(api_client, gym, seat)
    assert response.status_code == 201, response.text

    roles = await _seat_roles(
        db_session, user_id=gym["joiner_id"], organization_id=uuid.UUID(gym["org"])
    )
    assert roles == {seat}


@pytest.mark.parametrize(
    "seat", ["owner", "admin", "manager", "trainer", "staff", "member"]
)
async def test_the_granted_role_carries_its_defined_permissions(
    gym, api_client, db_session, seat
):
    """The bridge must grant the catalogue's permissions, not an empty role."""
    await _add_member(api_client, gym, seat)
    organization_id = uuid.UUID(gym["org"])
    expected = set(SYSTEM_ROLE_BY_SLUG[seat].permission_codes)

    for code in expected:
        assert await user_has_permission(
            db_session,
            user_id=gym["joiner_id"],
            organization_id=organization_id,
            permission_code=code,
        ), f"{seat} should hold {code}"

    for code in set(SYSTEM_ROLE_BY_SLUG["owner"].permission_codes) - expected:
        assert not await user_has_permission(
            db_session,
            user_id=gym["joiner_id"],
            organization_id=organization_id,
            permission_code=code,
        ), f"{seat} should not hold {code}"


async def test_a_new_member_can_immediately_use_the_api(gym, api_client, db_session):
    """The gap this closes: a seated member used to be able to do nothing."""
    await _add_member(api_client, gym, "manager")
    result = await db_session.execute(select(User).where(User.id == gym["joiner_id"]))
    result.scalar_one().organization_id = uuid.UUID(gym["org"])
    await db_session.commit()

    response = await api_client.get(
        f"/api/v1/organizations/{gym['org']}",
        headers=auth_header(gym["joiner_token"]),
    )

    assert response.status_code == 200


# --------------------------------------------------------------------------- #
# Seat changes
# --------------------------------------------------------------------------- #


async def test_changing_a_seat_replaces_the_role(gym, api_client, db_session):
    await _add_member(api_client, gym, "staff")

    response = await api_client.patch(
        f"/api/v1/organizations/{gym['org']}/members/{gym['joiner_id']}",
        json={"role": "trainer"},
        headers=auth_header(gym["owner_token"]),
    )
    assert response.status_code == 200

    roles = await _seat_roles(
        db_session, user_id=gym["joiner_id"], organization_id=uuid.UUID(gym["org"])
    )
    assert roles == {"trainer"}, "the previous seat's role must not linger"


async def test_a_demotion_actually_removes_permissions(gym, api_client, db_session):
    await _add_member(api_client, gym, "admin")
    organization_id = uuid.UUID(gym["org"])
    assert await user_has_permission(
        db_session,
        user_id=gym["joiner_id"],
        organization_id=organization_id,
        permission_code="billing:manage",
    )

    await api_client.patch(
        f"/api/v1/organizations/{gym['org']}/members/{gym['joiner_id']}",
        json={"role": "trainer"},
        headers=auth_header(gym["owner_token"]),
    )

    assert not await user_has_permission(
        db_session,
        user_id=gym["joiner_id"],
        organization_id=organization_id,
        permission_code="billing:manage",
    )


async def test_removing_a_member_revokes_their_permissions(gym, api_client, db_session):
    await _add_member(api_client, gym, "admin")
    organization_id = uuid.UUID(gym["org"])

    await api_client.delete(
        f"/api/v1/organizations/{gym['org']}/members/{gym['joiner_id']}",
        headers=auth_header(gym["owner_token"]),
    )

    roles = await _seat_roles(
        db_session, user_id=gym["joiner_id"], organization_id=organization_id
    )
    assert roles == set()
    assert not await user_has_permission(
        db_session,
        user_id=gym["joiner_id"],
        organization_id=organization_id,
        permission_code="membership:manage",
    )


async def test_a_custom_role_survives_a_seat_change(gym, api_client, db_session):
    """Seat sync touches system roles only; bespoke grants are the tenant's own."""
    await _add_member(api_client, gym, "staff")

    created = await api_client.post(
        "/api/v1/rbac/roles",
        json={"name": "Weekend Cover", "permission_codes": ["expenses:read"]},
        headers=auth_header(gym["owner_token"]),
    )
    assert created.status_code == 201, created.text
    custom_role_id = created.json()["data"]["id"]

    assigned = await api_client.post(
        f"/api/v1/rbac/users/{gym['joiner_id']}/roles",
        json={"role_id": custom_role_id},
        headers=auth_header(gym["owner_token"]),
    )
    assert assigned.status_code == 204, assigned.text

    await api_client.patch(
        f"/api/v1/organizations/{gym['org']}/members/{gym['joiner_id']}",
        json={"role": "trainer"},
        headers=auth_header(gym["owner_token"]),
    )

    result = await db_session.execute(
        select(func.count())
        .select_from(UserRole)
        .where(
            UserRole.user_id == gym["joiner_id"],
            UserRole.role_id == uuid.UUID(custom_role_id),
        )
    )
    assert result.scalar_one() == 1


# --------------------------------------------------------------------------- #
# Tenant scoping of a shared role
# --------------------------------------------------------------------------- #


async def test_a_shared_role_does_not_leak_across_tenants(
    api_client, make_clerk_token, db_session
):
    """
    System roles are global rows; the assignment is what carries the tenant.

    Holding admin in Organization A must confer nothing in Organization B.
    """
    token_a = make_clerk_token(subject="user_a")
    token_b = make_clerk_token(subject="user_b")
    org_a = (await create_org(api_client, token_a, "Gym A"))["organization"]["id"]
    org_b = (await create_org(api_client, token_b, "Gym B"))["organization"]["id"]
    user_a = await _user_id(db_session, "user_a")

    assert await user_has_permission(
        db_session,
        user_id=user_a,
        organization_id=uuid.UUID(org_a),
        permission_code="billing:manage",
    )
    assert not await user_has_permission(
        db_session,
        user_id=user_a,
        organization_id=uuid.UUID(org_b),
        permission_code="billing:manage",
    ), "a global role must not grant access in another tenant"


async def test_the_same_user_can_hold_different_seats_in_two_tenants(
    api_client, make_clerk_token, db_session
):
    token_a = make_clerk_token(subject="user_a")
    token_b = make_clerk_token(subject="user_b")
    org_a = (await create_org(api_client, token_a, "Gym A"))["organization"]["id"]
    org_b = (await create_org(api_client, token_b, "Gym B"))["organization"]["id"]
    user_a = await _user_id(db_session, "user_a")

    added = await api_client.post(
        f"/api/v1/organizations/{org_b}/members",
        json={"user_id": str(user_a), "role": "trainer"},
        headers=auth_header(token_b),
    )
    assert added.status_code == 201, added.text

    assert await _seat_roles(
        db_session, user_id=user_a, organization_id=uuid.UUID(org_a)
    ) == {"owner"}
    assert await _seat_roles(
        db_session, user_id=user_a, organization_id=uuid.UUID(org_b)
    ) == {"trainer"}

    # Owner in A, trainer in B: the trainer seat must not inherit A's reach.
    assert not await user_has_permission(
        db_session,
        user_id=user_a,
        organization_id=uuid.UUID(org_b),
        permission_code="billing:manage",
    )


async def test_joining_a_second_tenant_does_not_move_the_active_pointer(
    api_client, make_clerk_token, db_session
):
    token_a = make_clerk_token(subject="user_a")
    token_b = make_clerk_token(subject="user_b")
    org_a = (await create_org(api_client, token_a, "Gym A"))["organization"]["id"]
    org_b = (await create_org(api_client, token_b, "Gym B"))["organization"]["id"]
    user_a = await _user_id(db_session, "user_a")

    await api_client.post(
        f"/api/v1/organizations/{org_b}/members",
        json={"user_id": str(user_a), "role": "manager"},
        headers=auth_header(token_b),
    )

    result = await db_session.execute(
        select(User.organization_id).where(User.id == user_a)
    )
    assert result.scalar_one() == uuid.UUID(org_a)
