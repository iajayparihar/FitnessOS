from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.schemas import page_meta
from app.db.session import get_db
from app.modules.auth.models import User
from app.modules.crm.models import LeadStatus
from app.modules.crm.schemas import (
    FollowUpCompleteRequest,
    FollowUpCreate,
    FollowUpEnvelope,
    FollowUpListEnvelope,
    LeadConvertRequest,
    LeadCreate,
    LeadEnvelope,
    LeadListEnvelope,
    LeadLostRequest,
    LeadSourceCreate,
    LeadSourceEnvelope,
    LeadSourceListEnvelope,
    LeadUpdate,
)
from app.modules.crm.service import (
    complete_follow_up,
    convert_lead,
    create_follow_up,
    create_lead,
    create_lead_source,
    get_lead,
    list_follow_ups,
    list_lead_sources,
    list_leads,
    mark_lead_lost,
    update_lead,
)
from app.modules.rbac.dependencies import require_permission

router = APIRouter()


# --- lead sources --------------------------------------------------------------


@router.get("/lead-sources", response_model=LeadSourceListEnvelope)
async def get_lead_sources(
    current_user: User = Depends(require_permission("crm:read")),
    db: AsyncSession = Depends(get_db),
) -> LeadSourceListEnvelope:
    """List the organization's lead sources."""
    sources = await list_lead_sources(db, organization_id=current_user.organization_id)
    return LeadSourceListEnvelope(data=sources)


@router.post(
    "/lead-sources",
    response_model=LeadSourceEnvelope,
    status_code=status.HTTP_201_CREATED,
)
async def post_lead_source(
    payload: LeadSourceCreate,
    current_user: User = Depends(require_permission("crm:manage")),
    db: AsyncSession = Depends(get_db),
) -> LeadSourceEnvelope:
    """Create a lead source."""
    source = await create_lead_source(
        db, organization_id=current_user.organization_id, payload=payload
    )
    return LeadSourceEnvelope(data=source)


# --- leads ---------------------------------------------------------------------


@router.post("/leads", response_model=LeadEnvelope, status_code=status.HTTP_201_CREATED)
async def post_lead(
    payload: LeadCreate,
    current_user: User = Depends(require_permission("crm:manage")),
    db: AsyncSession = Depends(get_db),
) -> LeadEnvelope:
    """Create a lead."""
    lead = await create_lead(
        db,
        organization_id=current_user.organization_id,
        payload=payload,
        actor_id=current_user.id,
    )
    return LeadEnvelope(data=lead)


@router.get("/leads", response_model=LeadListEnvelope)
async def get_leads(
    current_user: User = Depends(require_permission("crm:read")),
    db: AsyncSession = Depends(get_db),
    status_filter: LeadStatus | None = Query(default=None, alias="status"),
    assigned_to: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> LeadListEnvelope:
    """List leads with optional filters and pagination."""
    leads, total = await list_leads(
        db,
        organization_id=current_user.organization_id,
        status=status_filter,
        assigned_to=assigned_to,
        page=page,
        page_size=page_size,
    )
    return LeadListEnvelope(
        data=leads, meta=page_meta(total=total, page=page, page_size=page_size)
    )


@router.get("/leads/{lead_id}", response_model=LeadEnvelope)
async def get_single_lead(
    lead_id: uuid.UUID,
    current_user: User = Depends(require_permission("crm:read")),
    db: AsyncSession = Depends(get_db),
) -> LeadEnvelope:
    """Fetch a single lead."""
    lead = await get_lead(
        db, organization_id=current_user.organization_id, lead_id=lead_id
    )
    return LeadEnvelope(data=lead)


@router.patch("/leads/{lead_id}", response_model=LeadEnvelope)
async def patch_lead(
    lead_id: uuid.UUID,
    payload: LeadUpdate,
    current_user: User = Depends(require_permission("crm:manage")),
    db: AsyncSession = Depends(get_db),
) -> LeadEnvelope:
    """Update a lead."""
    lead = await update_lead(
        db,
        organization_id=current_user.organization_id,
        lead_id=lead_id,
        payload=payload,
        actor_id=current_user.id,
    )
    return LeadEnvelope(data=lead)


@router.post("/leads/{lead_id}/convert", response_model=LeadEnvelope)
async def post_lead_convert(
    lead_id: uuid.UUID,
    payload: LeadConvertRequest,
    current_user: User = Depends(require_permission("crm:manage")),
    db: AsyncSession = Depends(get_db),
) -> LeadEnvelope:
    """Mark a lead as converted."""
    lead = await convert_lead(
        db,
        organization_id=current_user.organization_id,
        lead_id=lead_id,
        payload=payload,
        actor_id=current_user.id,
    )
    return LeadEnvelope(data=lead)


@router.post("/leads/{lead_id}/lost", response_model=LeadEnvelope)
async def post_lead_lost(
    lead_id: uuid.UUID,
    payload: LeadLostRequest,
    current_user: User = Depends(require_permission("crm:manage")),
    db: AsyncSession = Depends(get_db),
) -> LeadEnvelope:
    """Mark a lead as lost."""
    lead = await mark_lead_lost(
        db,
        organization_id=current_user.organization_id,
        lead_id=lead_id,
        payload=payload,
        actor_id=current_user.id,
    )
    return LeadEnvelope(data=lead)


# --- follow-ups ----------------------------------------------------------------


@router.post(
    "/leads/{lead_id}/follow-ups",
    response_model=FollowUpEnvelope,
    status_code=status.HTTP_201_CREATED,
)
async def post_follow_up(
    lead_id: uuid.UUID,
    payload: FollowUpCreate,
    current_user: User = Depends(require_permission("crm:manage")),
    db: AsyncSession = Depends(get_db),
) -> FollowUpEnvelope:
    """Schedule a follow-up on a lead."""
    follow_up = await create_follow_up(
        db,
        organization_id=current_user.organization_id,
        lead_id=lead_id,
        payload=payload,
        actor_id=current_user.id,
    )
    return FollowUpEnvelope(data=follow_up)


@router.get("/leads/{lead_id}/follow-ups", response_model=FollowUpListEnvelope)
async def get_follow_ups(
    lead_id: uuid.UUID,
    current_user: User = Depends(require_permission("crm:read")),
    db: AsyncSession = Depends(get_db),
) -> FollowUpListEnvelope:
    """List follow-ups for a lead."""
    follow_ups = await list_follow_ups(
        db, organization_id=current_user.organization_id, lead_id=lead_id
    )
    return FollowUpListEnvelope(data=follow_ups)


@router.post("/follow-ups/{follow_up_id}/complete", response_model=FollowUpEnvelope)
async def post_follow_up_complete(
    follow_up_id: uuid.UUID,
    payload: FollowUpCompleteRequest,
    current_user: User = Depends(require_permission("crm:manage")),
    db: AsyncSession = Depends(get_db),
) -> FollowUpEnvelope:
    """Complete a follow-up."""
    follow_up = await complete_follow_up(
        db,
        organization_id=current_user.organization_id,
        follow_up_id=follow_up_id,
        payload=payload,
        actor_id=current_user.id,
    )
    return FollowUpEnvelope(data=follow_up)
