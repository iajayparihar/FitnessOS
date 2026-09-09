"""Tenant isolation for billing-scoped permissions."""

from app.modules.rbac.service import user_has_permission
from tests.factories.tenant_factory import create_organization, make_owner
from tests.factories.user_factory import create_clerk_user


async def test_billing_permission_does_not_cross_organizations(db_session):
    org_a = await create_organization(db_session, name="Billing Gym A")
    org_b = await create_organization(db_session, name="Billing Gym B")
    owner_a = await create_clerk_user(db_session, organization_id=org_a.id)
    owner_b = await create_clerk_user(db_session, organization_id=org_b.id)
    await make_owner(db_session, user_id=owner_a.id, organization_id=org_a.id)
    await make_owner(db_session, user_id=owner_b.id, organization_id=org_b.id)

    assert await user_has_permission(
        db_session,
        user_id=owner_a.id,
        organization_id=org_a.id,
        permission_code="billing:manage",
    )
    assert not await user_has_permission(
        db_session,
        user_id=owner_a.id,
        organization_id=org_b.id,
        permission_code="billing:manage",
    )
