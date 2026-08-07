from __future__ import annotations

import uuid
import enum
from datetime import datetime
from typing import Optional, TYPE_CHECKING

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
from app.core.mixins import (
    TimestampMixin,
    AuditMixin,
    TenantScopedMixin,
    SoftDeleteMixin,
)
from app.core.enums import OrganizationStatus


class LeadStatus(str, enum.Enum):
    NEW = "new"
    CONTACTED = "contacted"
    TRIAL = "trial"
    FOLLOW_UP = "follow_up"
    NEGOTIATING = "negotiating"
    CONVERTED = "converted"
    LOST = "lost"


class LeadFollowUpType(str, enum.Enum):
    CALL = "call"
    VISIT = "visit"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    SMS = "sms"


class ActivityKind(str, enum.Enum):
    CALL = "call"
    EMAIL = "email"
    MEETING = "meeting"
    NOTE = "note"
    WHATSAPP = "whatsapp"
    VISIT = "visit"


class LeadSource(Base, TimestampMixin):
    __tablename__ = "lead_sources"

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
    channel: Mapped[Optional[str]] = mapped_column(Text, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    leads: Mapped[list["Lead"]] = relationship(
        "Lead",
        back_populates="source",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "uq_lead_sources_org_name",
            "organization_id",
            func.lower(name),
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<LeadSource(id={self.id}, organization_id={self.organization_id}, "
            f"name={self.name!r})>"
        )


class Lead(Base, AuditMixin):
    __tablename__ = "leads"

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
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lead_sources.id", ondelete="SET NULL"),
        default=None,
    )
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )
    status: Mapped[LeadStatus] = mapped_column(
        sa_Enum(LeadStatus, name="leadstatus"),
        nullable=False,
        default=LeadStatus.NEW,
    )
    first_name: Mapped[Optional[str]] = mapped_column(Text, default=None)
    last_name: Mapped[Optional[str]] = mapped_column(Text, default=None)
    email: Mapped[Optional[str]] = mapped_column(Text, default=None)
    phone: Mapped[Optional[str]] = mapped_column(Text, default=None)
    interested_plan: Mapped[Optional[str]] = mapped_column(Text, default=None)
    rating: Mapped[Optional[int]] = mapped_column(SmallInteger, default=None)
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        JSONB, name="metadata", default=None
    )
    converted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    converted_member_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="SET NULL"),
        default=None,
    )
    lost_reason: Mapped[Optional[str]] = mapped_column(Text, default=None)

    source: Mapped[Optional[LeadSource]] = relationship(
        "LeadSource",
        back_populates="leads",
    )
    assigned_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys="[Lead.assigned_to]",
        viewonly=True,
    )
    follow_ups: Mapped[list["LeadFollowUp"]] = relationship(
        "LeadFollowUp",
        back_populates="lead",
        cascade="all, delete-orphan",
    )
    activities: Mapped[list["LeadActivity"]] = relationship(
        "LeadActivity",
        back_populates="lead",
        cascade="all, delete-orphan",
    )

    if TYPE_CHECKING:
        from app.modules.membership.models import Member

    converted_member: Mapped[Optional["Member"]] = relationship(
        "Member",
        foreign_keys="Lead.converted_member_id",
        viewonly=True,
        uselist=False,
    )

    __table_args__ = (
        Index("ix_leads_organization_id_status", "organization_id", "status"),
        Index("ix_leads_organization_id_assigned_to", "organization_id", "assigned_to"),
        Index(
            "ix_leads_org_email_lower",
            "organization_id",
            func.lower(email),
            postgresql_where=(email.isnot(None)),
        ),
        CheckConstraint(
            "rating IS NULL OR (rating >= 1 AND rating <= 5)",
            name="ck_leads_rating_range",
        ),
         
    )

    @classmethod
    def not_deleted(cls):
        return cls.deleted_at.is_(None)

    @property
    def is_converted(self) -> bool:
        return self.converted_at is not None

    def __repr__(self) -> str:
        return (
            f"<Lead(id={self.id}, organization_id={self.organization_id}, "
            f"status={self.status}, assigned_to={self.assigned_to})>"
        )


class LeadFollowUp(Base, AuditMixin):
    __tablename__ = "lead_follow_ups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )
    type: Mapped[LeadFollowUpType] = mapped_column(
        sa_Enum(LeadFollowUpType, name="leadfollowuptype"),
        nullable=False,
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    outcome: Mapped[Optional[str]] = mapped_column(Text, default=None)
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)
    is_overdue: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    lead: Mapped[Lead] = relationship(
        "Lead",
        back_populates="follow_ups",
    )
    assignee: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys="[LeadFollowUp.assigned_to]",
        viewonly=True,
    )

    __table_args__ = (
        Index(
            "ix_lead_follow_ups_org_assignee_scheduled",
            "organization_id",
            "assigned_to",
            "scheduled_at",
        ),
        Index(
            "ix_lead_follow_ups_org_scheduled_pending",
            "organization_id",
            "scheduled_at",
            postgresql_where=(completed_at.is_(None)),
        ),
    )

    @classmethod
    def not_deleted(cls):
        return cls.deleted_at.is_(None)

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None

    def __repr__(self) -> str:
        return (
            f"<LeadFollowUp(id={self.id}, lead_id={self.lead_id}, "
            f"scheduled_at={self.scheduled_at}, is_overdue={self.is_overdue})>"
        )


class LeadActivity(Base, TimestampMixin):
    __tablename__ = "lead_activities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[ActivityKind] = mapped_column(
        sa_Enum(ActivityKind, name="activitykind"),
        nullable=False,
    )
    performed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
    )
    summary: Mapped[Optional[str]] = mapped_column(Text, default=None)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        JSONB, name="metadata", default=None
    )

    lead: Mapped[Lead] = relationship(
        "Lead",
        back_populates="activities",
    )

    __table_args__ = (
        Index("ix_lead_activities_lead_performed_at", "lead_id", "performed_at"),
        Index(
            "ix_lead_activities_organization_id_performed_by_performed_at",
            "organization_id",
            "performed_by",
            "performed_at",
        ),
    )

    def __repr__(self) -> str:
        return f"<LeadActivity(id={self.id}, lead_id={self.lead_id}, kind={self.kind})>"


class Note(Base, AuditMixin, SoftDeleteMixin):
    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_type: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    author_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        JSONB, name="metadata", default=None
    )

    __table_args__ = (
        Index("ix_notes_org_parent", "organization_id", "parent_type", "parent_id"),
        Index("ix_notes_author_id", "author_id"),
    )

    @classmethod
    def not_deleted(cls):
        return cls.deleted_at.is_(None)

    def __repr__(self) -> str:
        return (
            f"<Note(id={self.id}, organization_id={self.organization_id}, "
            f"parent_type={self.parent_type!r}, parent_id={self.parent_id})>"
        )
