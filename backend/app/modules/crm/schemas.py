from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.schemas import PageMeta
from app.modules.crm.models import LeadFollowUpType, LeadStatus


# --- lead sources --------------------------------------------------------------


class LeadSourceCreate(BaseModel):
    """Payload for creating a lead source."""

    name: str = Field(min_length=1, max_length=120)
    channel: str | None = Field(default=None, max_length=120)


class LeadSourceResponse(BaseModel):
    """Lead source response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    channel: str | None = None
    is_active: bool


class LeadSourceEnvelope(BaseModel):
    data: LeadSourceResponse


class LeadSourceListEnvelope(BaseModel):
    data: list[LeadSourceResponse]


# --- leads ---------------------------------------------------------------------


class LeadCreate(BaseModel):
    """Payload for creating a lead."""

    source_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    assigned_to: uuid.UUID | None = None
    first_name: str | None = Field(default=None, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=32)
    interested_plan: str | None = Field(default=None, max_length=120)
    rating: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None


class LeadUpdate(BaseModel):
    """Payload for updating a lead (all fields optional)."""

    source_id: uuid.UUID | None = None
    assigned_to: uuid.UUID | None = None
    status: LeadStatus | None = None
    first_name: str | None = Field(default=None, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=32)
    interested_plan: str | None = Field(default=None, max_length=120)
    rating: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None


class LeadConvertRequest(BaseModel):
    """Payload for converting a lead to a member."""

    converted_member_id: uuid.UUID | None = None


class LeadLostRequest(BaseModel):
    """Payload for marking a lead as lost."""

    lost_reason: str = Field(min_length=1, max_length=500)


class LeadResponse(BaseModel):
    """Lead response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None = None
    source_id: uuid.UUID | None = None
    assigned_to: uuid.UUID | None = None
    status: LeadStatus
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    interested_plan: str | None = None
    rating: int | None = None
    notes: str | None = None
    converted_at: datetime | None = None
    converted_member_id: uuid.UUID | None = None
    lost_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class LeadEnvelope(BaseModel):
    data: LeadResponse


class LeadListEnvelope(BaseModel):
    data: list[LeadResponse]
    meta: PageMeta


# --- follow-ups ----------------------------------------------------------------


class FollowUpCreate(BaseModel):
    """Payload for scheduling a follow-up on a lead."""

    type: LeadFollowUpType
    scheduled_at: datetime
    assigned_to: uuid.UUID | None = None
    notes: str | None = None


class FollowUpCompleteRequest(BaseModel):
    """Payload for completing a follow-up."""

    outcome: str | None = Field(default=None, max_length=500)
    notes: str | None = None


class FollowUpResponse(BaseModel):
    """Follow-up response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    lead_id: uuid.UUID
    assigned_to: uuid.UUID | None = None
    type: LeadFollowUpType
    scheduled_at: datetime
    completed_at: datetime | None = None
    outcome: str | None = None
    notes: str | None = None


class FollowUpEnvelope(BaseModel):
    data: FollowUpResponse


class FollowUpListEnvelope(BaseModel):
    data: list[FollowUpResponse]


__all__ = [
    "FollowUpCompleteRequest",
    "FollowUpCreate",
    "FollowUpEnvelope",
    "FollowUpListEnvelope",
    "FollowUpResponse",
    "LeadConvertRequest",
    "LeadCreate",
    "LeadEnvelope",
    "LeadListEnvelope",
    "LeadLostRequest",
    "LeadResponse",
    "LeadSourceCreate",
    "LeadSourceEnvelope",
    "LeadSourceListEnvelope",
    "LeadSourceResponse",
    "LeadUpdate",
]
