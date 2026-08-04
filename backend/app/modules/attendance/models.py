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


class DeviceType(str, enum.Enum):
    QR = "qr"
    RFID = "rfid"
    MANUAL = "manual"
    KIOSK = "kiosk"
    FACE = "face"
    API = "api"


class AttendanceType(str, enum.Enum):
    CHECKIN = "checkin"
    CHECKOUT = "checkout"


class CheckinMethod(str, enum.Enum):
    QR = "qr"
    RFID = "rfid"
    MANUAL = "manual"
    FACE = "face"
    API = "api"


class AttendanceDevice(Base, AuditMixin):
    __tablename__ = "attendance_devices"

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
    branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_branches.id", ondelete="SET NULL"),
        default=None,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    device_type: Mapped[DeviceType] = mapped_column(
        sa_Enum(DeviceType, name="devicetype"),
        nullable=False,
    )
    identifier: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    metadata_: Mapped[Optional[dict]] = mapped_column(
        JSONB, name="metadata", default=None
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "identifier",
            name="uq_attendance_devices_org_identifier",
            postgresql_where=deleted_at.is_(None),
        ),
        Index("organization_id", "is_active"),
        {"extend_existing": True},
    )

    @classmethod
    def not_deleted(cls):
        return cls.deleted_at.is_(None)

    def __repr__(self) -> str:
        return (
            f"<AttendanceDevice(id={self.id}, organization_id={self.organization_id}, "
            f"identifier={self.identifier!r}, is_active={self.is_active})>"
        )


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

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
    branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_branches.id", ondelete="SET NULL"),
        default=None,
    )
    member_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="SET NULL"),
        default=None,
    )
    device_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attendance_devices.id", ondelete="SET NULL"),
        default=None,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )
    type: Mapped[AttendanceType] = mapped_column(
        sa_Enum(AttendanceType, name="attendancetype"),
        nullable=False,
    )
    method: Mapped[CheckinMethod] = mapped_column(
        sa_Enum(CheckinMethod, name="checkinmethod"),
        nullable=False,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
    )
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
    )

    # PARTITION BY RANGE (recorded_at) — implement in Alembic
    __table_args__ = (
        Index(
            "organization_id",
            recorded_at.desc(),
            name="ix_attendance_records_org_time",
        ),
        Index(
            "organization_id",
            "member_id",
            recorded_at.desc(),
            name="ix_attendance_records_member_time",
        ),
        Index(
            "organization_id",
            "branch_id",
            recorded_at.desc(),
            postgresql_where=branch_id.isnot(None),
            name="ix_attendance_records_org_branch_time",
        ),
        {"postgresql_partition_by": "RANGE (recorded_at)"},
    )

    def __repr__(self) -> str:
        return (
            f"<AttendanceRecord(id={self.id}, organization_id={self.organization_id}, "
            f"member_id={self.member_id}, recorded_at={self.recorded_at})>"
        )


class AttendanceQRToken(Base, TimestampMixin):
    __tablename__ = "attendance_qr_tokens"

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
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
    )
    token: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    is_single_use: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("token", name="uq_qr_tokens_token"),
        Index("organization_id", "member_id"),
        Index("expires_at"),
        Index("token"),
        {"extend_existing": True},
    )

    @property
    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > datetime.utcnow()

    def __repr__(self) -> str:
        return (
            f"<AttendanceQRToken(id={self.id}, organization_id={self.organization_id}, "
            f"member_id={self.member_id}, is_single_use={self.is_single_use})>"
        )
