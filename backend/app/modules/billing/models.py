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

from app.db.base import Base
from app.core.mixins import (
    TimestampMixin,
    AuditMixin,
    TenantScopedMixin,
    SoftDeleteMixin,
)
from app.core.enums import PaymentStatus, PaymentMethod


class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    VOID = "void"

class DiscountSource(str, enum.Enum):
    COUPON = "coupon"
    MANUAL = "manual"
    LOYALTY = "loyalty"
    REFERRAL = "referral"

class DiscountValueType(str, enum.Enum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"


class RefundStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"


class TaxRate(Base, TimestampMixin):
    __tablename__ = "tax_rates"

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
    name: Mapped[str] = mapped_column(Text, nullable=False)
    rate: Mapped[Numeric] = mapped_column(Numeric(5, 2), nullable=False)
    country_code: Mapped[Optional[str]] = mapped_column(String(2), default=None)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("rate >= 0 AND rate <= 100", name="ck_tax_rates_rate_range"),
        Index("ix_tax_rates_organization_id_is_active", "organization_id", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<TaxRate(id={self.id}, organization_id={self.organization_id}, "
            f"name={self.name!r}, rate={self.rate})>"
        )


class Coupon(Base, AuditMixin):
    __tablename__ = "coupons"

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
    code: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    discount_source: Mapped[DiscountSource] = mapped_column(
        sa_Enum(DiscountSource, name="discountsource",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        )
    )

    discount_value_type: Mapped[DiscountValueType] = mapped_column(
    sa_Enum(
        DiscountValueType,
        name="discountvaluetype",
        values_callable=lambda enum: [e.value for e in enum],
    ),
    nullable=False,
)
    discount_value: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    max_redemptions: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    redeemed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_from: Mapped[Optional[Date]] = mapped_column(Date, default=None)
    valid_until: Mapped[Optional[Date]] = mapped_column(Date, default=None)
    applicable_plans: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), default=None
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index(
            "uq_coupons_org_code",
            "organization_id",
            func.lower(code),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint("discount_value > 0", name="ck_coupons_value_positive"),
        CheckConstraint("discount_value_type != 'percentage' OR discount_value <= 100",
            name="ck_coupons_pct_max",
        ),
        CheckConstraint(
            "redeemed_count >= 0", name="ck_coupons_redeemed_count_non_negative"
        ),
        CheckConstraint(
            "max_redemptions IS NULL OR redeemed_count <= max_redemptions",
            name="ck_coupons_redemption_limit",
        ),
        Index("ix_coupons_organization_id_is_active", "organization_id", "is_active"),
    )

    @classmethod
    def not_deleted(cls):
        return cls.deleted_at.is_(None)

    @property
    def is_valid(self) -> bool:
        today = datetime.utcnow().date()
        if not self.is_active:
            return False
        if self.valid_from is not None and today < self.valid_from:
            return False
        if self.valid_until is not None and today > self.valid_until:
            return False
        if (
            self.max_redemptions is not None
            and self.redeemed_count >= self.max_redemptions
        ):
            return False
        return True

    def __repr__(self) -> str:
        return f"<Coupon(id={self.id}, organization_id={self.organization_id}, code={self.code!r})>"


class Invoice(Base, AuditMixin):
    __tablename__ = "invoices"

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
    membership_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memberships.id", ondelete="SET NULL"),
        default=None,
    )
    invoice_number: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        sa_Enum(InvoiceStatus, name="invoicestatus",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=InvoiceStatus.DRAFT,
    )
    issue_date: Mapped[Date] = mapped_column(
        Date, nullable=False, default=func.current_date()
    )
    due_date: Mapped[Optional[Date]] = mapped_column(Date, default=None)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    subtotal_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    discount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tax_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    paid_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)
    terms: Mapped[Optional[str]] = mapped_column(Text, default=None)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        JSONB, name="metadata", default=None
    )
    issued_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    voided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )

    member: Mapped[Optional["Member"]] = relationship(
        "Member",
        back_populates="invoices",
    )
    items: Mapped[list["InvoiceItem"]] = relationship(
        "InvoiceItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )
    discounts: Mapped[list["Discount"]] = relationship(
        "Discount",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "uq_invoices_org_number",
            "organization_id",
            "invoice_number",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint(
            "subtotal_cents >= 0", name="ck_invoices_subtotal_non_negative"
        ),
        CheckConstraint(
            "discount_cents >= 0", name="ck_invoices_discount_non_negative"
        ),
        CheckConstraint("tax_cents >= 0", name="ck_invoices_tax_non_negative"),
        CheckConstraint("total_cents >= 0", name="ck_invoices_total_non_negative"),
        CheckConstraint("paid_cents >= 0", name="ck_invoices_paid_non_negative"),
        CheckConstraint("paid_cents <= total_cents", name="ck_invoices_paid_lte_total"),
        CheckConstraint(
            "due_date IS NULL OR due_date >= issue_date",
            name="ck_invoices_due_after_issue",
        ),
        Index("ix_invoices_organization_id_status", "organization_id", "status"),
        Index("ix_invoices_organization_id_member_id", "organization_id", "member_id"),
        Index(
            "ix_invoices_outstanding_due",
            "organization_id",
            "due_date",
            postgresql_where=text("status IN ('issued','overdue')"),
        ),
        Index("ix_invoices_org_issued_at", "organization_id", issued_at.desc()),
    )

    @classmethod
    def not_deleted(cls):
        return cls.deleted_at.is_(None)

    @property
    def balance_due(self) -> int:
        return self.total_cents - self.paid_cents

    @property
    def is_fully_paid(self) -> bool:
        return self.paid_cents >= self.total_cents

    def __repr__(self) -> str:
        return (
            f"<Invoice(id={self.id}, organization_id={self.organization_id}, "
            f"invoice_number={self.invoice_number!r}, status={self.status})>"
        )


class InvoiceItem(Base, TimestampMixin):
    __tablename__ = "invoice_items"

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
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tax_rate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tax_rates.id", ondelete="SET NULL"),
        default=None,
    )
    tax_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    invoice: Mapped[Invoice] = relationship(
        "Invoice",
        back_populates="items",
    )

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_invoice_items_quantity_positive"),
        CheckConstraint(
            "unit_price_cents >= 0", name="ck_invoice_items_unit_price_non_negative"
        ),
        CheckConstraint(
            "discount_cents >= 0", name="ck_invoice_items_discount_non_negative"
        ),
        CheckConstraint(
            "tax_amount_cents >= 0", name="ck_invoice_items_tax_amount_non_negative"
        ),
        CheckConstraint(
            "amount_cents >= 0", name="ck_invoice_items_amount_non_negative"
        ),
        Index("ix_invoice_items_invoice_id", "invoice_id"),
         
    )

    def __repr__(self) -> str:
        return (
            f"<InvoiceItem(id={self.id}, invoice_id={self.invoice_id}, "
            f"description={self.description!r})>"
        )


class Discount(Base, TimestampMixin):
    __tablename__ = "discounts"

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
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    coupon_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coupons.id", ondelete="SET NULL"),
        default=None,
    )
    type: Mapped[DiscountValueType] = mapped_column(
        sa_Enum(DiscountValueType, name="discountvaluetype",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    percentage: Mapped[Optional[Numeric]] = mapped_column(Numeric(5, 2), default=None)
    reason: Mapped[Optional[str]] = mapped_column(Text, default=None)
    applied_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    invoice: Mapped[Invoice] = relationship(
        "Invoice",
        back_populates="discounts",
    )

    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="ck_discounts_amount_positive"),
        Index("ix_discounts_invoice_id", "invoice_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Discount(id={self.id}, invoice_id={self.invoice_id}, "
            f"amount_cents={self.amount_cents})>"
        )


class Payment(Base, AuditMixin):
    __tablename__ = "payments"

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
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="SET NULL"),
        default=None,
    )
    member_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="SET NULL"),
        default=None,
    )
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[PaymentStatus] = mapped_column(
        sa_Enum(PaymentStatus, name="paymentstatus",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=PaymentStatus.PENDING,
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        sa_Enum(PaymentMethod, name="paymentmethod",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    gateway: Mapped[Optional[str]] = mapped_column(Text, default=None)
    gateway_payment_id: Mapped[Optional[str]] = mapped_column(Text, default=None)
    gateway_order_id: Mapped[Optional[str]] = mapped_column(Text, default=None)
    gateway_signature: Mapped[Optional[str]] = mapped_column(Text, default=None)
    captured_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, default=None)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        JSONB, name="metadata", default=None
    )
    collected_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )

    invoice: Mapped[Optional[Invoice]] = relationship(
        "Invoice",
        back_populates="payments",
    )
    member: Mapped[Optional["Member"]] = relationship(
        "Member",
        back_populates="payments",
    )

    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="ck_payments_amount_positive"),
        Index(
            "uq_payments_gateway_payment_id",
            "gateway",
            "gateway_payment_id",
            unique=True,
            postgresql_where=gateway_payment_id.isnot(None),
        ),
        Index("ix_payments_organization_id_status", "organization_id", "status"),
        Index("ix_payments_organization_id_member_id", "organization_id", "member_id"),
        Index("ix_payments_org_captured_at", "organization_id", captured_at.desc()),
        Index(
            "ix_payments_gateway_payment_id_not_null",
            "gateway_payment_id",
            postgresql_where=func.coalesce(gateway_payment_id, "") != "",
        ),
    )

    @classmethod
    def not_deleted(cls):
        return cls.deleted_at.is_(None)

    @property
    def is_successful(self) -> bool:
        return self.status == PaymentStatus.SUCCEEDED

    def __repr__(self) -> str:
        return (
            f"<Payment(id={self.id}, organization_id={self.organization_id}, "
            f"amount_cents={self.amount_cents}, status={self.status})>"
        )


class Refund(Base, AuditMixin):
    __tablename__ = "refunds"

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
    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[RefundStatus] = mapped_column(
        sa_Enum(RefundStatus, name="refundstatus",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=RefundStatus.PENDING,
    )
    gateway_refund_id: Mapped[Optional[str]] = mapped_column(Text, default=None)
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    processed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)

    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="ck_refunds_amount_positive"),
        Index("ix_refunds_organization_id_payment_id", "organization_id", "payment_id"),
        Index("ix_refunds_organization_id_status", "organization_id", "status"),
    )

    @classmethod
    def not_deleted(cls):
        return cls.deleted_at.is_(None)

    def __repr__(self) -> str:
        return (
            f"<Refund(id={self.id}, payment_id={self.payment_id}, "
            f"amount_cents={self.amount_cents}, status={self.status})>"
        )
