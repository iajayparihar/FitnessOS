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
    text,
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
from app.core.enums import BillingCycle, Gender


class MemberStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    FROZEN = "frozen"
    BLOCKED = "blocked"
    PENDING = "pending"


class MembershipStatus(str, enum.Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PENDING = "pending"


class BloodGroup(str, enum.Enum):
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    O_POS = "O+"
    O_NEG = "O-"


class DocumentType(str, enum.Enum):
    ID_PROOF = "id_proof"
    MEDICAL_CERT = "medical_cert"
    WAIVER = "waiver"
    AGREEMENT = "agreement"
    PHOTO = "photo"
    OTHER = "other"


class MembershipPlan(Base, AuditMixin):
    __tablename__ = "membership_plans"

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
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    billing_cycle: Mapped[BillingCycle] = mapped_column(
        sa_Enum(BillingCycle, name="billingcycle"),
        nullable=False,
    )
    duration_days: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    max_visits: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    max_freeze_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        JSONB, name="metadata", default=None
    )

    __table_args__ = (
        Index(
            "uq_membership_plans_org_slug",
            "organization_id",
            func.lower(slug),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint("price_cents >= 0", name="ck_membership_plans_price_positive"),
        Index("ix_membership_plans_organization_id_is_active", "organization_id", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<MembershipPlan(id={self.id}, organization_id={self.organization_id}, "
            f"slug={self.slug!r}, is_active={self.is_active})>"
        )


class Member(Base, AuditMixin):
    __tablename__ = "members"

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
    member_code: Mapped[str] = mapped_column(Text, nullable=False)
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(Text, default=None)
    email: Mapped[Optional[str]] = mapped_column(Text, default=None)
    phone: Mapped[Optional[str]] = mapped_column(Text, default=None)
    dob: Mapped[Optional[Date]] = mapped_column(Date, default=None)
    gender: Mapped[Optional[Gender]] = mapped_column(
        sa_Enum(Gender, name="gender"),
        default=None,
    )
    status: Mapped[MemberStatus] = mapped_column(
        sa_Enum(MemberStatus, name="memberstatus"),
        nullable=False,
        default=MemberStatus.ACTIVE,
    )
    photo_url: Mapped[Optional[str]] = mapped_column(Text, default=None)
    tags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), default=None)
    referred_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="SET NULL"),
        default=None,
    )
    metadata_: Mapped[Optional[dict]] = mapped_column(
        JSONB, name="metadata", default=None
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )

    profile: Mapped[Optional["MemberProfile"]] = relationship(
        "MemberProfile",
        back_populates="member",
        uselist=False,
        cascade="all, delete-orphan",
    )
    documents: Mapped[list["MemberDocument"]] = relationship(
        "MemberDocument",
        back_populates="member",
        cascade="all, delete-orphan",
    )
    memberships: Mapped[list["Membership"]] = relationship(
        "Membership",
        back_populates="member",
        cascade="all, delete-orphan",
    )
    emergency_contacts: Mapped[list["MemberEmergencyContact"]] = relationship(
        "MemberEmergencyContact",
        back_populates="member",
        cascade="all, delete-orphan",
    )
    referrer: Mapped[Optional["Member"]] = relationship(
        "Member",
        remote_side="Member.id",
        foreign_keys="Member.referred_by",
        back_populates="referrals",
        uselist=False,
    )
    referrals: Mapped[list["Member"]] = relationship(
        "Member",
        foreign_keys="Member.referred_by",
        back_populates="referrer",
    )

    if TYPE_CHECKING:
        from app.modules.attendance.models import AttendanceRecord
        from app.modules.trainer.models import WorkoutAssignment
        from app.modules.nutrition.models import NutritionPlan, BodyMetrics
        from app.modules.billing.models import Invoice, Payment

    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(
        "AttendanceRecord",
        back_populates="member",
        cascade="all, delete-orphan",
    )

    workout_assignments: Mapped[list["WorkoutAssignment"]] = relationship(
        "WorkoutAssignment",
        back_populates="member",
        cascade="all, delete-orphan",
    )

    nutrition_plans: Mapped[list["NutritionPlan"]] = relationship(
        "NutritionPlan",
        back_populates="member",
        cascade="all, delete-orphan",
    )

    body_metrics: Mapped[list["BodyMetrics"]] = relationship(
        "BodyMetrics",
        back_populates="member",
        cascade="all, delete-orphan",
    )

    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice",
        back_populates="member",
        cascade="all, delete-orphan",
    )

    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="member",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "member_code", name="uq_members_org_member_code"
        ),
        Index(
            "ix_members_org_email",
            "organization_id",
            func.lower(email),
            postgresql_where=text("email IS NOT NULL AND deleted_at IS NULL"),
        ),
        Index("ix_members_organization_id_status", "organization_id", "status"),
        Index(
            "ix_members_org_phone",
            "organization_id",
            func.lower(phone),
            postgresql_where=phone.isnot(None),
        ),
    )

    @classmethod
    def not_deleted(cls):
        return cls.deleted_at.is_(None)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name or ''}".strip()

    def __repr__(self) -> str:
        return (
            f"<Member(id={self.id}, organization_id={self.organization_id}, "
            f"member_code={self.member_code!r}, status={self.status})>"
        )


class MemberProfile(Base, TimestampMixin):
    __tablename__ = "member_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    medical_notes: Mapped[Optional[str]] = mapped_column(Text, default=None)
    blood_group: Mapped[Optional[BloodGroup]] = mapped_column(
        sa_Enum(BloodGroup, name="bloodgroup"),
        default=None,
    )
    allergies: Mapped[Optional[str]] = mapped_column(Text, default=None)
    fitness_goal: Mapped[Optional[str]] = mapped_column(Text, default=None)
    occupation: Mapped[Optional[str]] = mapped_column(Text, default=None)
    preferences: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)

    member: Mapped[Member] = relationship(
        "Member",
        back_populates="profile",
    )

    def __repr__(self) -> str:
        return f"<MemberProfile(id={self.id}, member_id={self.member_id})>"


class MemberEmergencyContact(Base, TimestampMixin):
    __tablename__ = "member_emergency_contacts"

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
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    relation: Mapped[str] = mapped_column(Text, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    member: Mapped[Member] = relationship(
        "Member",
        back_populates="emergency_contacts",
    )

    def __repr__(self) -> str:
        return (
            f"<MemberEmergencyContact(id={self.id}, member_id={self.member_id}, "
            f"name={self.name!r})>"
        )


class MemberDocument(Base, TimestampMixin):
    __tablename__ = "member_documents"

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
        index=True,
    )
    document_type: Mapped[DocumentType] = mapped_column(
        sa_Enum(DocumentType, name="documenttype"),
        nullable=False,
    )
    file_key: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, default=None)
    mime_type: Mapped[Optional[str]] = mapped_column(Text, default=None)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
    )
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verified_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )

    member: Mapped[Member] = relationship(
        "Member",
        back_populates="documents",
    )

    __table_args__ = (
        Index("ix_member_documents_organization_id_member_id", "organization_id", "member_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<MemberDocument(id={self.id}, member_id={self.member_id}, "
            f"document_type={self.document_type})>"
        )


class Membership(Base, AuditMixin):
    __tablename__ = "memberships"

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
        index=True,
    )
    membership_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("membership_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_branches.id", ondelete="SET NULL"),
        default=None,
    )
    starts_on: Mapped[Date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[Optional[Date]] = mapped_column(Date, default=None)
    status: Mapped[MembershipStatus] = mapped_column(
        sa_Enum(MembershipStatus, name="membershipstatus"),
        nullable=False,
        default=MembershipStatus.ACTIVE,
    )
    auto_renew: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    freeze_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_freeze_days_used: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    coupon_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), default=None
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    cancelled_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, default=None)

    member: Mapped[Member] = relationship(
        "Member",
        back_populates="memberships",
    )
    plan: Mapped[MembershipPlan] = relationship(
        "MembershipPlan",
        back_populates="memberships",
    )
    freezes: Mapped[list["MembershipFreeze"]] = relationship(
        "MembershipFreeze",
        back_populates="membership",
        cascade="all, delete-orphan",
    )
    transfers: Mapped[list["MembershipTransfer"]] = relationship(
        "MembershipTransfer",
        back_populates="membership",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "ends_on IS NULL OR ends_on >= starts_on", name="ck_memberships_date_order"
        ),
        CheckConstraint(
            "freeze_count >= 0", name="ck_memberships_freeze_count_non_negative"
        ),
        Index("ix_memberships_organization_id_member_id", "organization_id", "member_id"),
        Index("ix_memberships_organization_id_status", "organization_id", "status"),
        Index(
            "ix_memberships_active_expiry",
            "organization_id",
            "ends_on",
            postgresql_where=(status == MembershipStatus.ACTIVE),
        ),
    )

    @classmethod
    def not_deleted(cls):
        return cls.deleted_at.is_(None)

    @property
    def is_expired(self) -> bool:
        return self.ends_on is not None and self.ends_on < datetime.utcnow().date()

    def __repr__(self) -> str:
        return (
            f"<Membership(id={self.id}, member_id={self.member_id}, "
            f"membership_plan_id={self.membership_plan_id}, status={self.status})>"
        )


MembershipPlan.memberships = relationship(
    "Membership",
    back_populates="plan",
    cascade="all, delete-orphan",
)


class MembershipFreeze(Base, TimestampMixin):
    __tablename__ = "membership_freezes"

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
    membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memberships.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    frozen_at: Mapped[Date] = mapped_column(Date, nullable=False)
    resumes_at: Mapped[Date] = mapped_column(Date, nullable=False)
    actual_resumed_at: Mapped[Optional[Date]] = mapped_column(Date, default=None)
    reason: Mapped[Optional[str]] = mapped_column(Text, default=None)
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )
    days_frozen: Mapped[int] = mapped_column(Integer, nullable=False)

    membership: Mapped[Membership] = relationship(
        "Membership",
        back_populates="freezes",
    )

    __table_args__ = (
        CheckConstraint("resumes_at > frozen_at", name="ck_freeze_dates"),
        CheckConstraint("days_frozen > 0", name="ck_freeze_days_positive"),
    )

    def __repr__(self) -> str:
        return (
            f"<MembershipFreeze(id={self.id}, membership_id={self.membership_id}, "
            f"days_frozen={self.days_frozen})>"
        )


class MembershipTransfer(Base, TimestampMixin):
    __tablename__ = "membership_transfers"

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
    membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memberships.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    from_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="RESTRICT"),
        nullable=False,
    )
    to_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="RESTRICT"),
        nullable=False,
    )
    transferred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, default=None)
    transferred_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    membership: Mapped[Membership] = relationship(
        "Membership",
        back_populates="transfers",
    )

    __table_args__ = (
        CheckConstraint(
            "from_member_id != to_member_id", name="ck_transfer_different_members"
        ),
        Index("ix_membership_transfers_organization_id_to_member_id", "organization_id", "to_member_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<MembershipTransfer(id={self.id}, membership_id={self.membership_id}, "
            f"from_member_id={self.from_member_id}, to_member_id={self.to_member_id})>"
        )
