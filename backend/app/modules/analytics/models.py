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

from app.db.base import Base
from app.core.enums import ActorType

# SECURITY: This table must have NO UPDATE or DELETE privileges
# granted to the application DB role. INSERT only.


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        default=None,
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), default=None
    )
    actor_type: Mapped[ActorType] = mapped_column(
        sa_Enum(ActorType, name="actortype"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[Optional[str]] = mapped_column(Text, default=None)
    target_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), default=None
    )
    before_state: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    after_state: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    ip_address: Mapped[Optional[str]] = mapped_column(Text, default=None)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, default=None)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        JSONB, name="metadata", default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
    )

    __table_args__ = (
        Index("ix_audit_logs_org_time", "organization_id", created_at.desc()),
        Index(
            "ix_audit_logs_org_actor_time",
            "organization_id",
            "actor_id",
            created_at.desc(),
            postgresql_where=actor_id.isnot(None),
        ),
        Index(
            "ix_audit_logs_target",
            "organization_id",
            "target_type",
            "target_id",
            postgresql_where=target_id.isnot(None),
        ),
         
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, organization_id={self.organization_id}, "
            f"actor_type={self.actor_type}, action={self.action!r})>"
        )


class ReportSnapshot(Base):
    __tablename__ = "report_snapshots"

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
    report_key: Mapped[str] = mapped_column(Text, nullable=False)
    period_start: Mapped[Date] = mapped_column(Date, nullable=False)
    period_end: Mapped[Date] = mapped_column(Date, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
    )
    generated_by: Mapped[str] = mapped_column(Text, nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "report_key",
            "period_start",
            "period_end",
            name="uq_report_snapshots_org_key_period",
        ),
        CheckConstraint(
            "period_end >= period_start",
            name="ck_report_snapshots_period_order",
        ),
        Index("ix_audit_logs_organization_id_report_key_period_start", "organization_id", "report_key", period_start.desc(),
         
    ))

    def __repr__(self) -> str:
        return (
            f"<ReportSnapshot(id={self.id}, organization_id={self.organization_id}, "
            f"report_key={self.report_key!r}, period_start={self.period_start})>"
        )
