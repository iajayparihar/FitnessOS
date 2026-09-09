"""Factories for organization tenants, memberships and branches."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OrganizationMemberRole, OrganizationMemberStatus
from app.modules.auth.models import User
from app.modules.tenants.models import Organization, OrganizationMembership
from app.modules.tenants.schemas import OrgProvisionRequest
from app.modules.tenants.service import provision_organization, sync_seat_rbac_role


async def create_organization(
    db: AsyncSession,
    *,
    name: str,
    slug: str | None = None,
) -> Organization:
    """Create a bare organization row, without memberships or branches."""
    organization = Organization(
        name=name,
        slug=slug or name.lower().replace(" ", "-"),
    )
    db.add(organization)
    await db.commit()
    return organization


async def provision_tenant(
    db: AsyncSession,
    *,
    user: User,
    name: str,
    **overrides,
) -> tuple[Organization, OrganizationMembership, object]:
    """Provision a complete tenant the same way the API does."""
    payload = OrgProvisionRequest(name=name, **overrides)
    return await provision_organization(db, user=user, payload=payload)


async def add_member(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role: OrganizationMemberRole = OrganizationMemberRole.STAFF,
    status: OrganizationMemberStatus = OrganizationMemberStatus.ACTIVE,
) -> OrganizationMembership:
    """Attach a user to an organization and point them at it."""
    membership = OrganizationMembership(
        organization_id=organization_id,
        user_id=user_id,
        role=role,
        status=status,
    )
    db.add(membership)
    await db.commit()
    return membership


async def seat_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    seat: OrganizationMemberRole = OrganizationMemberRole.STAFF,
) -> OrganizationMembership:
    """
    Give a user a membership seat and the system role that comes with it.

    Mirrors what the members API does, so factory-built fixtures behave the same
    way as data created through HTTP.
    """
    membership = await add_member(
        db, organization_id=organization_id, user_id=user_id, role=seat
    )
    await sync_seat_rbac_role(
        db,
        organization_id=organization_id,
        user_id=user_id,
        seat=seat,
        actor_id=user_id,
    )
    await db.commit()
    return membership


async def make_owner(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> None:
    """Seat a user as owner, with the membership and role that implies."""
    await seat_user(
        db,
        user_id=user_id,
        organization_id=organization_id,
        seat=OrganizationMemberRole.OWNER,
    )
