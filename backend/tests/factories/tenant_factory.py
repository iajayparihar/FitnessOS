"""Factories for organization tenants and their owner role."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.rbac.service import assign_role_to_user, ensure_owner_role
from app.modules.tenants.models import Organization


async def create_organization(
    db: AsyncSession,
    *,
    name: str,
    slug: str | None = None,
) -> Organization:
    """Create an organization tenant."""
    organization = Organization(
        name=name,
        slug=slug or name.lower().replace(" ", "-"),
    )
    db.add(organization)
    await db.commit()
    return organization


async def make_owner(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> None:
    """Grant a user the owner role inside an organization."""
    owner_role = await ensure_owner_role(db, organization_id=organization_id)
    await assign_role_to_user(
        db,
        user_id=user_id,
        role_id=owner_role.id,
        organization_id=organization_id,
    )
    await db.commit()
