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
from app.core.mixins import (
    TimestampMixin,
    AuditMixin,
    TenantScopedMixin,
    SoftDeleteMixin,
)
from app.core.enums import NotificationChannel, NotificationStatus


class RecipientType(str, enum.Enum):
    MEMBER = "member"
    USER = "user"
    CONTACT = "contact"


class NotificationTemplate(Base, AuditMixin):
    __tablename__ = "notification_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        default=None,
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[NotificationChannel] = mapped_column(
        sa_Enum(NotificationChannel, name="notificationchannel"),
        nullable=False,
    )
    subject_template: Mapped[Optional[str]] = mapped_column(Text, default=None)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    default_context: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="template",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "uq_notif_templates_org_code_channel",
            "organization_id",
            "code",
            "channel",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_notification_templates_organization_id_is_active", "organization_id", "is_active"),
    )

    @classmethod
    def not_deleted(cls):
        return cls.deleted_at.is_(None)

    def __repr__(self) -> str:
        return (
            f"<NotificationTemplate(id={self.id}, organization_id={self.organization_id}, "
            f"code={self.code!r}, channel={self.channel})>"
        )


class Notification(Base, AuditMixin):
    __tablename__ = "notifications"

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
    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notification_templates.id", ondelete="SET NULL"),
        default=None,
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        sa_Enum(NotificationChannel, name="notificationchannel"),
        nullable=False,
    )
    recipient_type: Mapped[RecipientType] = mapped_column(
        sa_Enum(RecipientType, name="recipienttype"),
        nullable=False,
    )
    recipient_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), default=None
    )
    recipient_contact: Mapped[Optional[str]] = mapped_column(Text, default=None)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(
        sa_Enum(NotificationStatus, name="notificationstatus"),
        nullable=False,
        default=NotificationStatus.PENDING,
    )
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_error: Mapped[Optional[str]] = mapped_column(Text, default=None)
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=5)

    template: Mapped[Optional[NotificationTemplate]] = relationship(
        "NotificationTemplate",
        back_populates="notifications",
    )

    logs: Mapped[list["NotificationLog"]] = relationship(
        "NotificationLog",
        back_populates="notification",
        cascade="all, delete-orphan",
    )
    preferences: Mapped[list["NotificationPreference"]] = relationship(
        "NotificationPreference",
        primaryjoin="foreign(Notification.organization_id) == NotificationPreference.organization_id",
        viewonly=True,
    )

    __table_args__ = (
        CheckConstraint(
            "attempt_count >= 0", name="ck_notifications_attempt_count_non_negative"
        ),
        CheckConstraint(
            "priority BETWEEN 1 AND 10", name="ck_notifications_priority_range"
        ),
        CheckConstraint(
            "recipient_id IS NOT NULL OR recipient_contact IS NOT NULL",
            name="ck_notifications_has_recipient",
        ),
        Index(
            "ix_notifications_pending_queue",
            "status",
            "scheduled_at",
            postgresql_where=text("status IN ('pending','queued')"),
        ),
        Index(
            "ix_notifications_organization_id_recipient",
            "organization_id",
            "recipient_type",
            "recipient_id",
            postgresql_where=recipient_id.isnot(None),
        ),
        Index("ix_notifications_organization_id_sent_at", "organization_id", sent_at.desc()),
    )

    @classmethod
    def not_deleted(cls):
        return cls.deleted_at.is_(None)

    @property
    def can_retry(self) -> bool:
        return self.attempt_count < self.max_attempts

    def __repr__(self) -> str:
        return (
            f"<Notification(id={self.id}, organization_id={self.organization_id}, "
            f"status={self.status}, channel={self.channel})>"
        )


class NotificationLog(Base, TimestampMixin):
    __tablename__ = "notification_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    notification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    was_delivered: Mapped[bool] = mapped_column(Boolean, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
    )
    gateway_response: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    gateway_event_id: Mapped[Optional[str]] = mapped_column(Text, default=None)
    error_detail: Mapped[Optional[str]] = mapped_column(Text, default=None)

    notification: Mapped[Notification] = relationship(
        "Notification",
        back_populates="logs",
    )

    __table_args__ = (
        Index("notification_id", attempted_at.desc()),
         
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationLog(id={self.id}, notification_id={self.notification_id}, "
            f"was_delivered={self.was_delivered})>"
        )


class NotificationPreference(Base, TimestampMixin):
    __tablename__ = "notification_preferences"

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
    recipient_type: Mapped[RecipientType] = mapped_column(
        sa_Enum(RecipientType, name="recipienttype"),
        nullable=False,
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        sa_Enum(NotificationChannel, name="notificationchannel"),
        nullable=False,
    )
    template_code: Mapped[str] = mapped_column(Text, nullable=False)
    is_subscribed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "recipient_type",
            "recipient_id",
            "channel",
            "template_code",
            name="uq_notif_prefs_recipient_channel_template",
        ),
        Index(
            "ix_notification_preferences_organization_id_recipient",
            "organization_id",
            "recipient_type",
            "recipient_id",
        ),
         
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationPreference(id={self.id}, organization_id={self.organization_id}, "
            f"recipient_type={self.recipient_type}, channel={self.channel})>"
        )
