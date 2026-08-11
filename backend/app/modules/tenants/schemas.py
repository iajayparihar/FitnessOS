from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import OrganizationStatus


class OrgCreate(BaseModel):
    """Payload for creating an organization."""

    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=120)
    industry: str | None = Field(default=None, max_length=120)
    settings: dict[str, Any] | None = None
    branding: dict[str, Any] | None = None
    billing_contact: dict[str, Any] | None = None
    data_region: str | None = Field(default=None, max_length=64)


class OrgResponse(BaseModel):
    """Organization response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    status: OrganizationStatus
    industry: str | None = None
    settings: dict[str, Any] | None = None
    branding: dict[str, Any] | None = None
    billing_contact: dict[str, Any] | None = None
    data_region: str | None = None
    created_at: datetime
    updated_at: datetime


class OrgEnvelope(BaseModel):
    """Standard single-organization response envelope."""

    data: OrgResponse
