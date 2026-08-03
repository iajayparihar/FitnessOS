from __future__ import annotations

import uuid
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String,
    Boolean,
    Integer,
    BigInteger,
    Text,
    Date,
    DateTime,
    Numeric,
    SmallInteger,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
    func,
    text,
    Enum as sa_Enum,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY, INET
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base
from app.core.mixins import TimestampMixin, AuditMixin, TenantScopedMixin, SoftDeleteMixin


class WebhookDeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


class Webhook(Base, AuditMixin):
    __tablename__ = "webhooks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    secret_hash: Mapped[str] = mapped_column(Text, nullable=False)
    event_filters: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)

    deliveries: Mapped[list["WebhookDelivery"]] = relationship(
        "WebhookDelivery",
        back_populates="webhook",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("failure_count >= 0", name="ck_webhooks_failure_count_non_negative"),
        Index("organization_id", "is_active"),
        {"extend_existing": True},
    )

    @classmethod
    def not_deleted(cls):
        return cls.deleted_at.is_(None)

    def __repr__(self) -> str:
        return (
            f"<Webhook(id={self.id}, organization_id={self.organization_id}, "
            f"name={self.name!r}, is_active={self.is_active})>"
        )


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    webhook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("webhooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[WebhookDeliveryStatus] = mapped_column(
        sa_Enum(WebhookDeliveryStatus, name="webhookdeliverystatus"),
        nullable=False,
        default=WebhookDeliveryStatus.PENDING,
    )
    response_code: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    response_body: Mapped[Optional[str]] = mapped_column(Text, default=None)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
    )

    webhook: Mapped[Webhook] = relationship(
        "Webhook",
        back_populates="deliveries",
    )

    __table_args__ = (
        CheckConstraint("retry_count >= 0", name="ck_webhook_deliveries_retry_count_non_negative"),
        Index("webhook_id", attempted_at.desc()),
        Index(
            "organization_id",
            "status",
            "next_retry_at",
            postgresql_where=text("status IN ('pending','retrying')"),
            name="ix_webhook_deliveries_retry_queue",
        ),
        {"extend_existing": True},
    )

    def __repr__(self) -> str:
        return (
            f"<WebhookDelivery(id={self.id}, webhook_id={self.webhook_id}, "
            f"status={self.status}, attempted_at={self.attempted_at})>"
        )
