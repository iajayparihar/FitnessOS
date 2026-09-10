"""
Organization/tenant business logic.

Every read and write in this module is scoped by ``organization_id``. Callers
pass the tenant explicitly rather than letting it be inferred, so a missing scope
is a visible omission at the call site instead of a silent cross-tenant leak.
"""

from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import (
    OrganizationMemberRole,
    OrganizationMemberStatus,
    OrganizationStatus,
)
from app.modules.analytics.service import log_audit_event
from app.modules.auth.models import User
from app.modules.rbac.models import Role, UserRole
from app.modules.rbac.service import (
    assign_role_to_user,
    get_system_role,
)
from app.modules.tenants.exceptions import (
    BranchNotFound,
    DuplicateMembership,
    LastOwnerRemoval,
    MainBranchRequired,
    MembershipNotFound,
    OrgNotFound,
    OwnerSeatRequiresOwner,
    SelfRoleChangeNotAllowed,
    SlugUnavailable,
    UserNotFound,
)
from app.modules.tenants.models import (
    Organization,
    OrganizationBranch,
    OrganizationMembership,
    OrganizationSetting,
)
from app.modules.tenants.schemas import (
    BranchCreate,
    BranchUpdate,
    MembershipUpdate,
    OrgCreate,
    OrgProvisionRequest,
    OrgUpdate,
    SettingUpsert,
)

logger = logging.getLogger("app.tenants")

MAX_SLUG_ATTEMPTS = 50

# Seeded on organization creation so the onboarding flow has somewhere to read
# and write locale/business configuration from day one. Intentionally small:
# more keys can be added without a schema change.
DEFAULT_SETTING_KEYS = ("locale", "business_hours", "notifications")


def make_slug(value: str) -> str:
    """Create a normalized, URL-safe organization slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "organization"


# ---------------------------------------------------------------------------
# Organization reads
# ---------------------------------------------------------------------------


async def get_org_by_id(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
) -> Organization:
    """Return one non-deleted organization by id."""
    result = await db.execute(
        select(Organization).where(
            Organization.id == organization_id,
            Organization.deleted_at.is_(None),
        )
    )
    organization = result.scalar_one_or_none()
    if organization is None:
        raise OrgNotFound
    return organization


async def list_orgs_for_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> list[tuple[Organization, OrganizationMembership]]:
    """
    Return every organization the user has a live membership in.

    Joined in one query, so listing a user's organizations never degenerates into
    a membership lookup followed by one organization lookup per row.
    """
    result = await db.execute(
        select(Organization, OrganizationMembership)
        .join(
            OrganizationMembership,
            OrganizationMembership.organization_id == Organization.id,
        )
        .where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.deleted_at.is_(None),
            OrganizationMembership.status == OrganizationMemberStatus.ACTIVE,
            Organization.deleted_at.is_(None),
        )
        .order_by(Organization.name)
    )
    return [(row[0], row[1]) for row in result.all()]


async def ensure_slug_available(db: AsyncSession, *, slug: str) -> None:
    """Raise SlugUnavailable when an organization slug is already taken."""
    if await _slug_taken(db, slug=slug):
        raise SlugUnavailable(slug)


async def _slug_taken(db: AsyncSession, *, slug: str) -> bool:
    result = await db.execute(
        select(Organization.id).where(
            func.lower(Organization.slug) == slug.lower(),
            Organization.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none() is not None


async def allocate_slug(db: AsyncSession, *, preferred: str) -> str:
    """
    Return a free slug derived from the preferred value.

    Collisions get a numeric suffix ("ajay-fitness-studio-2"). The scan only
    narrows the candidate; the partial unique index on ``organizations.slug`` is
    what actually guarantees uniqueness under concurrency, and the caller retries
    on the resulting IntegrityError.
    """
    base = make_slug(preferred)
    if not await _slug_taken(db, slug=base):
        return base

    for suffix in range(2, MAX_SLUG_ATTEMPTS + 2):
        candidate = f"{base}-{suffix}"
        if not await _slug_taken(db, slug=candidate):
            return candidate

    return f"{base}-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Organization writes
# ---------------------------------------------------------------------------


async def create_org(
    db: AsyncSession,
    *,
    payload: OrgCreate,
    created_by: uuid.UUID | None = None,
    slug: str | None = None,
) -> Organization:
    """Create an organization row without committing."""
    organization = Organization(
        name=payload.name.strip(),
        slug=slug or make_slug(payload.slug or payload.name),
        business_type=payload.business_type,
        industry=payload.industry,
        phone=payload.phone,
        email=payload.email,
        website=payload.website,
        timezone=payload.timezone,
        currency=payload.currency,
        country=payload.country,
        settings=payload.settings,
        branding=payload.branding,
        billing_contact=payload.billing_contact,
        data_region=payload.data_region,
        created_by=created_by,
        updated_by=created_by,
    )
    db.add(organization)
    await db.flush()
    await db.refresh(organization)
    return organization


async def update_org(
    db: AsyncSession,
    *,
    organization: Organization,
    payload: OrgUpdate,
    actor_id: uuid.UUID,
) -> Organization:
    """Apply a partial update to an organization and record an audit event."""
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return organization

    before = {field: _auditable(getattr(organization, field)) for field in changes}
    for field, value in changes.items():
        setattr(organization, field, value)
    organization.updated_by = actor_id

    await db.flush()
    await log_audit_event(
        db,
        action="organization.updated",
        organization_id=organization.id,
        actor_id=actor_id,
        target_type="organization",
        target_id=organization.id,
        before_state=before,
        after_state={field: _auditable(value) for field, value in changes.items()},
    )
    await db.commit()
    await db.refresh(organization)
    return organization


async def archive_org(
    db: AsyncSession,
    *,
    organization: Organization,
    actor_id: uuid.UUID,
) -> None:
    """
    Soft-delete an organization.

    Business records are never physically removed: gym history is needed for
    billing, attendance and compliance long after a tenant stops trading.
    """
    organization.deleted_at = func.now()
    organization.deleted_by = actor_id
    organization.status = OrganizationStatus.ARCHIVED
    organization.updated_by = actor_id

    await db.flush()
    await log_audit_event(
        db,
        action="organization.archived",
        organization_id=organization.id,
        actor_id=actor_id,
        target_type="organization",
        target_id=organization.id,
    )
    await db.commit()


def _auditable(value: object) -> object:
    """Coerce a model value into something JSON-serialisable for the audit log."""
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    return value


# ---------------------------------------------------------------------------
# Provisioning
# ---------------------------------------------------------------------------


async def provision_organization(
    db: AsyncSession,
    *,
    user: User,
    payload: OrgProvisionRequest,
) -> tuple[Organization, OrganizationMembership, OrganizationBranch]:
    """
    Create a complete, usable tenant for a user, atomically.

    Organization, owner membership, owner RBAC role, main branch and default
    settings are all written in one transaction. If any step fails the whole
    thing rolls back, so a half-initialised organization — one with no owner, or
    no main branch — can never exist.

    The caller must not have committed anything on this session beforehand.
    """
    slug = await allocate_slug(db, preferred=payload.slug or payload.name)
    organization = await create_org(
        db,
        payload=payload,
        created_by=user.id,
        slug=slug,
    )

    membership = OrganizationMembership(
        organization_id=organization.id,
        user_id=user.id,
        role=OrganizationMemberRole.OWNER,
        status=OrganizationMemberStatus.ACTIVE,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(membership)

    # The user's active tenant pointer. Always validated against a live
    # membership before it is trusted (see dependencies.get_tenant_context).
    user.organization_id = organization.id
    await db.flush()

    await sync_seat_rbac_role(
        db,
        organization_id=organization.id,
        user_id=user.id,
        seat=OrganizationMemberRole.OWNER,
        actor_id=user.id,
    )

    main_branch = OrganizationBranch(
        organization_id=organization.id,
        name=payload.main_branch_name.strip(),
        phone=payload.phone,
        email=payload.email,
        is_main=True,
        is_active=True,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(main_branch)
    await db.flush()

    await _seed_default_settings(db, organization=organization)

    await log_audit_event(
        db,
        action="organization.created",
        organization_id=organization.id,
        actor_id=user.id,
        target_type="organization",
        target_id=organization.id,
        after_state={
            "id": str(organization.id),
            "slug": organization.slug,
            "business_type": organization.business_type.value,
            "main_branch_id": str(main_branch.id),
        },
    )

    await db.commit()
    await db.refresh(organization)
    await db.refresh(membership)
    await db.refresh(main_branch)

    logger.info(
        "organization_created",
        extra={
            "organization_id": str(organization.id),
            "user_id": str(user.id),
        },
    )
    return organization, membership, main_branch


async def _seed_default_settings(
    db: AsyncSession,
    *,
    organization: Organization,
) -> None:
    """Write the organization-scoped settings the onboarding flow expects."""
    defaults: dict[str, dict] = {
        "locale": {
            "timezone": organization.timezone,
            "currency": organization.currency.value,
            "country": organization.country,
            "date_format": "DD/MM/YYYY",
        },
        "business_hours": {
            "monday_to_friday": {"open": "06:00", "close": "22:00"},
            "saturday": {"open": "07:00", "close": "20:00"},
            "sunday": {"open": "08:00", "close": "14:00"},
        },
        "notifications": {
            "email_enabled": True,
            "sms_enabled": False,
            "whatsapp_enabled": False,
        },
    }
    for key in DEFAULT_SETTING_KEYS:
        db.add(
            OrganizationSetting(
                organization_id=organization.id,
                branch_id=None,
                key=key,
                value=defaults[key],
            )
        )
    await db.flush()


# ---------------------------------------------------------------------------
# Membership
# ---------------------------------------------------------------------------


def _membership_scope(organization_id: uuid.UUID) -> Select:
    """Base membership query, already narrowed to one tenant."""
    return select(OrganizationMembership).where(
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.deleted_at.is_(None),
    )


async def get_active_membership(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> OrganizationMembership | None:
    """Return the user's live, active membership in an organization."""
    result = await db.execute(
        _membership_scope(organization_id).where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == OrganizationMemberStatus.ACTIVE,
        )
    )
    return result.scalar_one_or_none()


async def list_memberships(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
) -> list[OrganizationMembership]:
    """List the memberships of one organization."""
    result = await db.execute(
        _membership_scope(organization_id).order_by(OrganizationMembership.created_at)
    )
    return list(result.scalars())


async def get_membership(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> OrganizationMembership:
    """
    Return one membership within a tenant.

    The organization filter is part of the lookup rather than a check afterwards,
    so a membership id from another tenant simply does not match.
    """
    result = await db.execute(
        _membership_scope(organization_id).where(
            OrganizationMembership.user_id == user_id
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise MembershipNotFound
    return membership


async def add_membership(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role: OrganizationMemberRole,
    actor_id: uuid.UUID,
) -> OrganizationMembership:
    """Add an existing user to an organization."""
    result = await db.execute(
        select(User.id).where(User.id == user_id, User.deleted_at.is_(None))
    )
    if result.scalar_one_or_none() is None:
        raise UserNotFound

    existing = await db.execute(
        _membership_scope(organization_id).where(
            OrganizationMembership.user_id == user_id
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise DuplicateMembership

    if role is OrganizationMemberRole.OWNER:
        await _require_actor_is_owner(
            db, organization_id=organization_id, actor_id=actor_id
        )

    membership = OrganizationMembership(
        organization_id=organization_id,
        user_id=user_id,
        role=role,
        status=OrganizationMemberStatus.ACTIVE,
        invited_by=actor_id,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(membership)
    await db.flush()

    await sync_seat_rbac_role(
        db,
        organization_id=organization_id,
        user_id=user_id,
        seat=role,
        actor_id=actor_id,
    )

    await log_audit_event(
        db,
        action="organization_member_added",
        organization_id=organization_id,
        actor_id=actor_id,
        target_type="organization_membership",
        target_id=membership.id,
        after_state={"user_id": str(user_id), "role": role.value},
    )
    await db.commit()
    await db.refresh(membership)
    return membership


async def sync_seat_rbac_role(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    seat: OrganizationMemberRole,
    actor_id: uuid.UUID | None,
) -> None:
    """
    Grant the system role matching a membership seat, replacing any previous one.

    Membership answers "which tenant"; RBAC answers "what may you do". The two
    stay separate systems, and this is the one bridge between them: each seat has
    a same-named system role, so a new member is usable immediately instead of
    holding a seat that grants nothing.

    Only system-role assignments are touched. Any additional custom role an
    organization has granted the user is left alone, so a seat change never
    silently revokes bespoke access.
    """
    role = await get_system_role(db, slug=seat.value)
    if role is None:  # pragma: no cover - every seat has a system role.
        return

    await _revoke_system_roles(
        db,
        organization_id=organization_id,
        user_id=user_id,
        keep_role_id=role.id,
    )
    await assign_role_to_user(
        db,
        user_id=user_id,
        role_id=role.id,
        organization_id=organization_id,
        assigned_by=actor_id,
    )


async def _revoke_system_roles(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    keep_role_id: uuid.UUID | None = None,
) -> None:
    """Remove a user's system-role assignments within one organization."""
    result = await db.execute(
        select(UserRole)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            UserRole.user_id == user_id,
            UserRole.organization_id == organization_id,
            Role.is_system.is_(True),
        )
    )
    for assignment in result.scalars():
        if keep_role_id is not None and assignment.role_id == keep_role_id:
            continue
        await db.delete(assignment)
    await db.flush()


async def update_membership(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: MembershipUpdate,
    actor_id: uuid.UUID,
) -> OrganizationMembership:
    """Change a member's seat or status, protecting the last owner."""
    membership = await get_membership(
        db, organization_id=organization_id, user_id=user_id
    )
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return membership

    if "role" in changes and actor_id == user_id:
        # A user must never be able to change their own role by manipulating a
        # request body, even downward — an owner "stepping down" is a separate,
        # deliberate flow this phase does not implement, not a side effect of
        # this endpoint.
        raise SelfRoleChangeNotAllowed

    # Granting the owner seat, revoking it, or otherwise touching a membership
    # that currently holds it (e.g. suspending its status) is ownership-level
    # administration, not routine member management: gated to actors who
    # already hold the owner seat themselves so users:manage — held by Admin —
    # cannot mint, depose, or disable an owner.
    touches_owner_seat = (
        membership.role is OrganizationMemberRole.OWNER
        or changes.get("role") is OrganizationMemberRole.OWNER
    )
    if touches_owner_seat:
        await _require_actor_is_owner(
            db, organization_id=organization_id, actor_id=actor_id
        )

    loses_owner_seat = (
        membership.role is OrganizationMemberRole.OWNER
        and changes.get("role", OrganizationMemberRole.OWNER)
        is not OrganizationMemberRole.OWNER
    ) or (
        membership.role is OrganizationMemberRole.OWNER
        and changes.get("status", OrganizationMemberStatus.ACTIVE)
        is not OrganizationMemberStatus.ACTIVE
    )
    if loses_owner_seat and await _count_active_owners(db, organization_id) <= 1:
        raise LastOwnerRemoval

    before = {field: _auditable(getattr(membership, field)) for field in changes}
    for field, value in changes.items():
        setattr(membership, field, value)
    membership.updated_by = actor_id

    await db.flush()
    if "role" in changes:
        await sync_seat_rbac_role(
            db,
            organization_id=organization_id,
            user_id=user_id,
            seat=membership.role,
            actor_id=actor_id,
        )
    await log_audit_event(
        db,
        action="organization_member_updated",
        organization_id=organization_id,
        actor_id=actor_id,
        target_type="organization_membership",
        target_id=membership.id,
        before_state=before,
        after_state={field: _auditable(value) for field, value in changes.items()},
    )
    await db.commit()
    await db.refresh(membership)
    return membership


async def remove_membership(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """Soft-delete a membership, refusing to strand the organization ownerless."""
    membership = await get_membership(
        db, organization_id=organization_id, user_id=user_id
    )
    if (
        membership.role is OrganizationMemberRole.OWNER
        and await _count_active_owners(db, organization_id) <= 1
    ):
        raise LastOwnerRemoval

    membership.deleted_at = func.now()
    membership.deleted_by = actor_id
    membership.status = OrganizationMemberStatus.REMOVED
    await _revoke_system_roles(db, organization_id=organization_id, user_id=user_id)

    # Do not leave the removed user pointing at a tenant they can no longer read.
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is not None and user.organization_id == organization_id:
        user.organization_id = None

    await db.flush()
    await log_audit_event(
        db,
        action="organization_member_removed",
        organization_id=organization_id,
        actor_id=actor_id,
        target_type="organization_membership",
        target_id=membership.id,
        before_state={"user_id": str(user_id), "role": membership.role.value},
    )
    await db.commit()


async def _require_actor_is_owner(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """Raise OwnerSeatRequiresOwner unless the actor holds an active owner seat."""
    actor_membership = await get_active_membership(
        db, user_id=actor_id, organization_id=organization_id
    )
    if (
        actor_membership is None
        or actor_membership.role is not OrganizationMemberRole.OWNER
    ):
        raise OwnerSeatRequiresOwner


async def _count_active_owners(
    db: AsyncSession,
    organization_id: uuid.UUID,
) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(OrganizationMembership)
        .where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.deleted_at.is_(None),
            OrganizationMembership.status == OrganizationMemberStatus.ACTIVE,
            OrganizationMembership.role == OrganizationMemberRole.OWNER,
        )
    )
    return int(result.scalar_one())


async def switch_active_organization(
    db: AsyncSession,
    *,
    user: User,
    organization_id: uuid.UUID,
) -> Organization:
    """
    Repoint the user's active tenant, after proving they belong to it.

    Membership is the authority on access; this only moves the pointer that
    decides which of the caller's organizations subsequent requests operate in.
    """
    membership = await get_active_membership(
        db, user_id=user.id, organization_id=organization_id
    )
    if membership is None:
        raise OrgNotFound

    organization = await get_org_by_id(db, organization_id=organization_id)
    user.organization_id = organization.id
    await db.commit()
    return organization


# ---------------------------------------------------------------------------
# Branches
# ---------------------------------------------------------------------------


def _branch_scope(organization_id: uuid.UUID) -> Select:
    """Base branch query, already narrowed to one tenant."""
    return select(OrganizationBranch).where(
        OrganizationBranch.organization_id == organization_id,
        OrganizationBranch.deleted_at.is_(None),
    )


async def list_branches(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
) -> list[OrganizationBranch]:
    """List the branches of one organization."""
    result = await db.execute(
        _branch_scope(organization_id).order_by(
            OrganizationBranch.is_main.desc(), OrganizationBranch.name
        )
    )
    return list(result.scalars())


async def get_branch(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    branch_id: uuid.UUID,
) -> OrganizationBranch:
    """
    Return one branch within a tenant.

    A branch id alone is never sufficient authorization: the organization filter
    is part of the query, so another tenant's branch id yields BranchNotFound
    rather than the record.
    """
    result = await db.execute(
        _branch_scope(organization_id).where(OrganizationBranch.id == branch_id)
    )
    branch = result.scalar_one_or_none()
    if branch is None:
        raise BranchNotFound
    return branch


async def create_branch(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    payload: BranchCreate,
    actor_id: uuid.UUID,
) -> OrganizationBranch:
    """Create a branch in the current tenant."""
    if payload.is_main:
        await _demote_current_main_branch(db, organization_id=organization_id)

    branch = OrganizationBranch(
        organization_id=organization_id,
        name=payload.name.strip(),
        code=payload.code,
        phone=payload.phone,
        email=payload.email,
        address=payload.address,
        is_main=payload.is_main,
        is_active=payload.is_active,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(branch)
    await db.flush()

    await log_audit_event(
        db,
        action="branch_created",
        organization_id=organization_id,
        actor_id=actor_id,
        target_type="organization_branch",
        target_id=branch.id,
        after_state={"name": branch.name, "is_main": branch.is_main},
    )
    await db.commit()
    await db.refresh(branch)
    return branch


async def update_branch(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    branch_id: uuid.UUID,
    payload: BranchUpdate,
    actor_id: uuid.UUID,
) -> OrganizationBranch:
    """Apply a partial update to a branch in the current tenant."""
    branch = await get_branch(db, organization_id=organization_id, branch_id=branch_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return branch

    if changes.get("is_main") is True and not branch.is_main:
        await _demote_current_main_branch(db, organization_id=organization_id)
    if changes.get("is_main") is False and branch.is_main:
        raise MainBranchRequired

    before = {field: _auditable(getattr(branch, field)) for field in changes}
    for field, value in changes.items():
        setattr(branch, field, value)
    branch.updated_by = actor_id

    await db.flush()
    await log_audit_event(
        db,
        action="branch_updated",
        organization_id=organization_id,
        actor_id=actor_id,
        target_type="organization_branch",
        target_id=branch.id,
        before_state=before,
        after_state={field: _auditable(value) for field, value in changes.items()},
    )
    await db.commit()
    await db.refresh(branch)
    return branch


async def delete_branch(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    branch_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """Soft-delete a branch, keeping the main-branch invariant intact."""
    branch = await get_branch(db, organization_id=organization_id, branch_id=branch_id)
    if branch.is_main:
        raise MainBranchRequired

    branch.deleted_at = func.now()
    branch.deleted_by = actor_id
    branch.is_active = False

    await db.flush()
    await log_audit_event(
        db,
        action="branch_deleted",
        organization_id=organization_id,
        actor_id=actor_id,
        target_type="organization_branch",
        target_id=branch.id,
        before_state={"name": branch.name},
    )
    await db.commit()


async def _demote_current_main_branch(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
) -> None:
    """
    Clear the existing main branch so a new one can take the flag.

    Flushed before the replacement is written, because the partial unique index
    permits only one main branch per organization at a time.
    """
    result = await db.execute(
        _branch_scope(organization_id).where(OrganizationBranch.is_main.is_(True))
    )
    for branch in result.scalars():
        branch.is_main = False
    await db.flush()


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


async def list_settings(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
) -> list[OrganizationSetting]:
    """List the organization-scoped settings of one tenant."""
    result = await db.execute(
        select(OrganizationSetting)
        .where(
            OrganizationSetting.organization_id == organization_id,
            OrganizationSetting.branch_id.is_(None),
        )
        .order_by(OrganizationSetting.key)
    )
    return list(result.scalars())


async def upsert_setting(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    payload: SettingUpsert,
    actor_id: uuid.UUID,
) -> OrganizationSetting:
    """Create or replace one organization-scoped setting."""
    result = await db.execute(
        select(OrganizationSetting).where(
            OrganizationSetting.organization_id == organization_id,
            OrganizationSetting.branch_id.is_(None),
            OrganizationSetting.key == payload.key,
        )
    )
    setting = result.scalar_one_or_none()
    if setting is None:
        setting = OrganizationSetting(
            organization_id=organization_id,
            branch_id=None,
            key=payload.key,
            value=payload.value,
            description=payload.description,
        )
        db.add(setting)
    else:
        setting.value = payload.value
        setting.description = payload.description

    await db.flush()
    await log_audit_event(
        db,
        action="organization_setting_updated",
        organization_id=organization_id,
        actor_id=actor_id,
        target_type="organization_setting",
        target_id=setting.id,
        after_state={"key": setting.key},
    )
    await db.commit()
    await db.refresh(setting)
    return setting


async def get_org_with_memberships(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
) -> Organization:
    """Load an organization with its memberships eagerly, avoiding N+1 access."""
    result = await db.execute(
        select(Organization)
        .options(selectinload(Organization.memberships))
        .where(
            Organization.id == organization_id,
            Organization.deleted_at.is_(None),
        )
    )
    organization = result.scalar_one_or_none()
    if organization is None:
        raise OrgNotFound
    return organization
