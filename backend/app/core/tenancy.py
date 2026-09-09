"""
Tenant context for multi-tenant request handling.

One Organization is one tenant. Every tenant-owned query must be filtered by
``organization_id``, and that value is resolved server-side from the caller's
membership — never accepted from the client.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OrganizationMemberRole

if TYPE_CHECKING:
    from app.modules.auth.models import User
    from app.modules.tenants.models import Organization, OrganizationMembership

# PostgreSQL setting consumed by the row-level-security policies described in the
# model modules. Kept in one place so the policies and the application cannot
# drift apart.
TENANT_SETTING = "app.current_organization_id"

# Seats that may administer the organization itself. Fine-grained authorization
# lives in the RBAC permission system; this set exists only for organization
# invariants that RBAC does not express, such as protecting the last owner.
ORGANIZATION_ADMIN_ROLES = frozenset(
    {OrganizationMemberRole.OWNER, OrganizationMemberRole.ADMIN}
)


@dataclass(frozen=True)
class TenantContext:
    """
    Resolved tenant for a single request.

    Immutable and constructed per request, so nothing is shared between
    concurrently running requests on the same worker.
    """

    user: User
    membership: OrganizationMembership
    organization: Organization

    @property
    def organization_id(self) -> uuid.UUID:
        """Return the tenant every query in this request must be scoped to."""
        return self.organization.id

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.id

    @property
    def role(self) -> OrganizationMemberRole:
        return self.membership.role

    @property
    def is_owner(self) -> bool:
        return self.membership.role is OrganizationMemberRole.OWNER

    @property
    def is_organization_admin(self) -> bool:
        """Return whether this seat may administer the organization itself."""
        return (
            self.user.is_superuser or self.membership.role in ORGANIZATION_ADMIN_ROLES
        )

    def owns(self, organization_id: uuid.UUID | None) -> bool:
        """Return whether a record's organization_id belongs to this tenant."""
        return organization_id is not None and organization_id == self.organization_id


async def set_tenant_context(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
) -> None:
    """
    Bind the tenant to the current database transaction.

    Uses ``set_config(..., is_local => true)`` so the value is scoped to the
    transaction and is discarded on COMMIT or ROLLBACK. That matters because
    connections are pooled: a session-level ``SET`` would survive the checkin and
    leak one tenant's identity into the next request that borrows the connection.

    SQLAlchemy autobegins a transaction for this statement, so the setting stays
    in force for the rest of the request's work on this session.
    """
    await db.execute(
        select(
            text("set_config(:setting, :value, true)").bindparams(
                bindparam("setting", TENANT_SETTING),
                bindparam("value", str(organization_id)),
            )
        )
    )


async def get_tenant_setting(db: AsyncSession) -> str | None:
    """Return the tenant bound to the current transaction, or None if unset."""
    result = await db.execute(
        select(
            text("current_setting(:setting, true)").bindparams(
                bindparam("setting", TENANT_SETTING)
            )
        )
    )
    value = result.scalar_one_or_none()
    return value or None


def setup_tenant_context():
    """
    Deprecated no-op retained for import compatibility.

    Tenant context is established per request by
    ``app.modules.tenants.dependencies.get_tenant_context``.
    """
    return None
