"""The system role catalogue: seeding, permission sets and escalation guards."""

import pytest
from sqlalchemy import func, select

from app.core.enums import OrganizationMemberRole
from app.modules.rbac.models import Permission, Role, RolePermission
from app.modules.rbac.service import (
    ALL_PERMISSION_CODES,
    DEFAULT_PERMISSIONS,
    SYSTEM_ROLE_BY_SLUG,
    SYSTEM_ROLE_DEFINITIONS,
    ensure_owner_role,
    get_system_role,
    seed_system_roles,
)

# --------------------------------------------------------------------------- #
# Catalogue shape
# --------------------------------------------------------------------------- #


def test_every_membership_seat_has_a_system_role():
    """A seat with no matching role would grant nothing on assignment."""
    seats = {seat.value for seat in OrganizationMemberRole}

    assert seats == set(SYSTEM_ROLE_BY_SLUG)


def test_every_referenced_permission_exists():
    """A typo in a role definition would silently narrow that role."""
    known = set(ALL_PERMISSION_CODES)

    for definition in SYSTEM_ROLE_DEFINITIONS:
        unknown = set(definition.permission_codes) - known
        assert not unknown, f"{definition.slug} references {unknown}"


def test_permission_codes_are_unique():
    codes = [code for code, _, _ in DEFAULT_PERMISSIONS]

    assert len(codes) == len(set(codes))


def test_owner_holds_every_permission():
    assert set(SYSTEM_ROLE_BY_SLUG["owner"].permission_codes) == set(
        ALL_PERMISSION_CODES
    )


@pytest.mark.parametrize("slug", ["admin", "manager", "trainer", "staff", "member"])
def test_only_the_owner_can_manage_roles(slug):
    """
    rbac:manage is equivalent to ownership.

    Anyone who can edit roles can grant themselves any permission, so holding it
    below owner would make the whole catalogue decorative.
    """
    assert "rbac:manage" not in SYSTEM_ROLE_BY_SLUG[slug].permission_codes


@pytest.mark.parametrize("slug", ["admin", "manager", "trainer", "staff", "member"])
def test_only_the_owner_can_change_the_organization_or_its_subscription(slug):
    codes = SYSTEM_ROLE_BY_SLUG[slug].permission_codes

    assert "tenants:manage" not in codes
    assert "subscriptions:manage" not in codes


def test_seats_are_ordered_by_breadth():
    """Each seat should be a superset of the trust placed in the ones below it."""
    sizes = [
        len(SYSTEM_ROLE_BY_SLUG[slug].permission_codes)
        for slug in ("owner", "admin", "manager", "staff", "trainer", "member")
    ]

    assert sizes == sorted(sizes, reverse=True), sizes


def test_opening_a_branch_is_separate_from_organization_lifecycle():
    """
    Adding a location is routine business; archiving the tenant is not.

    Bundling both under tenants:manage would have left an Admin unable to open a
    new branch, which multi-branch operators need every day.
    """
    admin = set(SYSTEM_ROLE_BY_SLUG["admin"].permission_codes)

    assert "branches:manage" in admin
    assert "tenants:manage" not in admin


def test_only_owner_and_admin_open_new_locations():
    for slug in ("manager", "trainer", "staff", "member"):
        assert "branches:manage" not in SYSTEM_ROLE_BY_SLUG[slug].permission_codes


def test_working_seats_can_see_the_branch_list():
    """Front-desk and coaching staff must know which locations exist."""
    for slug in ("admin", "manager", "trainer", "staff"):
        assert "branches:read" in SYSTEM_ROLE_BY_SLUG[slug].permission_codes


def test_member_holds_no_organization_wide_reads():
    """
    Permissions are organization-wide, so a gym-goer must hold almost none.

    Granting membership:read here would expose the whole member list to every
    member; self-service needs object-level scoping that does not exist yet.
    """
    codes = set(SYSTEM_ROLE_BY_SLUG["member"].permission_codes)

    assert codes == {"tenants:read"}


def test_trainers_cannot_reach_money_or_staff_administration():
    codes = set(SYSTEM_ROLE_BY_SLUG["trainer"].permission_codes)

    for forbidden in (
        "billing:read",
        "billing:manage",
        "users:manage",
        "expenses:read",
    ):
        assert forbidden not in codes


def test_front_desk_cannot_move_money():
    codes = set(SYSTEM_ROLE_BY_SLUG["staff"].permission_codes)

    assert "billing:read" in codes
    assert "billing:manage" not in codes


# --------------------------------------------------------------------------- #
# Seeding
# --------------------------------------------------------------------------- #


async def test_seeding_creates_global_roles(db_session):
    roles = await seed_system_roles(db_session)
    await db_session.commit()

    assert set(roles) == set(SYSTEM_ROLE_BY_SLUG)
    for role in roles.values():
        assert role.organization_id is None, "system roles are not per-tenant"
        assert role.is_system is True


async def test_seeding_is_idempotent(db_session):
    await seed_system_roles(db_session)
    await db_session.commit()
    await seed_system_roles(db_session)
    await db_session.commit()

    count = await db_session.execute(
        select(func.count()).select_from(Role).where(Role.is_system.is_(True))
    )
    assert count.scalar_one() == len(SYSTEM_ROLE_DEFINITIONS)


async def test_seeding_grants_exactly_the_defined_permissions(db_session):
    roles = await seed_system_roles(db_session)
    await db_session.commit()

    for slug, definition in SYSTEM_ROLE_BY_SLUG.items():
        result = await db_session.execute(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(
                RolePermission.role_id == roles[slug].id,
                RolePermission.granted.is_(True),
            )
        )
        assert set(result.scalars()) == set(definition.permission_codes), slug


async def test_seeding_revokes_permissions_dropped_from_a_definition(db_session):
    """The catalogue in code is the source of truth, not the database."""
    roles = await seed_system_roles(db_session)
    stray = await db_session.execute(
        select(Permission).where(Permission.code == "billing:manage")
    )
    db_session.add(
        RolePermission(
            role_id=roles["member"].id,
            permission_id=stray.scalar_one().id,
            granted=True,
        )
    )
    await db_session.commit()

    await seed_system_roles(db_session)
    await db_session.commit()

    result = await db_session.execute(
        select(func.count())
        .select_from(RolePermission)
        .where(RolePermission.role_id == roles["member"].id)
    )
    assert result.scalar_one() == 1


async def test_get_system_role_seeds_on_demand(db_session):
    role = await get_system_role(db_session, slug="manager")
    await db_session.commit()

    assert role is not None
    assert role.slug == "manager"


async def test_get_system_role_rejects_unknown_slugs(db_session):
    assert await get_system_role(db_session, slug="superuser") is None


async def test_ensure_owner_role_returns_the_shared_system_role(db_session):
    """The legacy helper must no longer mint a per-organization copy."""
    role = await ensure_owner_role(db_session)
    await db_session.commit()

    assert role.organization_id is None
    assert role.is_system is True
    assert role.slug == "owner"


async def test_one_role_row_serves_every_organization(
    db_session, api_client, make_clerk_token
):
    """Scale check: roles are not copied per tenant."""
    from tests.test_tenants.test_organizations import create_org

    for index in range(3):
        await create_org(
            api_client, make_clerk_token(subject=f"user_{index}"), f"Gym {index}"
        )

    result = await db_session.execute(
        select(func.count()).select_from(Role).where(Role.deleted_at.is_(None))
    )
    assert result.scalar_one() == len(SYSTEM_ROLE_DEFINITIONS)
