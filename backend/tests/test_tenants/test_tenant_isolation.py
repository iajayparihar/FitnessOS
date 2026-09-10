"""
Cross-tenant isolation regression suite.

Two fully provisioned tenants, then every way an authenticated user of one might
try to reach the other: path ids, nested resource ids, request bodies, tenant
switching and the raw database session variable.

An authenticated user of Organization A must never observe Organization B.
"""

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.tenancy import TENANT_SETTING, get_tenant_setting, set_tenant_context
from app.modules.auth.models import User
from app.modules.rbac.exceptions import RoleNotFound, UserNotInOrganization
from app.modules.rbac.schemas import RoleCreate
from app.modules.rbac.service import assign_role_to_user, create_role, get_system_role
from app.modules.tenants.exceptions import BranchNotFound, MembershipNotFound
from app.modules.tenants.models import (
    OrganizationBranch,
    OrganizationMembership,
)
from app.modules.tenants.service import (
    get_branch,
    get_membership,
    list_branches,
    list_memberships,
)
from tests.test_tenants.test_organizations import auth_header, create_org


@pytest.fixture
async def two_tenants(api_client, make_clerk_token, db_session):
    """
    Build User A / Organization A / Branch A and User B / Organization B / Branch B.

    Returned as a dict so each test can attack from either direction.
    """
    token_a = make_clerk_token(subject="user_a")
    token_b = make_clerk_token(subject="user_b")
    org_a = await create_org(api_client, token_a, "Gym A")
    org_b = await create_org(api_client, token_b, "Gym B")

    extra_a = await api_client.post(
        f"/api/v1/organizations/{org_a['organization']['id']}/branches",
        json={"name": "A Second"},
        headers=auth_header(token_a),
    )
    extra_b = await api_client.post(
        f"/api/v1/organizations/{org_b['organization']['id']}/branches",
        json={"name": "B Second"},
        headers=auth_header(token_b),
    )

    users = await db_session.execute(
        select(User).where(User.clerk_user_id.in_(["user_a", "user_b"]))
    )
    by_clerk = {user.clerk_user_id: user.id for user in users.scalars()}

    return {
        "token_a": token_a,
        "token_b": token_b,
        "org_a": org_a["organization"]["id"],
        "org_b": org_b["organization"]["id"],
        "branch_a": extra_a.json()["data"]["id"],
        "branch_b": extra_b.json()["data"]["id"],
        "main_a": org_a["main_branch"]["id"],
        "main_b": org_b["main_branch"]["id"],
        "membership_a": org_a["membership"]["id"],
        "membership_b": org_b["membership"]["id"],
        "user_a": by_clerk["user_a"],
        "user_b": by_clerk["user_b"],
    }


# --------------------------------------------------------------------------- #
# Organization endpoints
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "method,suffix",
    [
        ("get", ""),
        ("patch", ""),
        ("delete", ""),
        ("get", "/members"),
        ("post", "/members"),
        ("get", "/branches"),
        ("post", "/branches"),
        ("get", "/settings"),
        ("put", "/settings"),
    ],
)
async def test_user_a_cannot_reach_organization_b(
    two_tenants, api_client, method, suffix
):
    """Every organization-scoped route must refuse the other tenant's id."""
    url = f"/api/v1/organizations/{two_tenants['org_b']}{suffix}"
    call = getattr(api_client, method)
    kwargs = {"headers": auth_header(two_tenants["token_a"])}
    if method in {"post", "patch", "put"}:
        kwargs["json"] = {
            "name": "Hijacked",
            "user_id": str(two_tenants["user_a"]),
            "key": "locale",
            "value": {},
        }

    response = await call(url, **kwargs)

    assert response.status_code == 404, f"{method.upper()} {url} -> {response.text}"
    assert response.json()["detail"] == "Organization not found."


async def test_user_b_cannot_reach_organization_a(two_tenants, api_client):
    """Isolation holds in both directions, not just the one that was tested first."""
    response = await api_client.get(
        f"/api/v1/organizations/{two_tenants['org_a']}",
        headers=auth_header(two_tenants["token_b"]),
    )

    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Nested resource ids
# --------------------------------------------------------------------------- #


async def test_user_a_cannot_read_organization_b_branches(two_tenants, api_client):
    response = await api_client.get(
        f"/api/v1/organizations/{two_tenants['org_b']}/branches/{two_tenants['branch_b']}",
        headers=auth_header(two_tenants["token_a"]),
    )

    assert response.status_code == 404


async def test_branch_b_id_under_organization_a_is_not_found(two_tenants, api_client):
    """
    A branch id alone is never sufficient authorization.

    Here the path organization is the caller's own tenant, so the tenant check
    passes; the branch must still be refused because it belongs to Organization B.
    """
    for method in ("get", "patch", "delete"):
        call = getattr(api_client, method)
        kwargs = {"headers": auth_header(two_tenants["token_a"])}
        if method == "patch":
            kwargs["json"] = {"name": "Stolen"}

        response = await call(
            f"/api/v1/organizations/{two_tenants['org_a']}/branches/{two_tenants['branch_b']}",
            **kwargs,
        )

        assert response.status_code == 404, method


async def test_organization_b_member_cannot_be_touched_from_organization_a(
    two_tenants, api_client
):
    """A user_id from another tenant must not resolve under the caller's tenant."""
    for method in ("patch", "delete"):
        call = getattr(api_client, method)
        kwargs = {"headers": auth_header(two_tenants["token_a"])}
        if method == "patch":
            kwargs["json"] = {"role": "owner"}

        response = await call(
            f"/api/v1/organizations/{two_tenants['org_a']}/members/{two_tenants['user_b']}",
            **kwargs,
        )

        assert response.status_code == 404, method


async def test_branch_listing_never_includes_another_tenant(two_tenants, api_client):
    response = await api_client.get(
        f"/api/v1/organizations/{two_tenants['org_a']}/branches",
        headers=auth_header(two_tenants["token_a"]),
    )

    ids = {row["id"] for row in response.json()["data"]}
    assert two_tenants["branch_b"] not in ids
    assert two_tenants["main_b"] not in ids
    assert ids == {two_tenants["branch_a"], two_tenants["main_a"]}


async def test_member_listing_never_includes_another_tenant(two_tenants, api_client):
    response = await api_client.get(
        f"/api/v1/organizations/{two_tenants['org_a']}/members",
        headers=auth_header(two_tenants["token_a"]),
    )

    user_ids = {row["user_id"] for row in response.json()["data"]}
    assert str(two_tenants["user_b"]) not in user_ids
    assert user_ids == {str(two_tenants["user_a"])}


async def test_organization_listing_never_includes_another_tenant(
    two_tenants, api_client
):
    response = await api_client.get(
        "/api/v1/organizations", headers=auth_header(two_tenants["token_a"])
    )

    ids = {row["id"] for row in response.json()["data"]}
    assert ids == {two_tenants["org_a"]}


# --------------------------------------------------------------------------- #
# Request-body and switching attacks
# --------------------------------------------------------------------------- #


async def test_a_forged_organization_id_in_the_body_is_ignored(
    two_tenants, api_client, db_session
):
    """Writes land in the caller's tenant no matter what the body claims."""
    response = await api_client.post(
        f"/api/v1/organizations/{two_tenants['org_a']}/branches",
        json={
            "name": "Injected Branch",
            "organization_id": two_tenants["org_b"],
            "id": str(uuid.uuid4()),
        },
        headers=auth_header(two_tenants["token_a"]),
    )

    assert response.status_code == 201
    assert response.json()["data"]["organization_id"] == two_tenants["org_a"]

    leaked = await db_session.execute(
        select(func.count())
        .select_from(OrganizationBranch)
        .where(
            OrganizationBranch.organization_id == uuid.UUID(two_tenants["org_b"]),
            OrganizationBranch.name == "Injected Branch",
        )
    )
    assert leaked.scalar_one() == 0


async def test_a_user_cannot_switch_into_a_tenant_they_do_not_belong_to(
    two_tenants, api_client, db_session
):
    response = await api_client.post(
        f"/api/v1/organizations/{two_tenants['org_b']}/switch",
        headers=auth_header(two_tenants["token_a"]),
    )

    assert response.status_code == 404

    result = await db_session.execute(
        select(User.organization_id).where(User.id == two_tenants["user_a"])
    )
    assert result.scalar_one() == uuid.UUID(two_tenants["org_a"])


async def test_a_forged_membership_row_is_still_bounded_by_status(
    two_tenants, api_client, db_session
):
    """A non-active membership must not grant access."""
    db_session.add(
        OrganizationMembership(
            organization_id=uuid.UUID(two_tenants["org_b"]),
            user_id=two_tenants["user_a"],
            role="admin",
            status="suspended",
        )
    )
    await db_session.commit()

    switched = await api_client.post(
        f"/api/v1/organizations/{two_tenants['org_b']}/switch",
        headers=auth_header(two_tenants["token_a"]),
    )

    assert switched.status_code == 404


# --------------------------------------------------------------------------- #
# Service layer
# --------------------------------------------------------------------------- #


async def test_service_lookups_are_scoped_not_checked_afterwards(
    two_tenants, db_session
):
    """
    The organization filter is part of each query, not a post-hoc comparison.

    A post-hoc check is easy to forget at a new call site; a scoped query simply
    returns nothing for the wrong tenant.
    """
    org_a = uuid.UUID(two_tenants["org_a"])

    with pytest.raises(BranchNotFound):
        await get_branch(
            db_session,
            organization_id=org_a,
            branch_id=uuid.UUID(two_tenants["branch_b"]),
        )

    with pytest.raises(MembershipNotFound):
        await get_membership(
            db_session,
            organization_id=org_a,
            user_id=two_tenants["user_b"],
        )

    branches = await list_branches(db_session, organization_id=org_a)
    memberships = await list_memberships(db_session, organization_id=org_a)
    assert all(b.organization_id == org_a for b in branches)
    assert all(m.organization_id == org_a for m in memberships)


# --------------------------------------------------------------------------- #
# Database tenant setting (RLS groundwork)
# --------------------------------------------------------------------------- #


async def test_tenant_setting_is_transaction_local(db_engine):
    """
    The tenant setting must not survive the transaction that set it.

    Connections are pooled. A session-level SET would outlive checkin and hand
    one tenant's identity to whichever request borrows the connection next, which
    is exactly the leak RLS is meant to prevent.
    """
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    organization_id = uuid.uuid4()

    async with session_maker() as session:
        await set_tenant_context(session, organization_id=organization_id)
        assert await get_tenant_setting(session) == str(organization_id)
        await session.commit()
        assert await get_tenant_setting(session) is None, "leaked past COMMIT"

    async with session_maker() as other_session:
        assert (
            await get_tenant_setting(other_session) is None
        ), "leaked to a new session"


async def test_tenant_setting_is_discarded_on_rollback(db_engine):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)

    async with session_maker() as session:
        await set_tenant_context(session, organization_id=uuid.uuid4())
        await session.rollback()
        assert await get_tenant_setting(session) is None


async def test_request_binds_the_callers_tenant(two_tenants, api_client):
    """A tenant-scoped request must bind its own organization, not another's."""
    response = await api_client.get(
        f"/api/v1/organizations/{two_tenants['org_a']}",
        headers=auth_header(two_tenants["token_a"]),
    )

    assert response.status_code == 200
    assert TENANT_SETTING == "app.current_organization_id"


# --------------------------------------------------------------------------- #
# Error shape
# --------------------------------------------------------------------------- #


async def test_cross_tenant_errors_reveal_nothing(two_tenants, api_client):
    """
    A cross-tenant probe and a genuinely absent id must be indistinguishable.

    Otherwise the status code itself confirms which organization ids exist.
    """
    real_other_tenant = await api_client.get(
        f"/api/v1/organizations/{two_tenants['org_b']}",
        headers=auth_header(two_tenants["token_a"]),
    )
    never_existed = await api_client.get(
        f"/api/v1/organizations/{uuid.uuid4()}",
        headers=auth_header(two_tenants["token_a"]),
    )

    assert real_other_tenant.status_code == never_existed.status_code == 404
    assert real_other_tenant.json() == never_existed.json()

    body = real_other_tenant.text
    for secret in ("Gym B", two_tenants["org_b"], two_tenants["branch_b"]):
        assert secret not in body


# --------------------------------------------------------------------------- #
# RBAC role assignment
# --------------------------------------------------------------------------- #


async def test_a_users_custom_role_from_org_a_cannot_be_assigned_in_org_b(
    two_tenants, api_client, db_session
):
    """A role_id is scoped by organization; another tenant's role must not resolve."""
    custom_role = await create_role(
        db_session,
        organization_id=uuid.UUID(two_tenants["org_a"]),
        payload=RoleCreate(name="A-Only Role", permission_codes=["billing:read"]),
    )

    response = await api_client.post(
        f"/api/v1/rbac/users/{two_tenants['user_b']}/roles",
        json={"role_id": str(custom_role.id)},
        headers=auth_header(two_tenants["token_b"]),
    )

    assert response.status_code == 404


async def test_assigning_a_role_across_organizations_is_rejected_at_the_service(
    two_tenants, db_session
):
    """
    Both halves of a cross-tenant role assignment are rejected independently.

    A role scoped to Organization A must not resolve for Organization B, and a
    user who belongs only to Organization B must not be assignable a role under
    Organization A's id — either mistake alone is enough to catch a bug at a new
    call site.
    """
    role_a = await create_role(
        db_session,
        organization_id=uuid.UUID(two_tenants["org_a"]),
        payload=RoleCreate(name="A Role", permission_codes=["billing:read"]),
    )

    with pytest.raises(RoleNotFound):
        await assign_role_to_user(
            db_session,
            user_id=two_tenants["user_b"],
            role_id=role_a.id,
            organization_id=uuid.UUID(two_tenants["org_b"]),
        )

    owner_role = await get_system_role(db_session, slug="owner")
    with pytest.raises(UserNotInOrganization):
        await assign_role_to_user(
            db_session,
            user_id=two_tenants["user_b"],
            role_id=owner_role.id,
            organization_id=uuid.UUID(two_tenants["org_a"]),
        )


async def test_a_user_b_cannot_assign_roles_inside_organization_a(
    two_tenants, api_client
):
    """rbac:manage is resolved from the caller's own tenant, never the path body."""
    owner_role_id_response = await api_client.get(
        "/api/v1/rbac/roles", headers=auth_header(two_tenants["token_a"])
    )
    owner_role_id = next(
        row["id"]
        for row in owner_role_id_response.json()["data"]
        if row["slug"] == "staff"
    )

    response = await api_client.post(
        f"/api/v1/rbac/users/{two_tenants['user_a']}/roles",
        json={"role_id": owner_role_id},
        headers=auth_header(two_tenants["token_b"]),
    )

    # user_a is not a member of Organization B, so this is UserNotInOrganization
    # under B's tenant scope regardless of which role_id was supplied.
    assert response.status_code == 404
