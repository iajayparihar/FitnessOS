"""
Tenant resolution dependencies.

The organization a request operates in is derived from the authenticated user's
membership. It is never read from a request body, query string or path
parameter, so a caller cannot nominate a tenant they do not belong to.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OrganizationStatus
from app.core.tenancy import TenantContext, set_tenant_context
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.rbac.exceptions import PermissionDenied
from app.modules.rbac.service import ensure_user_has_permission
from app.modules.tenants.exceptions import OrgNotFound
from app.modules.tenants.models import Organization, OrganizationMembership
from app.modules.tenants.service import get_active_membership, get_org_by_id

logger = logging.getLogger("app.tenants")

# Cross-tenant and no-membership cases answer with the same message a genuinely
# missing organization gets, so response codes cannot be used to probe which
# organization ids exist.
ORGANIZATION_NOT_FOUND = "Organization not found."


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=ORGANIZATION_NOT_FOUND,
    )


async def get_current_membership(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMembership:
    """
    Resolve the caller's membership in their active organization.

    ``users.organization_id`` is only a pointer to which organization the user is
    currently working in. It is re-validated against a live membership on every
    request, so revoking a membership takes effect immediately and a stale
    pointer grants nothing.
    """
    if current_user.organization_id is None:
        raise _not_found()

    membership = await get_active_membership(
        db,
        user_id=current_user.id,
        organization_id=current_user.organization_id,
    )
    if membership is None:
        logger.info(
            "tenant.membership_missing",
            extra={
                "user_id": str(current_user.id),
                "organization_id": str(current_user.organization_id),
            },
        )
        raise _not_found()
    return membership


async def get_current_organization(
    membership: OrganizationMembership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    """Resolve the organization the caller is currently operating in."""
    try:
        return await get_org_by_id(db, organization_id=membership.organization_id)
    except OrgNotFound as exc:
        raise _not_found() from exc


async def get_tenant_context(
    current_user: User = Depends(get_current_user),
    membership: OrganizationMembership = Depends(get_current_membership),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    """
    Build the request's tenant context and bind it to the transaction.

    Suspended, cancelled and archived organizations are refused here rather than
    in each endpoint, so no tenant-scoped route can accidentally keep serving a
    tenant that should be frozen.
    """
    if organization.status not in OrganizationStatus.operational():
        logger.info(
            "tenant.not_operational",
            extra={
                "organization_id": str(organization.id),
                "status": organization.status.value,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization is not active.",
        )

    await set_tenant_context(db, organization_id=organization.id)
    return TenantContext(
        user=current_user,
        membership=membership,
        organization=organization,
    )


async def get_current_org(
    organization: Organization = Depends(get_current_organization),
) -> Organization:
    """
    Resolve the current user's organization tenant.

    Retained under its original name for the existing ``/api/v1/tenants``
    endpoints; new code should depend on ``get_tenant_context``.
    """
    return organization


def require_org_permission(permission_code: str) -> Callable:
    """
    Return a dependency requiring an RBAC permission inside the current tenant.

    Authorization stays in the RBAC permission system. Membership decides which
    tenant the request belongs to; permissions decide what may be done in it.
    """

    async def dependency(
        context: TenantContext = Depends(get_tenant_context),
        db: AsyncSession = Depends(get_db),
    ) -> TenantContext:
        if context.user.is_superuser:
            return context

        try:
            await ensure_user_has_permission(
                db,
                user_id=context.user_id,
                organization_id=context.organization_id,
                permission_code=permission_code,
            )
        except PermissionDenied as exc:
            logger.info(
                "tenant.permission_denied",
                extra={
                    "organization_id": str(context.organization_id),
                    "user_id": str(context.user_id),
                    "permission": permission_code,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied.",
            ) from exc
        return context

    return dependency


def resolve_path_organization(
    organization_id: uuid.UUID,
    context: TenantContext = Depends(get_tenant_context),
) -> TenantContext:
    """
    Confirm a path organization_id matches the caller's resolved tenant.

    The path parameter is a routing convenience only. It never selects the
    tenant; a mismatch is answered as "not found" so an authenticated user cannot
    discover which organization ids are real by probing.
    """
    if organization_id != context.organization_id:
        logger.warning(
            "tenant.cross_tenant_denied",
            extra={
                "organization_id": str(context.organization_id),
                "user_id": str(context.user_id),
            },
        )
        raise _not_found()
    return context


def require_path_org_permission(permission_code: str) -> Callable:
    """
    Require that the path tenant is the caller's tenant, then check a permission.

    Order matters. The tenant match is verified first so a request aimed at
    another organization always answers 404, regardless of what the caller may do
    inside their own tenant. Checking the permission first would let a caller
    distinguish "wrong tenant" (404) from "right tenant, no permission" (403) and
    thereby probe which organization ids are real.
    """

    async def dependency(
        organization_id: uuid.UUID,
        context: TenantContext = Depends(get_tenant_context),
        db: AsyncSession = Depends(get_db),
    ) -> TenantContext:
        resolve_path_organization(organization_id, context)

        if context.user.is_superuser:
            return context

        try:
            await ensure_user_has_permission(
                db,
                user_id=context.user_id,
                organization_id=context.organization_id,
                permission_code=permission_code,
            )
        except PermissionDenied as exc:
            logger.info(
                "tenant.permission_denied",
                extra={
                    "organization_id": str(context.organization_id),
                    "user_id": str(context.user_id),
                    "permission": permission_code,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied.",
            ) from exc
        return context

    return dependency
