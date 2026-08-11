from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.rbac.exceptions import PermissionDenied
from app.modules.rbac.service import ensure_user_has_permission


def require_permission(permission_code: str) -> Callable:
    """Return a dependency that requires a tenant-scoped permission."""

    async def dependency(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if current_user.is_superuser:
            return current_user
        if current_user.organization_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied.",
            )

        try:
            await ensure_user_has_permission(
                db,
                user_id=current_user.id,
                organization_id=current_user.organization_id,
                permission_code=permission_code,
            )
        except PermissionDenied as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied.",
            ) from exc
        return current_user

    return dependency
