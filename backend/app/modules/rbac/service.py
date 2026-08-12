from __future__ import annotations

import re
import uuid

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
from app.modules.tenants.models import OrganizationBranch

DEFAULT_PERMISSIONS: tuple[tuple[str, str, str], ...] = (
    ("tenants:read", "Read current organization information.", "tenants"),
    ("tenants:manage", "Manage organization settings.", "tenants"),
    ("users:read", "Read organization users.", "users"),
    ("users:manage", "Manage organization users.", "users"),
    ("rbac:read", "Read roles and permissions.", "rbac"),
    ("rbac:manage", "Create roles and assign permissions.", "rbac"),
    ("crm:manage", "Manage CRM data.", "crm"),
    ("membership:manage", "Manage members and memberships.", "membership"),
    ("attendance:manage", "Manage attendance.", "attendance"),
    ("billing:manage", "Manage invoices and payments.", "billing"),
)


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
        db.add(RolePermission(role_id=role.id, permission_id=permission.id, granted=True))

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


async def ensure_owner_role(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
) -> Role:
    """Create or return the tenant owner role with all default permissions."""
    permissions = await seed_default_permissions(db)
    result = await db.execute(
        select(Role).where(
            Role.organization_id == organization_id,
            func.lower(Role.slug) == "owner",
            Role.deleted_at.is_(None),
        )
    )
    role = result.scalar_one_or_none()
    if role is None:
        role = Role(
            organization_id=organization_id,
            name="Owner",
            slug="owner",
            description="Full organization owner access.",
            is_system=False,
            is_active=True,
        )
        db.add(role)
        await db.flush()

    result = await db.execute(
        select(RolePermission.permission_id).where(RolePermission.role_id == role.id)
    )
    existing_permission_ids = set(result.scalars())
    for permission in permissions:
        if permission.id not in existing_permission_ids:
            db.add(
                RolePermission(
                    role_id=role.id,
                    permission_id=permission.id,
                    granted=True,
                )
            )

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
    result = await db.execute(
        select(User.id).where(
            User.id == user_id,
            User.organization_id == organization_id,
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
) -> bool:
    """Return whether a user has a permission in an organization."""
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
) -> None:
    """Raise PermissionDenied when a user lacks a permission."""
    if not await user_has_permission(
        db,
        user_id=user_id,
        organization_id=organization_id,
        permission_code=permission_code,
    ):
        raise PermissionDenied(permission_code)
