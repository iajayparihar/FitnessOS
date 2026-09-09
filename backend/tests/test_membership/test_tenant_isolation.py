"""Tenant isolation of the authorization layer, across organizations."""

from app.modules.auth.context import build_authenticated_context
from app.modules.rbac.service import user_has_permission
from tests.factories.tenant_factory import create_organization, make_owner
from tests.factories.user_factory import create_clerk_user


async def test_permissions_do_not_cross_organizations(db_session):
    """An owner of org A must hold no permission inside org B."""
    org_a = await create_organization(db_session, name="Gym A")
    org_b = await create_organization(db_session, name="Gym B")
    user_a = await create_clerk_user(db_session, organization_id=org_a.id)
    await make_owner(db_session, user_id=user_a.id, organization_id=org_a.id)

    assert await user_has_permission(
        db_session,
        user_id=user_a.id,
        organization_id=org_a.id,
        permission_code="membership:manage",
    )
    assert not await user_has_permission(
        db_session,
        user_id=user_a.id,
        organization_id=org_b.id,
        permission_code="membership:manage",
    )


async def test_context_is_scoped_to_the_users_own_tenant(db_session):
    org_a = await create_organization(db_session, name="Gym A")
    org_b = await create_organization(db_session, name="Gym B")
    user_a = await create_clerk_user(db_session, organization_id=org_a.id)
    await make_owner(db_session, user_id=user_a.id, organization_id=org_a.id)

    context = await build_authenticated_context(db_session, user=user_a)

    assert context.organization_id == org_a.id
    assert context.owns_organization(org_a.id)
    assert not context.owns_organization(org_b.id)
    assert not context.owns_organization(None)


async def test_a_user_without_a_tenant_holds_no_permissions(db_session):
    user = await create_clerk_user(db_session, organization_id=None)

    context = await build_authenticated_context(db_session, user=user)

    assert context.organization_id is None
    assert context.permissions == frozenset()
    assert context.role_slugs == ()
    assert not context.has_permission("membership:manage")


async def test_a_superuser_is_not_confined_to_one_tenant(db_session):
    org_b = await create_organization(db_session, name="Gym B")
    superuser = await create_clerk_user(db_session, is_superuser=True)

    context = await build_authenticated_context(db_session, user=superuser)

    assert context.owns_organization(org_b.id)
    assert context.has_permission("billing:manage")
