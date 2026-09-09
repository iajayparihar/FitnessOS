"""Tenant service unit behaviour that does not need the HTTP layer."""

import uuid

import pytest

from app.core.enums import OrganizationMemberRole, OrganizationStatus
from app.core.tenancy import TenantContext
from app.modules.tenants.exceptions import OrgNotFound, SlugUnavailable
from app.modules.tenants.models import Organization, OrganizationMembership
from app.modules.tenants.service import (
    allocate_slug,
    ensure_slug_available,
    get_org_by_id,
    make_slug,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("Ajay Fitness Studio", "ajay-fitness-studio"),
        ("CrossFit Box #7", "crossfit-box-7"),
        ("  spaced  out  ", "spaced-out"),
        ("Ünicode Gym", "nicode-gym"),
        ("", "organization"),
        ("---", "organization"),
    ],
)
def test_make_slug_normalises(value, expected):
    assert make_slug(value) == expected


async def test_allocate_slug_suffixes_on_collision(db_session):
    for slug in ("gym", "gym-2"):
        db_session.add(Organization(name=slug, slug=slug))
    await db_session.commit()

    assert await allocate_slug(db_session, preferred="Gym") == "gym-3"


async def test_ensure_slug_available_raises_for_taken_slugs(db_session):
    db_session.add(Organization(name="Taken", slug="taken"))
    await db_session.commit()

    await ensure_slug_available(db_session, slug="free")
    with pytest.raises(SlugUnavailable):
        await ensure_slug_available(db_session, slug="taken")


async def test_get_org_by_id_hides_soft_deleted_organizations(db_session):
    from sqlalchemy import func

    organization = Organization(name="Gone", slug="gone", deleted_at=func.now())
    db_session.add(organization)
    await db_session.commit()

    with pytest.raises(OrgNotFound):
        await get_org_by_id(db_session, organization_id=organization.id)


def test_tenant_context_rejects_other_tenants():
    context = TenantContext(
        user=object(),
        membership=OrganizationMembership(role=OrganizationMemberRole.OWNER),
        organization=Organization(id=uuid.uuid4()),
    )

    assert context.owns(context.organization_id)
    assert not context.owns(uuid.uuid4())
    assert not context.owns(None)
    assert context.is_owner


def test_only_operational_statuses_permit_tenant_work():
    assert OrganizationStatus.ACTIVE in OrganizationStatus.operational()
    assert OrganizationStatus.PENDING in OrganizationStatus.operational()
    for frozen in (
        OrganizationStatus.SUSPENDED,
        OrganizationStatus.CANCELLED,
        OrganizationStatus.ARCHIVED,
    ):
        assert frozen not in OrganizationStatus.operational()
