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
from app.core.enums import PaymentMethod


class EmploymentType(str, enum.Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    FREELANCE = "freelance"


class PaySchedule(str, enum.Enum):
    MONTHLY = "monthly"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"


class PayrollRunStatus(str, enum.Enum):
    DRAFT = "draft"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ExpenseCategory(Base, TimestampMixin):
    __tablename__ = "expense_categories"

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
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    color: Mapped[Optional[str]] = mapped_column(Text, default=None)

    __table_args__ = (
        Index(
            "uq_expense_categories_org_name",
            "organization_id",
            func.lower(name),
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ExpenseCategory(id={self.id}, organization_id={self.organization_id}, "
            f"name={self.name!r})>"
        )


class Expense(Base, AuditMixin):
    __tablename__ = "expenses"

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
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expense_categories.id", ondelete="SET NULL"),
        default=None,
    )
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    incurred_at: Mapped[Date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    vendor_name: Mapped[Optional[str]] = mapped_column(Text, default=None)
    receipt_file_key: Mapped[Optional[str]] = mapped_column(Text, default=None)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        sa_Enum(PaymentMethod, name="paymentmethod",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    is_recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recurrence_interval: Mapped[Optional[str]] = mapped_column(Text, default=None)

    category: Mapped[Optional[ExpenseCategory]] = relationship(
        "ExpenseCategory",
    )

    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="ck_expenses_amount_positive"),
        Index("ix_expenses_organization_id_incurred_at", "organization_id", incurred_at.desc()),
        Index("ix_expenses_organization_id_category_id", "organization_id", "category_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Expense(id={self.id}, organization_id={self.organization_id}, "
            f"amount_cents={self.amount_cents}, incurred_at={self.incurred_at})>"
        )


class PayrollEmployee(Base, AuditMixin):
    __tablename__ = "payroll_employees"

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
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    employment_type: Mapped[EmploymentType] = mapped_column(
        sa_Enum(EmploymentType, name="employmenttype",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    designation: Mapped[Optional[str]] = mapped_column(Text, default=None)
    salary_cents: Mapped[Optional[int]] = mapped_column(BigInteger, default=None)
    pay_schedule: Mapped[PaySchedule] = mapped_column(
        sa_Enum(PaySchedule, name="payschedule",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=PaySchedule.MONTHLY,
    )
    bank_account_vault_key: Mapped[Optional[str]] = mapped_column(Text, default=None)
    joining_date: Mapped[Optional[Date]] = mapped_column(Date, default=None)
    leaving_date: Mapped[Optional[Date]] = mapped_column(Date, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index(
            "uq_payroll_employees_org_user",
            "organization_id",
            "user_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint(
            "salary_cents IS NULL OR salary_cents >= 0",
            name="ck_payroll_employees_salary_non_negative",
        ),
        CheckConstraint(
            "leaving_date IS NULL OR leaving_date >= joining_date",
            name="ck_payroll_employees_leaving_after_joining",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PayrollEmployee(id={self.id}, organization_id={self.organization_id}, "
            f"user_id={self.user_id}, employment_type={self.employment_type})>"
        )


class PayrollRun(Base, AuditMixin):
    __tablename__ = "payroll_runs"

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
    period_start: Mapped[Date] = mapped_column(Date, nullable=False)
    period_end: Mapped[Date] = mapped_column(Date, nullable=False)
    status: Mapped[PayrollRunStatus] = mapped_column(
        sa_Enum(PayrollRunStatus, name="payrollrunstatus",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=PayrollRunStatus.DRAFT,
    )
    total_gross_cents: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    total_deductions_cents: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    total_net_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    processed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )

    items: Mapped[list["PayrollItem"]] = relationship(
        "PayrollItem",
        back_populates="payroll_run",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "period_end >= period_start", name="ck_payroll_runs_period_order"
        ),
        CheckConstraint(
            "total_gross_cents >= 0", name="ck_payroll_runs_gross_non_negative"
        ),
        CheckConstraint(
            "total_net_cents >= 0", name="ck_payroll_runs_net_non_negative"
        ),
        Index(
            "ix_payroll_runs_organization_id_period_start",
            "organization_id",
            period_start.desc(),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PayrollRun(id={self.id}, organization_id={self.organization_id}, "
            f"period_start={self.period_start}, status={self.status})>"
        )


class PayrollItem(Base, TimestampMixin):
    __tablename__ = "payroll_items"

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
    payroll_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payroll_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payroll_employees.id", ondelete="RESTRICT"),
        nullable=False,
    )
    gross_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deductions: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    net_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payment_ref: Mapped[Optional[str]] = mapped_column(Text, default=None)
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )

    payroll_run: Mapped[PayrollRun] = relationship(
        "PayrollRun",
        back_populates="items",
    )

    __table_args__ = (
        CheckConstraint("gross_cents >= 0", name="ck_payroll_items_gross_non_negative"),
        CheckConstraint("net_cents >= 0", name="ck_payroll_items_net_non_negative"),
        CheckConstraint(
            "net_cents <= gross_cents", name="ck_payroll_items_net_lte_gross"
        ),
        UniqueConstraint(
            "payroll_run_id", "employee_id", name="uq_payroll_items_run_employee"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PayrollItem(id={self.id}, payroll_run_id={self.payroll_run_id}, "
            f"employee_id={self.employee_id}, net_cents={self.net_cents})>"
        )
