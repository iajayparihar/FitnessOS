from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tenants.exceptions import OrgNotFound
from app.modules.tenants.models import Organization
from app.modules.tenants.schemas import OrgCreate


def make_slug(value: str) -> str:
    """Create a normalized organization slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "organization"


async def get_org_by_id(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
) -> Organization:
    """Return one active, non-deleted organization by id."""
    result = await db.execute(
        select(Organization).where(
            Organization.id == organization_id,
            Organization.deleted_at.is_(None),
        )
    )
    organization = result.scalar_one_or_none()
    if organization is None:
        raise OrgNotFound
    return organization


async def create_org(
    db: AsyncSession,
    *,
    payload: OrgCreate,
    created_by: uuid.UUID | None = None,
) -> Organization:
    """Create an organization tenant."""
    organization = Organization(
        name=payload.name.strip(),
        slug=make_slug(payload.slug or payload.name),
        industry=payload.industry,
        settings=payload.settings,
        branding=payload.branding,
        billing_contact=payload.billing_contact,
        data_region=payload.data_region,
        created_by=created_by,
        updated_by=created_by,
    )
    db.add(organization)
    await db.flush()
    await db.refresh(organization)
    return organization


async def ensure_slug_available(
    db: AsyncSession,
    *,
    slug: str,
) -> None:
    """Raise ValueError when an organization slug is already taken."""
    result = await db.execute(
        select(Organization.id).where(
            func.lower(Organization.slug) == slug.lower(),
            Organization.deleted_at.is_(None),
        )
    )
    if result.scalar_one_or_none() is not None:
        raise ValueError("Organization slug is already in use.")
