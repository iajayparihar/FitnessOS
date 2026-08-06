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
from app.core.enums import BillingCycle


class SubscriptionStatus(str, enum.Enum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class SubscriptionPlan(Base, TimestampMixin):
    __tablename__ = "subscription_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    billing_cycle: Mapped[BillingCycle] = mapped_column(
        sa_Enum(BillingCycle, name="billingcycle"),
        nullable=False,
    )
    price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    setup_fee_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    trial_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_members: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    max_branches: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    features: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("price_cents >= 0", name="ck_sub_plans_price_positive"),
        CheckConstraint("trial_days >= 0", name="ck_sub_plans_trial_positive"),
        Index("ix_subscription_plans_active_public", "is_active", "is_public"),
    )

    def __repr__(self) -> str:
        return (
            f"<SubscriptionPlan(id={self.id}, code={self.code!r}, "
            f"billing_cycle={self.billing_cycle}, price_cents={self.price_cents})>"
        )


class PlanFeature(Base, TimestampMixin):
    __tablename__ = "plan_features"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_key: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)

    plan: Mapped[SubscriptionPlan] = relationship(
        "SubscriptionPlan",
        back_populates="features_list",
    )

    __table_args__ = (
        UniqueConstraint("plan_id", "feature_key", name="uq_plan_features_plan_key"),
    )

    def __repr__(self) -> str:
        return (
            f"<PlanFeature(id={self.id}, plan_id={self.plan_id}, "
            f"feature_key={self.feature_key!r})>"
        )


SubscriptionPlan.features_list = relationship(
    "PlanFeature",
    back_populates="plan",
    cascade="all, delete-orphan",
)


class TenantSubscription(Base, AuditMixin):
    __tablename__ = "tenant_subscriptions"

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
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        sa_Enum(SubscriptionStatus, name="subscriptionstatus"),
        nullable=False,
        default=SubscriptionStatus.TRIALING,
    )
    seats: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    next_billing_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    external_subscription_id: Mapped[Optional[str]] = mapped_column(Text, default=None)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        JSONB, name="metadata", default=None
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="subscriptions",
    )
    plan: Mapped[SubscriptionPlan] = relationship(
        "SubscriptionPlan",
        back_populates="tenant_subscriptions",
    )

    __table_args__ = (
        CheckConstraint(
            "price_cents >= 0", name="ck_tenant_subscriptions_price_positive"
        ),
        CheckConstraint("seats >= 1", name="ck_tenant_subscriptions_seats_positive"),
        Index(
            "ix_tenant_subscriptions_organization_id_status",
            "organization_id",
            "status",
        ),
        Index(
            "ix_tenant_subscriptions_next_billing_active",
            "next_billing_at",
            postgresql_where=(status == SubscriptionStatus.ACTIVE),
        ),
    )

    @classmethod
    def not_deleted(cls):
        return cls.deleted_at.is_(None)

    def __repr__(self) -> str:
        return (
            f"<TenantSubscription(id={self.id}, organization_id={self.organization_id}, "
            f"plan_id={self.plan_id}, status={self.status})>"
        )


SubscriptionPlan.tenant_subscriptions = relationship(
    "TenantSubscription",
    back_populates="plan",
    cascade="all, delete-orphan",
)


class TenantFeatureFlag(Base, TimestampMixin):
    __tablename__ = "tenant_feature_flags"

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
    feature_key: Mapped[str] = mapped_column(Text, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    config: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "feature_key", name="uq_tenant_feature_flags_org_key"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<TenantFeatureFlag(id={self.id}, organization_id={self.organization_id}, "
            f"feature_key={self.feature_key!r}, is_enabled={self.is_enabled})>"
        )
