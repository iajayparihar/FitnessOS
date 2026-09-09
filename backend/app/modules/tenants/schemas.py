from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    BusinessType,
    Currency,
    OrganizationMemberRole,
    OrganizationMemberStatus,
    OrganizationStatus,
)

# ---------------------------------------------------------------------------
# Organization
#
# No request schema accepts organization_id. The tenant is always resolved from
# the caller's membership server-side, so a client cannot nominate a tenant.
# ---------------------------------------------------------------------------


class OrgCreate(BaseModel):
    """Payload for creating an organization."""

    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="Optional preferred slug. Normalized, and suffixed on collision.",
    )
    business_type: BusinessType = BusinessType.GYM
    industry: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=320)
    website: str | None = Field(default=None, max_length=255)
    timezone: str = Field(default="UTC", max_length=64)
    currency: Currency = Currency.INR
    country: str | None = Field(default=None, max_length=2)
    settings: dict[str, Any] | None = None
    branding: dict[str, Any] | None = None
    billing_contact: dict[str, Any] | None = None
    data_region: str | None = Field(default=None, max_length=64)


class OrgUpdate(BaseModel):
    """Partial update for an organization's business profile."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    business_type: BusinessType | None = None
    industry: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=320)
    website: str | None = Field(default=None, max_length=255)
    timezone: str | None = Field(default=None, max_length=64)
    currency: Currency | None = None
    country: str | None = Field(default=None, max_length=2)
    branding: dict[str, Any] | None = None
    billing_contact: dict[str, Any] | None = None


class OrgResponse(BaseModel):
    """Organization response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    status: OrganizationStatus
    business_type: BusinessType
    industry: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    timezone: str
    currency: Currency
    country: str | None = None
    settings: dict[str, Any] | None = None
    branding: dict[str, Any] | None = None
    billing_contact: dict[str, Any] | None = None
    data_region: str | None = None
    created_at: datetime
    updated_at: datetime


class OrgEnvelope(BaseModel):
    """Standard single-organization response envelope."""

    data: OrgResponse


class OrgListEnvelope(BaseModel):
    """Standard organization list response envelope."""

    data: list[OrgResponse]


class OrgSummary(BaseModel):
    """An organization as seen from one of the caller's memberships."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    status: OrganizationStatus
    business_type: BusinessType
    role: OrganizationMemberRole
    is_current: bool


class OrgSummaryListEnvelope(BaseModel):
    """List of organizations the caller belongs to."""

    data: list[OrgSummary]


# ---------------------------------------------------------------------------
# Membership
# ---------------------------------------------------------------------------


class MembershipCreate(BaseModel):
    """Payload for adding an existing user to the current organization."""

    user_id: uuid.UUID
    role: OrganizationMemberRole = OrganizationMemberRole.MEMBER


class MembershipUpdate(BaseModel):
    """Payload for changing a member's seat or status."""

    role: OrganizationMemberRole | None = None
    status: OrganizationMemberStatus | None = None


class MembershipResponse(BaseModel):
    """Organization membership response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    role: OrganizationMemberRole
    status: OrganizationMemberStatus
    joined_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class MembershipEnvelope(BaseModel):
    """Standard single-membership response envelope."""

    data: MembershipResponse


class MembershipListEnvelope(BaseModel):
    """Standard membership list response envelope."""

    data: list[MembershipResponse]


# ---------------------------------------------------------------------------
# Branch
# ---------------------------------------------------------------------------


class BranchCreate(BaseModel):
    """Payload for creating a branch inside the current organization."""

    name: str = Field(min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=320)
    address: dict[str, Any] | None = None
    is_main: bool = False
    is_active: bool = True


class BranchUpdate(BaseModel):
    """Partial update for a branch."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=320)
    address: dict[str, Any] | None = None
    is_main: bool | None = None
    is_active: bool | None = None


class BranchResponse(BaseModel):
    """Branch response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    code: str | None = None
    phone: str | None = None
    email: str | None = None
    address: dict[str, Any] | None = None
    is_main: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BranchEnvelope(BaseModel):
    """Standard single-branch response envelope."""

    data: BranchResponse


class BranchListEnvelope(BaseModel):
    """Standard branch list response envelope."""

    data: list[BranchResponse]


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class SettingUpsert(BaseModel):
    """Payload for creating or replacing one organization setting."""

    key: str = Field(min_length=1, max_length=120)
    value: dict[str, Any]
    description: str | None = Field(default=None, max_length=500)


class SettingResponse(BaseModel):
    """Organization setting response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None = None
    key: str
    value: dict[str, Any]
    description: str | None = None


class SettingListEnvelope(BaseModel):
    """Standard settings list response envelope."""

    data: list[SettingResponse]


class SettingEnvelope(BaseModel):
    """Standard single-setting response envelope."""

    data: SettingResponse


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------


class OrgProvisionRequest(OrgCreate):
    """Payload for the full onboarding flow: organization plus its main branch."""

    main_branch_name: str = Field(default="Main Branch", min_length=1, max_length=200)


class OrgProvisionData(BaseModel):
    """Everything created by a successful organization provisioning."""

    organization: OrgResponse
    membership: MembershipResponse
    main_branch: BranchResponse


class OrgProvisionEnvelope(BaseModel):
    """Standard provisioning response envelope."""

    data: OrgProvisionData
