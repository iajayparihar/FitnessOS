from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.rbac.service import (
    get_user_permission_codes,
    get_user_role_slugs,
)


@dataclass(frozen=True)
class AuthenticatedContext:
    """
    Identity and authorization state for one authenticated request.

    Identity comes from Clerk; the organization, roles and permissions are
    resolved from FitnessOS and are never read from the session token.
    """

    user: User
    clerk_user_id: str | None
    user_id: uuid.UUID
    organization_id: uuid.UUID | None
    is_superuser: bool
    role_slugs: tuple[str, ...] = field(default=())
    permissions: frozenset[str] = field(default_factory=frozenset)

    def has_permission(self, permission_code: str) -> bool:
        """Return whether this request may exercise a permission."""
        return self.is_superuser or permission_code in self.permissions

    def owns_organization(self, organization_id: uuid.UUID | None) -> bool:
        """Return whether this request may act on the given tenant."""
        if self.is_superuser:
            return True
        return (
            organization_id is not None
            and self.organization_id is not None
            and organization_id == self.organization_id
        )


async def build_authenticated_context(
    db: AsyncSession,
    *,
    user: User,
) -> AuthenticatedContext:
    """Resolve FitnessOS authorization state for an authenticated user."""
    role_slugs: tuple[str, ...] = ()
    permissions: frozenset[str] = frozenset()

    if user.organization_id is not None:
        role_slugs = tuple(
            await get_user_role_slugs(
                db,
                user_id=user.id,
                organization_id=user.organization_id,
            )
        )
        permissions = frozenset(
            await get_user_permission_codes(
                db,
                user_id=user.id,
                organization_id=user.organization_id,
            )
        )

    return AuthenticatedContext(
        user=user,
        clerk_user_id=user.clerk_user_id,
        user_id=user.id,
        organization_id=user.organization_id,
        is_superuser=user.is_superuser,
        role_slugs=role_slugs,
        permissions=permissions,
    )
