from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.exceptions import (
    FollowUpAlreadyCompleted,
    FollowUpNotFound,
    LeadAlreadyConverted,
    LeadNotFound,
    LeadSourceConflict,
    LeadSourceNotFound,
)
from app.modules.crm.models import (
    ActivityKind,
    Lead,
    LeadActivity,
    LeadFollowUp,
    LeadSource,
    LeadStatus,
)
from app.modules.crm.schemas import (
    FollowUpCompleteRequest,
    FollowUpCreate,
    LeadConvertRequest,
    LeadCreate,
    LeadLostRequest,
    LeadSourceCreate,
    LeadUpdate,
)


def _record_activity(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    lead_id: uuid.UUID,
    kind: ActivityKind,
    performed_by: uuid.UUID | None,
    summary: str,
) -> None:
    db.add(
        LeadActivity(
            organization_id=organization_id,
            lead_id=lead_id,
            kind=kind,
            performed_by=performed_by,
            summary=summary,
        )
    )


# --- lead sources --------------------------------------------------------------


async def list_lead_sources(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
) -> list[LeadSource]:
    """Return active lead sources for an organization."""
    result = await db.execute(
        select(LeadSource)
        .where(
            LeadSource.organization_id == organization_id,
            LeadSource.is_active.is_(True),
        )
        .order_by(LeadSource.name)
    )
    return list(result.scalars())


async def create_lead_source(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    payload: LeadSourceCreate,
) -> LeadSource:
    """Create a lead source, rejecting duplicate names within the tenant."""
    result = await db.execute(
        select(LeadSource.id).where(
            LeadSource.organization_id == organization_id,
            func.lower(LeadSource.name) == payload.name.strip().lower(),
        )
    )
    if result.scalar_one_or_none() is not None:
        raise LeadSourceConflict

    source = LeadSource(
        organization_id=organization_id,
        name=payload.name.strip(),
        channel=payload.channel,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


async def _get_lead_source(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    source_id: uuid.UUID,
) -> LeadSource:
    result = await db.execute(
        select(LeadSource).where(
            LeadSource.id == source_id,
            LeadSource.organization_id == organization_id,
        )
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise LeadSourceNotFound
    return source


# --- leads ---------------------------------------------------------------------


async def get_lead(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    lead_id: uuid.UUID,
) -> Lead:
    """Return one non-deleted lead scoped to the organization (404 otherwise)."""
    result = await db.execute(
        select(Lead).where(
            Lead.id == lead_id,
            Lead.organization_id == organization_id,
            Lead.deleted_at.is_(None),
        )
    )
    lead = result.scalar_one_or_none()
    if lead is None:
        raise LeadNotFound
    return lead


async def create_lead(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    payload: LeadCreate,
    actor_id: uuid.UUID | None = None,
) -> Lead:
    """Create a lead within the organization."""
    if payload.source_id is not None:
        await _get_lead_source(
            db, organization_id=organization_id, source_id=payload.source_id
        )

    lead = Lead(
        organization_id=organization_id,
        branch_id=payload.branch_id,
        source_id=payload.source_id,
        assigned_to=payload.assigned_to,
        status=LeadStatus.NEW,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email.strip().lower() if payload.email else None,
        phone=payload.phone,
        interested_plan=payload.interested_plan,
        rating=payload.rating,
        notes=payload.notes,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(lead)
    await db.flush()
    _record_activity(
        db,
        organization_id=organization_id,
        lead_id=lead.id,
        kind=ActivityKind.NOTE,
        performed_by=actor_id,
        summary="Lead created.",
    )
    await db.commit()
    await db.refresh(lead)
    return lead


async def list_leads(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    status: LeadStatus | None = None,
    assigned_to: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Lead], int]:
    """Return a page of leads plus the total count for the filter."""
    conditions = [
        Lead.organization_id == organization_id,
        Lead.deleted_at.is_(None),
    ]
    if status is not None:
        conditions.append(Lead.status == status)
    if assigned_to is not None:
        conditions.append(Lead.assigned_to == assigned_to)

    total = await db.scalar(
        select(func.count()).select_from(Lead).where(*conditions)
    )
    result = await db.execute(
        select(Lead)
        .where(*conditions)
        .order_by(Lead.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars()), int(total or 0)


async def update_lead(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    lead_id: uuid.UUID,
    payload: LeadUpdate,
    actor_id: uuid.UUID | None = None,
) -> Lead:
    """Apply a partial update to a lead."""
    lead = await get_lead(db, organization_id=organization_id, lead_id=lead_id)
    updates = payload.model_dump(exclude_unset=True)
    if "source_id" in updates and updates["source_id"] is not None:
        await _get_lead_source(
            db, organization_id=organization_id, source_id=updates["source_id"]
        )
    if "email" in updates and updates["email"]:
        updates["email"] = updates["email"].strip().lower()

    for field, value in updates.items():
        setattr(lead, field, value)
    lead.updated_by = actor_id
    await db.commit()
    await db.refresh(lead)
    return lead


async def convert_lead(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    lead_id: uuid.UUID,
    payload: LeadConvertRequest,
    actor_id: uuid.UUID | None = None,
) -> Lead:
    """Mark a lead as converted."""
    lead = await get_lead(db, organization_id=organization_id, lead_id=lead_id)
    if lead.converted_at is not None:
        raise LeadAlreadyConverted

    lead.status = LeadStatus.CONVERTED
    lead.converted_at = datetime.now(UTC)
    lead.converted_member_id = payload.converted_member_id
    lead.updated_by = actor_id
    _record_activity(
        db,
        organization_id=organization_id,
        lead_id=lead.id,
        kind=ActivityKind.NOTE,
        performed_by=actor_id,
        summary="Lead converted.",
    )
    await db.commit()
    await db.refresh(lead)
    return lead


async def mark_lead_lost(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    lead_id: uuid.UUID,
    payload: LeadLostRequest,
    actor_id: uuid.UUID | None = None,
) -> Lead:
    """Mark a lead as lost with a reason."""
    lead = await get_lead(db, organization_id=organization_id, lead_id=lead_id)
    if lead.converted_at is not None:
        raise LeadAlreadyConverted

    lead.status = LeadStatus.LOST
    lead.lost_reason = payload.lost_reason.strip()
    lead.updated_by = actor_id
    _record_activity(
        db,
        organization_id=organization_id,
        lead_id=lead.id,
        kind=ActivityKind.NOTE,
        performed_by=actor_id,
        summary="Lead marked lost.",
    )
    await db.commit()
    await db.refresh(lead)
    return lead


# --- follow-ups ----------------------------------------------------------------


async def create_follow_up(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    lead_id: uuid.UUID,
    payload: FollowUpCreate,
    actor_id: uuid.UUID | None = None,
) -> LeadFollowUp:
    """Schedule a follow-up on a lead."""
    await get_lead(db, organization_id=organization_id, lead_id=lead_id)
    follow_up = LeadFollowUp(
        organization_id=organization_id,
        lead_id=lead_id,
        assigned_to=payload.assigned_to,
        type=payload.type,
        scheduled_at=payload.scheduled_at,
        notes=payload.notes,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(follow_up)
    await db.commit()
    await db.refresh(follow_up)
    return follow_up


async def list_follow_ups(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    lead_id: uuid.UUID,
) -> list[LeadFollowUp]:
    """Return follow-ups for a lead within the organization."""
    await get_lead(db, organization_id=organization_id, lead_id=lead_id)
    result = await db.execute(
        select(LeadFollowUp)
        .where(
            LeadFollowUp.organization_id == organization_id,
            LeadFollowUp.lead_id == lead_id,
            LeadFollowUp.deleted_at.is_(None),
        )
        .order_by(LeadFollowUp.scheduled_at)
    )
    return list(result.scalars())


async def complete_follow_up(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    follow_up_id: uuid.UUID,
    payload: FollowUpCompleteRequest,
    actor_id: uuid.UUID | None = None,
) -> LeadFollowUp:
    """Mark a follow-up as completed."""
    result = await db.execute(
        select(LeadFollowUp).where(
            LeadFollowUp.id == follow_up_id,
            LeadFollowUp.organization_id == organization_id,
            LeadFollowUp.deleted_at.is_(None),
        )
    )
    follow_up = result.scalar_one_or_none()
    if follow_up is None:
        raise FollowUpNotFound
    if follow_up.completed_at is not None:
        raise FollowUpAlreadyCompleted

    follow_up.completed_at = datetime.now(UTC)
    follow_up.outcome = payload.outcome
    if payload.notes is not None:
        follow_up.notes = payload.notes
    follow_up.updated_by = actor_id
    _record_activity(
        db,
        organization_id=organization_id,
        lead_id=follow_up.lead_id,
        kind=ActivityKind.NOTE,
        performed_by=actor_id,
        summary="Follow-up completed.",
    )
    await db.commit()
    await db.refresh(follow_up)
    return follow_up
