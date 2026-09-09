from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenancy import TenantContext
from app.db.session import get_db
from app.modules.auth.models import User
from app.modules.rbac.exceptions import PermissionDenied
from app.modules.rbac.service import ensure_user_has_permission


def require_permission(permission_code: str) -> Callable:
    """
    Return a dependency that requires a tenant-scoped permission.

    The tenant comes from the membership-backed tenant context rather than from
    ``users.organization_id`` directly, so every permission check runs against an
    organization the caller demonstrably still belongs to, and against an
    organization whose status permits operation.
    """
    # Imported here because the tenants module depends on this one for RBAC
    # checks of its own; deferring the import keeps that cycle from forming at
    # module load time.
    from app.modules.tenants.dependencies import get_tenant_context

    async def dependency(
        context: TenantContext = Depends(get_tenant_context),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if context.user.is_superuser:
            return context.user

        try:
            await ensure_user_has_permission(
                db,
                user_id=context.user_id,
                organization_id=context.organization_id,
                permission_code=permission_code,
            )
        except PermissionDenied as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied.",
            ) from exc
        return context.user

    return dependency
