from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.tenants.schemas import OrgCreate, OrgResponse


class OnboardingRequest(BaseModel):
    """Payload for an authenticated user to create their organization."""

    organization: OrgCreate


class InviteAcceptRequest(BaseModel):
    """Payload for accepting an organization invite."""

    token: str = Field(min_length=1, max_length=512)


class UserResponse(BaseModel):
    """Authenticated user response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID | None = None
    email: str
    email_verified: bool
    is_active: bool
    is_superuser: bool
    last_login_at: datetime | None = None


class AccountData(BaseModel):
    """User plus resolved organization after onboarding or invite acceptance."""

    user: UserResponse
    organization: OrgResponse | None = None


class AccountResponse(BaseModel):
    """Standard account response envelope."""

    data: AccountData


class UserEnvelope(BaseModel):
    """Standard single-user response envelope."""

    data: UserResponse
