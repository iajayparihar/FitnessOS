from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics.service import log_audit_event
from app.modules.auth.models import User
from app.modules.rbac.exceptions import (
    BranchNotInOrganization,
    PermissionDenied,
    PermissionNotFound,
    RoleNotFound,
    UserNotInOrganization,
)
from app.modules.rbac.models import Permission, Role, RolePermission, UserRole
from app.modules.rbac.schemas import RoleCreate
from app.modules.tenants.models import OrganizationBranch, OrganizationMembership

DEFAULT_PERMISSIONS: tuple[tuple[str, str, str], ...] = (
    ("tenants:read", "Read current organization information.", "tenants"),
    ("tenants:manage", "Manage organization settings and lifecycle.", "tenants"),
    ("branches:read", "Read organization branches.", "tenants"),
    ("branches:manage", "Create, update and remove branches.", "tenants"),
    ("users:read", "Read organization users and memberships.", "users"),
    ("users:manage", "Add, update and remove organization members.", "users"),
    ("rbac:read", "Read roles and permissions.", "rbac"),
    ("rbac:manage", "Create roles and assign permissions.", "rbac"),
    ("crm:read", "Read leads and CRM activity.", "crm"),
    ("crm:manage", "Manage CRM data.", "crm"),
    ("membership:read", "Read members, plans and memberships.", "membership"),
    ("membership:manage", "Manage members and memberships.", "membership"),
    ("attendance:read", "Read attendance records.", "attendance"),
    ("attendance:manage", "Manage attendance.", "attendance"),
    ("billing:read", "Read invoices, payments and refunds.", "billing"),
    ("billing:manage", "Manage invoices and payments.", "billing"),
    ("trainer:read", "Read trainer profiles and schedules.", "trainer"),
    ("trainer:manage", "Manage trainers, schedules and sessions.", "trainer"),
    ("nutrition:read", "Read nutrition plans.", "nutrition"),
    ("nutrition:manage", "Manage nutrition plans and assignments.", "nutrition"),
    ("inventory:read", "Read products, stock and suppliers.", "inventory"),
    ("inventory:manage", "Manage products, stock and purchase orders.", "inventory"),
    ("expenses:read", "Read expenses and payroll.", "expenses"),
    ("expenses:manage", "Manage expenses and payroll.", "expenses"),
    ("notifications:read", "Read notification history.", "notifications"),
    ("notifications:manage", "Send and configure notifications.", "notifications"),
    (
        "subscriptions:read",
        "Read the organization's platform subscription.",
        "subscriptions",
    ),
    (
        "subscriptions:manage",
        "Manage the organization's platform subscription.",
        "subscriptions",
    ),
    ("analytics:read", "Read dashboards and reports.", "analytics"),
)

ALL_PERMISSION_CODES: tuple[str, ...] = tuple(
    code for code, _, _ in DEFAULT_PERMISSIONS
)


@dataclass(frozen=True)
class SystemRoleDefinition:
    """A platform-defined role available to every organization."""

    slug: str
    name: str
    description: str
    permission_codes: tuple[str, ...]


# The catalogue below is deliberately global rather than copied per tenant: one
# row per role serves every organization, and a permission change reaches all of
# them without a data migration. Assignments are what carry the tenant, through
# ``user_roles.organization_id``.
#
# Two escalation guards shape these sets:
#   * only OWNER holds rbac:manage — anyone who can edit roles can grant
#     themselves any permission, so that is equivalent to ownership;
#   * only OWNER holds tenants:manage and subscriptions:manage, which cover
#     archiving the organization and changing what it pays for.
#
# MEMBER is intentionally near-empty. Permissions here are organization-wide, so
# granting a gym-goer membership:read would expose the entire member list.
# Self-service needs object-level scoping, which this system does not yet have.
SYSTEM_ROLE_DEFINITIONS: tuple[SystemRoleDefinition, ...] = (
    SystemRoleDefinition(
        slug="owner",
        name="Owner",
        description="Full control of the organization, including roles and billing.",
        permission_codes=ALL_PERMISSION_CODES,
    ),
    SystemRoleDefinition(
        slug="admin",
        name="Admin",
        description=(
            "Runs the business day to day. Everything except role management, "
            "organization lifecycle and platform subscription."
        ),
        permission_codes=(
            "tenants:read",
            "branches:read",
            "branches:manage",
            "users:read",
            "users:manage",
            "rbac:read",
            "crm:read",
            "crm:manage",
            "membership:read",
            "membership:manage",
            "attendance:read",
            "attendance:manage",
            "billing:read",
            "billing:manage",
            "trainer:read",
            "trainer:manage",
            "nutrition:read",
            "nutrition:manage",
            "inventory:read",
            "inventory:manage",
            "expenses:read",
            "expenses:manage",
            "notifications:read",
            "notifications:manage",
            "subscriptions:read",
            "analytics:read",
        ),
    ),
    SystemRoleDefinition(
        slug="manager",
        name="Manager",
        description=(
            "Runs floor operations. Full member, trainer and inventory control; "
            "financial data is read-only."
        ),
        permission_codes=(
            "tenants:read",
            "branches:read",
            "users:read",
            "crm:read",
            "crm:manage",
            "membership:read",
            "membership:manage",
            "attendance:read",
            "attendance:manage",
            "billing:read",
            "trainer:read",
            "trainer:manage",
            "nutrition:read",
            "nutrition:manage",
            "inventory:read",
            "inventory:manage",
            "expenses:read",
            "notifications:read",
            "notifications:manage",
            "analytics:read",
        ),
    ),
    SystemRoleDefinition(
        slug="trainer",
        name="Trainer",
        description=(
            "Coaches members: marks attendance and manages training and nutrition "
            "plans. No access to money or staff administration."
        ),
        permission_codes=(
            "tenants:read",
            "branches:read",
            "crm:read",
            "membership:read",
            "attendance:read",
            "attendance:manage",
            "trainer:read",
            "nutrition:read",
            "nutrition:manage",
        ),
    ),
    SystemRoleDefinition(
        slug="staff",
        name="Staff",
        description=(
            "Front desk: registers members, captures leads and records check-ins. "
            "Billing is read-only."
        ),
        permission_codes=(
            "tenants:read",
            "branches:read",
            "crm:read",
            "crm:manage",
            "membership:read",
            "membership:manage",
            "attendance:read",
            "attendance:manage",
            "billing:read",
            "trainer:read",
            "inventory:read",
            "notifications:read",
        ),
    ),
    SystemRoleDefinition(
        slug="member",
        name="Member",
        description=(
            "A gym-goer. Holds no organization-wide read access; self-service "
            "requires object-level scoping that does not exist yet."
        ),
        permission_codes=("tenants:read",),
    ),
)

SYSTEM_ROLE_BY_SLUG: dict[str, SystemRoleDefinition] = {
    definition.slug: definition for definition in SYSTEM_ROLE_DEFINITIONS
}


def make_slug(value: str) -> str:
    """Create a normalized role slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "role"


async def seed_default_permissions(db: AsyncSession) -> list[Permission]:
    """Create baseline permissions if they do not already exist."""
    result = await db.execute(select(Permission))
    existing_by_code = {permission.code: permission for permission in result.scalars()}
    permissions: list[Permission] = []

    for code, description, category in DEFAULT_PERMISSIONS:
        permission = existing_by_code.get(code)
        if permission is None:
            permission = Permission(
                code=code,
                description=description,
                category=category,
                is_active=True,
            )
            db.add(permission)
            await db.flush()
        permissions.append(permission)

    return permissions


async def list_permissions(db: AsyncSession) -> list[Permission]:
    """Return all active permissions."""
    await seed_default_permissions(db)
    result = await db.execute(
        select(Permission)
        .where(Permission.is_active.is_(True))
        .order_by(Permission.code)
    )
    return list(result.scalars())


async def list_roles(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
) -> list[Role]:
    """Return active roles visible to an organization."""
    result = await db.execute(
        select(Role)
        .where(
            Role.deleted_at.is_(None),
            Role.is_active.is_(True),
            (Role.organization_id == organization_id) | (Role.is_system.is_(True)),
        )
        .order_by(Role.is_system.desc(), Role.name)
    )
    return list(result.scalars())


async def get_role_by_id(
    db: AsyncSession,
    *,
    role_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> Role:
    """Return a role visible to an organization."""
    result = await db.execute(
        select(Role).where(
            Role.id == role_id,
            Role.deleted_at.is_(None),
            Role.is_active.is_(True),
            (Role.organization_id == organization_id) | (Role.is_system.is_(True)),
        )
    )
    role = result.scalar_one_or_none()
    if role is None:
        raise RoleNotFound
    return role


async def get_permissions_by_codes(
    db: AsyncSession,
    *,
    permission_codes: list[str],
) -> list[Permission]:
    """Return active permissions for the given codes."""
    await seed_default_permissions(db)
    if not permission_codes:
        return []

    result = await db.execute(
        select(Permission).where(
            Permission.code.in_(permission_codes),
            Permission.is_active.is_(True),
        )
    )
    permissions = list(result.scalars())
    found_codes = {permission.code for permission in permissions}
    missing_codes = set(permission_codes) - found_codes
    if missing_codes:
        raise PermissionNotFound(", ".join(sorted(missing_codes)))
    return permissions


async def create_role(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    payload: RoleCreate,
    actor_id: uuid.UUID | None = None,
) -> Role:
    """Create a tenant role with optional permissions."""
    role = Role(
        organization_id=organization_id,
        name=payload.name.strip(),
        slug=make_slug(payload.slug or payload.name),
        description=payload.description,
        is_system=False,
        is_active=True,
    )
    db.add(role)
    await db.flush()

    permissions = await get_permissions_by_codes(
        db,
        permission_codes=payload.permission_codes,
    )
    for permission in permissions:
        db.add(
            RolePermission(role_id=role.id, permission_id=permission.id, granted=True)
        )

    await log_audit_event(
        db,
        action="rbac.role.create",
        organization_id=organization_id,
        actor_id=actor_id,
        target_type="role",
        target_id=role.id,
        after_state={
            "id": str(role.id),
            "organization_id": str(organization_id),
            "name": role.name,
            "slug": role.slug,
            "description": role.description,
            "is_system": role.is_system,
            "is_active": role.is_active,
            "permission_codes": [permission.code for permission in permissions],
        },
    )
    await db.commit()
    await db.refresh(role)
    return role


async def seed_system_roles(db: AsyncSession) -> dict[str, Role]:
    """
    Create or refresh the platform's system roles and their permissions.

    Idempotent, and safe to call repeatedly: roles are matched by slug, missing
    permissions are granted, and permissions no longer in a role's definition are
    revoked so the catalogue in code stays the single source of truth.

    System roles carry ``organization_id IS NULL``. There is one row per role for
    the whole platform rather than a copy per tenant, so adding a permission to
    Manager reaches every organization without a data migration. The tenant lives
    on the assignment (``user_roles.organization_id``), not on the role.
    """
    permissions = await seed_default_permissions(db)
    permission_by_code = {permission.code: permission for permission in permissions}

    result = await db.execute(
        select(Role).where(
            Role.organization_id.is_(None),
            Role.is_system.is_(True),
        )
    )
    role_by_slug = {role.slug: role for role in result.scalars()}

    roles: dict[str, Role] = {}
    for definition in SYSTEM_ROLE_DEFINITIONS:
        role = role_by_slug.get(definition.slug)
        if role is None:
            role = Role(
                organization_id=None,
                name=definition.name,
                slug=definition.slug,
                description=definition.description,
                is_system=True,
                is_active=True,
            )
            db.add(role)
            await db.flush()
        else:
            role.name = definition.name
            role.description = definition.description
            role.is_active = True

        await _sync_role_permissions(
            db,
            role=role,
            permission_codes=definition.permission_codes,
            permission_by_code=permission_by_code,
        )
        roles[definition.slug] = role

    await db.flush()
    return roles


async def _sync_role_permissions(
    db: AsyncSession,
    *,
    role: Role,
    permission_codes: tuple[str, ...],
    permission_by_code: dict[str, Permission],
) -> None:
    """Make a role's granted permissions match its definition exactly."""
    wanted_ids = {
        permission_by_code[code].id
        for code in permission_codes
        if code in permission_by_code
    }

    result = await db.execute(
        select(RolePermission).where(RolePermission.role_id == role.id)
    )
    existing = {row.permission_id: row for row in result.scalars()}

    for permission_id in wanted_ids - set(existing):
        db.add(
            RolePermission(
                role_id=role.id,
                permission_id=permission_id,
                granted=True,
            )
        )
    for permission_id, row in existing.items():
        if permission_id not in wanted_ids:
            await db.delete(row)
        elif not row.granted:
            row.granted = True


async def get_system_role(db: AsyncSession, *, slug: str) -> Role | None:
    """Return one system role by slug, seeding the catalogue if it is absent."""
    if slug not in SYSTEM_ROLE_BY_SLUG:
        return None

    result = await db.execute(
        select(Role).where(
            Role.organization_id.is_(None),
            Role.is_system.is_(True),
            func.lower(Role.slug) == slug.lower(),
        )
    )
    role = result.scalar_one_or_none()
    if role is not None:
        return role

    return (await seed_system_roles(db)).get(slug)


async def ensure_owner_role(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID | None = None,
) -> Role:
    """
    Return the platform's owner role.

    Kept under its original name for existing callers. It no longer creates a
    per-organization copy: ``organization_id`` is accepted and ignored, because
    the owner role is now one shared system role scoped by the assignment.
    """
    role = await get_system_role(db, slug="owner")
    if role is None:  # pragma: no cover - the catalogue always defines owner.
        raise RoleNotFound
    return role


async def assign_role_to_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    organization_id: uuid.UUID,
    assigned_by: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
) -> UserRole:
    """Assign a role to a user within an organization."""
    await get_role_by_id(db, role_id=role_id, organization_id=organization_id)
    # Membership is the authority on who belongs to a tenant. users.
    # organization_id only records which organization the user is currently
    # working in, so a user may hold roles in an organization that is not their
    # active one.
    result = await db.execute(
        select(OrganizationMembership.id)
        .join(User, User.id == OrganizationMembership.user_id)
        .where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.deleted_at.is_(None),
            User.deleted_at.is_(None),
        )
    )
    if result.scalar_one_or_none() is None:
        raise UserNotInOrganization

    if branch_id is not None:
        result = await db.execute(
            select(OrganizationBranch.id).where(
                OrganizationBranch.id == branch_id,
                OrganizationBranch.organization_id == organization_id,
                OrganizationBranch.deleted_at.is_(None),
            )
        )
        if result.scalar_one_or_none() is None:
            raise BranchNotInOrganization

    branch_condition = (
        UserRole.branch_id.is_(None)
        if branch_id is None
        else UserRole.branch_id == branch_id
    )
    result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
            UserRole.organization_id == organization_id,
            branch_condition,
        )
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        assignment = UserRole(
            user_id=user_id,
            role_id=role_id,
            organization_id=organization_id,
            assigned_by=assigned_by,
            branch_id=branch_id,
        )
        db.add(assignment)
        await db.flush()
        await log_audit_event(
            db,
            action="rbac.user_role.assign",
            organization_id=organization_id,
            actor_id=assigned_by,
            target_type="user_role",
            target_id=assignment.id,
            after_state={
                "id": str(assignment.id),
                "user_id": str(user_id),
                "role_id": str(role_id),
                "organization_id": str(organization_id),
                "branch_id": str(branch_id) if branch_id is not None else None,
                "assigned_by": str(assigned_by) if assigned_by is not None else None,
            },
        )
    return assignment


async def user_has_permission(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    permission_code: str,
    branch_id: uuid.UUID | None = None,
) -> bool:
    """
    Return whether a user has a permission in an organization.

    ``branch_id`` is accepted for forward compatibility with branch-scoped
    resources but is NOT yet enforced: a role assignment grants its permissions
    organization-wide regardless of the ``UserRole.branch_id`` it was made with.
    Evaluating branch scope here would be fake enforcement until a caller
    actually has a branch-scoped resource to check against; ``UserRole.branch_id``
    exists so that evaluation can be added without a schema change.
    """
    result = await db.execute(
        select(Permission.id)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.user_id == user_id,
            UserRole.organization_id == organization_id,
            (Role.organization_id == organization_id) | (Role.is_system.is_(True)),
            Permission.code == permission_code,
            Permission.is_active.is_(True),
            RolePermission.granted.is_(True),
            Role.is_active.is_(True),
            Role.deleted_at.is_(None),
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def ensure_user_has_permission(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    permission_code: str,
    branch_id: uuid.UUID | None = None,
) -> None:
    """Raise PermissionDenied when a user lacks a permission."""
    if not await user_has_permission(
        db,
        user_id=user_id,
        organization_id=organization_id,
        permission_code=permission_code,
        branch_id=branch_id,
    ):
        raise PermissionDenied(permission_code)


async def get_user_role_slugs(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> list[str]:
    """Return the active role slugs a user holds inside an organization."""
    result = await db.execute(
        select(Role.slug)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.user_id == user_id,
            UserRole.organization_id == organization_id,
            (Role.organization_id == organization_id) | (Role.is_system.is_(True)),
            Role.is_active.is_(True),
            Role.deleted_at.is_(None),
        )
        .distinct()
        .order_by(Role.slug)
    )
    return list(result.scalars())


async def get_user_permission_codes(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> list[str]:
    """Return the permission codes a user is granted inside an organization."""
    result = await db.execute(
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.user_id == user_id,
            UserRole.organization_id == organization_id,
            (Role.organization_id == organization_id) | (Role.is_system.is_(True)),
            Permission.is_active.is_(True),
            RolePermission.granted.is_(True),
            Role.is_active.is_(True),
            Role.deleted_at.is_(None),
        )
        .distinct()
        .order_by(Permission.code)
    )
    return list(result.scalars())
