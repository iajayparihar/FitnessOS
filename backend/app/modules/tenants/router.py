"""
Organization/tenant API.

Path parameters never select the tenant. ``organization_id`` in a URL is checked
against the tenant resolved from the caller's membership, and a mismatch is
answered as 404 rather than 403 so identifiers in other tenants stay unprobeable.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenancy import TenantContext
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.tenants.dependencies import (
    get_current_org,
    require_path_org_permission,
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
from app.modules.tenants.models import Organization
from app.modules.tenants.schemas import (
    BranchCreate,
    BranchEnvelope,
    BranchListEnvelope,
    BranchUpdate,
    MembershipCreate,
    MembershipEnvelope,
    MembershipListEnvelope,
    MembershipUpdate,
    OrgCreate,
    OrgEnvelope,
    OrgProvisionData,
    OrgProvisionEnvelope,
    OrgProvisionRequest,
    OrgSummary,
    OrgSummaryListEnvelope,
    OrgUpdate,
    SettingEnvelope,
    SettingListEnvelope,
    SettingUpsert,
)
from app.modules.tenants.service import (
    add_membership,
    archive_org,
    create_branch,
    delete_branch,
    get_branch,
    list_branches,
    list_memberships,
    list_orgs_for_user,
    list_settings,
    provision_organization,
    remove_membership,
    switch_active_organization,
    update_branch,
    update_membership,
    update_org,
    upsert_setting,
)

router = APIRouter()

# Permission codes are the existing RBAC ones; no new authorization vocabulary
# is introduced by this module.
TENANTS_READ = "tenants:read"
TENANTS_MANAGE = "tenants:manage"
# Branches are separated from organization lifecycle on purpose: opening a new
# location is routine business, whereas tenants:manage also archives the tenant.
BRANCHES_READ = "branches:read"
BRANCHES_MANAGE = "branches:manage"
USERS_READ = "users:read"
USERS_MANAGE = "users:manage"


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=OrgProvisionEnvelope,
    status_code=status.HTTP_201_CREATED,
    summary="Create an organization",
    description=(
        "Provisions a complete tenant in one transaction: the organization, an "
        "owner membership for the caller, the owner RBAC role, a main branch and "
        "default settings. Any failure rolls the whole thing back, so a partially "
        "initialised organization is never left behind."
    ),
    responses={
        401: {"description": "Authentication required."},
        409: {"description": "The caller already belongs to an organization."},
    },
)
async def create_organization(
    payload: OrgProvisionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrgProvisionEnvelope:
    """Create an organization and make the caller its owner."""
    if current_user.organization_id is not None and not current_user.is_superuser:
        raise _conflict("User already belongs to an organization.")

    try:
        organization, membership, main_branch = await provision_organization(
            db,
            user=current_user,
            payload=payload,
        )
    except SlugUnavailable as exc:
        await db.rollback()
        raise _conflict("Organization slug is already in use.") from exc
    except IntegrityError as exc:
        await db.rollback()
        raise _conflict("Organization already exists.") from exc

    return OrgProvisionEnvelope(
        data=OrgProvisionData(
            organization=organization,
            membership=membership,
            main_branch=main_branch,
        )
    )


@router.get(
    "",
    response_model=OrgSummaryListEnvelope,
    summary="List the caller's organizations",
    description=(
        "Returns every organization the authenticated user has an active "
        "membership in, with the seat they hold and which one is currently active."
    ),
)
async def list_organizations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrgSummaryListEnvelope:
    """List organizations available to the authenticated user."""
    rows = await list_orgs_for_user(db, user_id=current_user.id)
    return OrgSummaryListEnvelope(
        data=[
            OrgSummary(
                id=organization.id,
                name=organization.name,
                slug=organization.slug,
                status=organization.status,
                business_type=organization.business_type,
                role=membership.role,
                is_current=organization.id == current_user.organization_id,
            )
            for organization, membership in rows
        ]
    )


@router.get(
    "/{organization_id}",
    response_model=OrgEnvelope,
    summary="Get organization details",
    responses={404: {"description": "Organization not found or not the caller's."}},
)
async def get_organization(
    context: TenantContext = Depends(require_path_org_permission(TENANTS_READ)),
) -> OrgEnvelope:
    """Return the caller's organization."""
    return OrgEnvelope(data=context.organization)


@router.patch(
    "/{organization_id}",
    response_model=OrgEnvelope,
    summary="Update an organization",
    responses={
        403: {"description": "Permission denied, or organization not active."},
        404: {"description": "Organization not found or not the caller's."},
    },
)
async def patch_organization(
    payload: OrgUpdate,
    context: TenantContext = Depends(require_path_org_permission(TENANTS_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> OrgEnvelope:
    """Apply a partial update to the caller's organization."""
    organization = await update_org(
        db,
        organization=context.organization,
        payload=payload,
        actor_id=context.user_id,
    )
    return OrgEnvelope(data=organization)


@router.delete(
    "/{organization_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive an organization",
    description=(
        "Soft-deletes the organization and marks it archived. Business records "
        "are retained for billing, attendance and compliance history."
    ),
)
async def delete_organization(
    context: TenantContext = Depends(require_path_org_permission(TENANTS_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Archive the caller's organization."""
    await archive_org(
        db,
        organization=context.organization,
        actor_id=context.user_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{organization_id}/switch",
    response_model=OrgEnvelope,
    summary="Switch the caller's active organization",
    description=(
        "Repoints the caller at another organization they belong to. Membership "
        "is verified before the pointer moves."
    ),
    responses={404: {"description": "The caller has no membership there."}},
)
async def switch_organization(
    organization_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrgEnvelope:
    """Make one of the caller's organizations the active tenant."""
    try:
        organization = await switch_active_organization(
            db,
            user=current_user,
            organization_id=organization_id,
        )
    except OrgNotFound as exc:
        raise _not_found("Organization not found.") from exc
    return OrgEnvelope(data=organization)


# ---------------------------------------------------------------------------
# Memberships
# ---------------------------------------------------------------------------


@router.get(
    "/{organization_id}/members",
    response_model=MembershipListEnvelope,
    summary="List organization members",
)
async def get_members(
    context: TenantContext = Depends(require_path_org_permission(USERS_READ)),
    db: AsyncSession = Depends(get_db),
) -> MembershipListEnvelope:
    """List the memberships of the caller's organization."""
    memberships = await list_memberships(db, organization_id=context.organization_id)
    return MembershipListEnvelope(data=memberships)


@router.post(
    "/{organization_id}/members",
    response_model=MembershipEnvelope,
    status_code=status.HTTP_201_CREATED,
    summary="Add a member to the organization",
    responses={
        403: {"description": "Only an owner may grant the owner seat."},
        404: {"description": "User not found."},
        409: {"description": "User is already a member."},
    },
)
async def post_member(
    payload: MembershipCreate,
    context: TenantContext = Depends(require_path_org_permission(USERS_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> MembershipEnvelope:
    """Add an existing user to the caller's organization."""
    try:
        membership = await add_membership(
            db,
            organization_id=context.organization_id,
            user_id=payload.user_id,
            role=payload.role,
            actor_id=context.user_id,
        )
    except UserNotFound as exc:
        raise _not_found("User not found.") from exc
    except DuplicateMembership as exc:
        raise _conflict("User is already a member of this organization.") from exc
    except OwnerSeatRequiresOwner as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an existing owner can grant the owner seat.",
        ) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise _conflict("User is already a member of this organization.") from exc
    return MembershipEnvelope(data=membership)


@router.patch(
    "/{organization_id}/members/{user_id}",
    response_model=MembershipEnvelope,
    summary="Update a member's seat or status",
    description=(
        "An actor may never change their own role through this endpoint, and "
        "granting or revoking the owner seat requires the actor to already be "
        "an owner."
    ),
    responses={
        403: {
            "description": ("Self role change, or a non-owner touching the owner seat.")
        },
        404: {"description": "Membership not found in this organization."},
        409: {"description": "The organization would be left without an owner."},
    },
)
async def patch_member(
    user_id: uuid.UUID,
    payload: MembershipUpdate,
    context: TenantContext = Depends(require_path_org_permission(USERS_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> MembershipEnvelope:
    """Change a member's role or status inside the caller's organization."""
    try:
        membership = await update_membership(
            db,
            organization_id=context.organization_id,
            user_id=user_id,
            payload=payload,
            actor_id=context.user_id,
        )
    except MembershipNotFound as exc:
        raise _not_found("Member not found.") from exc
    except SelfRoleChangeNotAllowed as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot change your own role.",
        ) from exc
    except OwnerSeatRequiresOwner as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an existing owner can grant or revoke the owner seat.",
        ) from exc
    except LastOwnerRemoval as exc:
        raise _conflict("An organization must keep at least one owner.") from exc
    return MembershipEnvelope(data=membership)


@router.delete(
    "/{organization_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member from the organization",
    responses={
        404: {"description": "Membership not found in this organization."},
        409: {"description": "The organization would be left without an owner."},
    },
)
async def delete_member(
    user_id: uuid.UUID,
    context: TenantContext = Depends(require_path_org_permission(USERS_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Remove a member from the caller's organization."""
    try:
        await remove_membership(
            db,
            organization_id=context.organization_id,
            user_id=user_id,
            actor_id=context.user_id,
        )
    except MembershipNotFound as exc:
        raise _not_found("Member not found.") from exc
    except LastOwnerRemoval as exc:
        raise _conflict("An organization must keep at least one owner.") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Branches
# ---------------------------------------------------------------------------


@router.get(
    "/{organization_id}/branches",
    response_model=BranchListEnvelope,
    summary="List branches",
)
async def get_branches(
    context: TenantContext = Depends(require_path_org_permission(BRANCHES_READ)),
    db: AsyncSession = Depends(get_db),
) -> BranchListEnvelope:
    """List the branches of the caller's organization."""
    branches = await list_branches(db, organization_id=context.organization_id)
    return BranchListEnvelope(data=branches)


@router.post(
    "/{organization_id}/branches",
    response_model=BranchEnvelope,
    status_code=status.HTTP_201_CREATED,
    summary="Create a branch",
    responses={409: {"description": "A branch with that name already exists."}},
)
async def post_branch(
    payload: BranchCreate,
    context: TenantContext = Depends(require_path_org_permission(BRANCHES_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> BranchEnvelope:
    """Create a branch inside the caller's organization."""
    try:
        branch = await create_branch(
            db,
            organization_id=context.organization_id,
            payload=payload,
            actor_id=context.user_id,
        )
    except IntegrityError as exc:
        await db.rollback()
        raise _conflict("A branch with that name already exists.") from exc
    return BranchEnvelope(data=branch)


@router.get(
    "/{organization_id}/branches/{branch_id}",
    response_model=BranchEnvelope,
    summary="Get a branch",
    responses={404: {"description": "Branch not found in this organization."}},
)
async def get_one_branch(
    branch_id: uuid.UUID,
    context: TenantContext = Depends(require_path_org_permission(BRANCHES_READ)),
    db: AsyncSession = Depends(get_db),
) -> BranchEnvelope:
    """Return one branch belonging to the caller's organization."""
    try:
        branch = await get_branch(
            db,
            organization_id=context.organization_id,
            branch_id=branch_id,
        )
    except BranchNotFound as exc:
        raise _not_found("Branch not found.") from exc
    return BranchEnvelope(data=branch)


@router.patch(
    "/{organization_id}/branches/{branch_id}",
    response_model=BranchEnvelope,
    summary="Update a branch",
    responses={
        404: {"description": "Branch not found in this organization."},
        409: {"description": "The organization must keep a main branch."},
    },
)
async def patch_branch(
    branch_id: uuid.UUID,
    payload: BranchUpdate,
    context: TenantContext = Depends(require_path_org_permission(BRANCHES_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> BranchEnvelope:
    """Apply a partial update to a branch of the caller's organization."""
    try:
        branch = await update_branch(
            db,
            organization_id=context.organization_id,
            branch_id=branch_id,
            payload=payload,
            actor_id=context.user_id,
        )
    except BranchNotFound as exc:
        raise _not_found("Branch not found.") from exc
    except MainBranchRequired as exc:
        raise _conflict(
            "Promote another branch before clearing the main branch."
        ) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise _conflict("A branch with that name already exists.") from exc
    return BranchEnvelope(data=branch)


@router.delete(
    "/{organization_id}/branches/{branch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a branch",
    responses={
        404: {"description": "Branch not found in this organization."},
        409: {"description": "The main branch cannot be deleted."},
    },
)
async def delete_one_branch(
    branch_id: uuid.UUID,
    context: TenantContext = Depends(require_path_org_permission(BRANCHES_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Soft-delete a branch of the caller's organization."""
    try:
        await delete_branch(
            db,
            organization_id=context.organization_id,
            branch_id=branch_id,
            actor_id=context.user_id,
        )
    except BranchNotFound as exc:
        raise _not_found("Branch not found.") from exc
    except MainBranchRequired as exc:
        raise _conflict(
            "Promote another branch before deleting the main branch."
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@router.get(
    "/{organization_id}/settings",
    response_model=SettingListEnvelope,
    summary="List organization settings",
)
async def get_settings(
    context: TenantContext = Depends(require_path_org_permission(TENANTS_READ)),
    db: AsyncSession = Depends(get_db),
) -> SettingListEnvelope:
    """List the organization-scoped settings of the caller's tenant."""
    settings = await list_settings(db, organization_id=context.organization_id)
    return SettingListEnvelope(data=settings)


@router.put(
    "/{organization_id}/settings",
    response_model=SettingEnvelope,
    summary="Create or replace an organization setting",
)
async def put_setting(
    payload: SettingUpsert,
    context: TenantContext = Depends(require_path_org_permission(TENANTS_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> SettingEnvelope:
    """Create or replace one setting in the caller's organization."""
    setting = await upsert_setting(
        db,
        organization_id=context.organization_id,
        payload=payload,
        actor_id=context.user_id,
    )
    return SettingEnvelope(data=setting)


# ---------------------------------------------------------------------------
# Legacy /api/v1/tenants surface
# ---------------------------------------------------------------------------

legacy_router = APIRouter()


@legacy_router.post(
    "",
    response_model=OrgEnvelope,
    status_code=status.HTTP_201_CREATED,
    deprecated=True,
    summary="Create an organization (deprecated)",
    description="Use POST /api/v1/organizations, which also provisions the tenant.",
)
async def create_organization_legacy(
    payload: OrgCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrgEnvelope:
    """Create an organization tenant via the pre-existing endpoint."""
    if current_user.organization_id is not None and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User already belongs to an organization.",
        )

    try:
        organization, _, _ = await provision_organization(
            db,
            user=current_user,
            payload=OrgProvisionRequest(**payload.model_dump()),
        )
    except SlugUnavailable as exc:
        await db.rollback()
        raise _conflict("Organization slug is already in use.") from exc
    except IntegrityError as exc:
        await db.rollback()
        raise _conflict("Organization already exists.") from exc

    return OrgEnvelope(data=organization)


@legacy_router.get(
    "/current",
    response_model=OrgEnvelope,
    summary="Get the caller's current organization",
)
async def current_organization(
    organization: Organization = Depends(get_current_org),
) -> OrgEnvelope:
    """Return the authenticated user's organization tenant."""
    return OrgEnvelope(data=organization)
