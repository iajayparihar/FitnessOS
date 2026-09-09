from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.tenants.schemas import OrgCreate, OrgResponse


class LoginRequest(BaseModel):
    """Payload for password login."""

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)
    organization_id: uuid.UUID | None = None


class RegisterRequest(BaseModel):
    """Payload for owner signup with organization creation."""

    organization: OrgCreate
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)
    first_name: str | None = Field(default=None, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)


class RefreshRequest(BaseModel):
    """Payload for access-token refresh."""

    refresh_token: str = Field(min_length=32)


class LogoutRequest(BaseModel):
    """Payload for refresh-token revocation."""

    refresh_token: str = Field(min_length=32)


class OnboardingRequest(BaseModel):
    """Payload for provisioning a tenant for a Clerk-authenticated user."""

    organization: OrgCreate
    first_name: str | None = Field(default=None, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)


class UserResponse(BaseModel):
    """Authenticated user response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID | None = None
    clerk_user_id: str | None = None
    email: str
    email_verified: bool
    is_active: bool
    is_superuser: bool
    last_login_at: datetime | None = None


class TokenPair(BaseModel):
    """Access and refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthData(TokenPair):
    """Authentication response data."""

    user: UserResponse
    organization: OrgResponse | None = None


class AuthResponse(BaseModel):
    """Standard auth response envelope."""

    data: AuthData


class UserEnvelope(BaseModel):
    """Standard single-user response envelope."""

    data: UserResponse


class AuthContextData(BaseModel):
    """Identity plus the FitnessOS authorization state for the current request."""

    user: UserResponse
    organization: OrgResponse | None = None
    role_slugs: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class AuthContextResponse(BaseModel):
    """Standard authenticated-context response envelope."""

    data: AuthContextData


class OnboardingData(BaseModel):
    """Result of provisioning a tenant for a Clerk-authenticated user."""

    user: UserResponse
    organization: OrgResponse


class OnboardingResponse(BaseModel):
    """Standard onboarding response envelope."""

    data: OnboardingData
