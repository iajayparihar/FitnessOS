from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PermissionResponse(BaseModel):
    """Permission response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    description: str | None = None
    category: str
    is_active: bool


class RoleCreate(BaseModel):
    """Payload for creating an organization role."""

    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    permission_codes: list[str] = Field(default_factory=list)


class RoleResponse(BaseModel):
    """Role response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID | None = None
    name: str
    slug: str
    description: str | None = None
    is_system: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AssignRoleRequest(BaseModel):
    """Payload for assigning a role to a user."""

    role_id: uuid.UUID
    branch_id: uuid.UUID | None = None


class PermissionListEnvelope(BaseModel):
    """Standard permission list response envelope."""

    data: list[PermissionResponse]


class RoleEnvelope(BaseModel):
    """Standard single-role response envelope."""

    data: RoleResponse


class RoleListEnvelope(BaseModel):
    """Standard role list response envelope."""

    data: list[RoleResponse]
