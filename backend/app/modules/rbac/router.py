import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.models import User
from app.modules.rbac.dependencies import require_permission
from app.modules.rbac.exceptions import (
    BranchNotInOrganization,
    PermissionNotFound,
    RoleNotFound,
    UserNotInOrganization,
)
from app.modules.rbac.schemas import (
    AssignRoleRequest,
    PermissionListEnvelope,
    RoleCreate,
    RoleEnvelope,
    RoleListEnvelope,
)
from app.modules.rbac.service import (
    assign_role_to_user,
    create_role,
    list_permissions,
    list_roles,
)

router = APIRouter()


@router.get("/permissions", response_model=PermissionListEnvelope)
async def get_permissions(
    _: User = Depends(require_permission("rbac:read")),
    db: AsyncSession = Depends(get_db),
) -> PermissionListEnvelope:
    """List active permissions."""
    permissions = await list_permissions(db)
    return PermissionListEnvelope(data=permissions)


@router.get("/roles", response_model=RoleListEnvelope)
async def get_roles(
    current_user: User = Depends(require_permission("rbac:read")),
    db: AsyncSession = Depends(get_db),
) -> RoleListEnvelope:
    """List roles visible to the current organization."""
    roles = await list_roles(db, organization_id=current_user.organization_id)
    return RoleListEnvelope(data=roles)


@router.post(
    "/roles",
    response_model=RoleEnvelope,
    status_code=status.HTTP_201_CREATED,
)
async def post_role(
    payload: RoleCreate,
    current_user: User = Depends(require_permission("rbac:manage")),
    db: AsyncSession = Depends(get_db),
) -> RoleEnvelope:
    """Create a role for the current organization."""
    try:
        role = await create_role(
            db,
            organization_id=current_user.organization_id,
            payload=payload,
        )
    except PermissionNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown permission: {exc}",
        ) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role already exists.",
        ) from exc
    return RoleEnvelope(data=role)


@router.post("/users/{user_id}/roles", status_code=status.HTTP_204_NO_CONTENT)
async def post_user_role(
    user_id: uuid.UUID,
    payload: AssignRoleRequest,
    current_user: User = Depends(require_permission("rbac:manage")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Assign a role to a user in the current organization."""
    try:
        await assign_role_to_user(
            db,
            user_id=user_id,
            role_id=payload.role_id,
            organization_id=current_user.organization_id,
            assigned_by=current_user.id,
            branch_id=payload.branch_id,
        )
        await db.commit()
    except RoleNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found.",
        ) from exc
    except UserNotInOrganization as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        ) from exc
    except BranchNotInOrganization as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found.",
        ) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role assignment already exists.",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
