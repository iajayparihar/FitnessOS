from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """
    Mixin that adds created_at and updated_at timestamps to models.
    Automatically tracks creation and modification time in UTC.
    """

    created_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """
    Mixin that adds soft delete support to models.
    Records who deleted and when, but preserves the record in the database.
    """

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        default=None,
        nullable=True,
    )
    deleted_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        default=None,
        nullable=True,
    )

    @classmethod
    def not_deleted(cls):
        """Query filter: returns only non-deleted records."""
        return cls.deleted_at.is_(None)

    @classmethod
    def is_deleted(cls):
        """Query filter: returns only deleted records."""
        return cls.deleted_at.isnot(None)


class AuditMixin(TimestampMixin, SoftDeleteMixin):
    """
    Mixin that combines timestamp and soft delete tracking with audit fields.
    Tracks who created, updated, and deleted records.
    """

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        default=None,
        nullable=True,
    )
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        default=None,
        nullable=True,
    )
    version: Mapped[int] = mapped_column(
        default=1,
        nullable=False,
    )


class TenantScopedMixin(AuditMixin):
    """
    Mixin for multi-tenant isolation.
    Every tenant-scoped model must include organization_id.
    This ensures data isolation between tenants.
    Does NOT define the `id` primary key — each model defines its own.
    """

    organization_id: Mapped[uuid.UUID] = mapped_column(
        index=True,
        nullable=False,
    )
