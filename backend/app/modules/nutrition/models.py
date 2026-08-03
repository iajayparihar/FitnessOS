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
from app.core.mixins import TimestampMixin, AuditMixin, TenantScopedMixin, SoftDeleteMixin


class MealType(str, enum.Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    PRE_WORKOUT = "pre_workout"
    POST_WORKOUT = "post_workout"


class FoodItem(Base, AuditMixin):
    __tablename__ = "food_items"

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
    calories_kcal: Mapped[Numeric] = mapped_column(Numeric(8, 2), nullable=False)
    protein_g: Mapped[Numeric] = mapped_column(Numeric(6, 2), nullable=False)
    carbs_g: Mapped[Numeric] = mapped_column(Numeric(6, 2), nullable=False)
    fat_g: Mapped[Numeric] = mapped_column(Numeric(6, 2), nullable=False)
    fiber_g: Mapped[Optional[Numeric]] = mapped_column(Numeric(6, 2), default=None)
    serving_size_g: Mapped[Numeric] = mapped_column(Numeric(6, 2), nullable=False, default=100)
    barcode: Mapped[Optional[str]] = mapped_column(Text, default=None)
    metadata_: Mapped[Optional[dict]] = mapped_column(JSONB, name="metadata", default=None)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            func.lower(name),
            name="uq_food_items_org_name",
        ),
        Index("organization_id"),
        Index(
            "barcode",
            postgresql_where=barcode.isnot(None),
            name="ix_food_items_barcode",
        ),
        {"extend_existing": True},
    )

    def __repr__(self) -> str:
        return (
            f"<FoodItem(id={self.id}, organization_id={self.organization_id}, "
            f"name={self.name!r})>"
        )


class MealTemplate(Base, AuditMixin):
    __tablename__ = "meal_templates"

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
    meal_type: Mapped[MealType] = mapped_column(
        sa_Enum(MealType, name="mealtype"),
        nullable=False,
    )
    items: Mapped[dict] = mapped_column(JSONB, nullable=False)
    total_calories_kcal: Mapped[Numeric] = mapped_column(Numeric(8, 2), nullable=False)
    total_protein_g: Mapped[Numeric] = mapped_column(Numeric(6, 2), nullable=False)
    total_carbs_g: Mapped[Numeric] = mapped_column(Numeric(6, 2), nullable=False)
    total_fat_g: Mapped[Numeric] = mapped_column(Numeric(6, 2), nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )

    def __repr__(self) -> str:
        return (
            f"<MealTemplate(id={self.id}, organization_id={self.organization_id}, "
            f"name={self.name!r}, meal_type={self.meal_type})>"
        )


class NutritionPlan(Base, AuditMixin):
    __tablename__ = "nutrition_plans"

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
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    target_calories_kcal: Mapped[int] = mapped_column(Integer, nullable=False)
    target_protein_g: Mapped[int] = mapped_column(Integer, nullable=False)
    target_carbs_g: Mapped[int] = mapped_column(Integer, nullable=False)
    target_fat_g: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_on: Mapped[Date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[Optional[Date]] = mapped_column(Date, default=None)
    plan_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint(
            "ends_on IS NULL OR ends_on >= starts_on",
            name="ck_nutrition_plans_date_order",
        ),
        Index("organization_id", "member_id", "is_active"),
        {"extend_existing": True},
    )

    def __repr__(self) -> str:
        return (
            f"<NutritionPlan(id={self.id}, organization_id={self.organization_id}, "
            f"member_id={self.member_id}, is_active={self.is_active})>"
        )


class NutritionLog(Base, TimestampMixin):
    __tablename__ = "nutrition_logs"

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
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    meal_type: Mapped[MealType] = mapped_column(
        sa_Enum(MealType, name="mealtype"),
        nullable=False,
    )
    items: Mapped[dict] = mapped_column(JSONB, nullable=False)
    total_calories_kcal: Mapped[Numeric] = mapped_column(Numeric(8, 2), nullable=False)
    total_protein_g: Mapped[Numeric] = mapped_column(Numeric(6, 2), nullable=False)
    total_carbs_g: Mapped[Numeric] = mapped_column(Numeric(6, 2), nullable=False)
    total_fat_g: Mapped[Numeric] = mapped_column(Numeric(6, 2), nullable=False)
    water_ml: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)

    __table_args__ = (
        Index("organization_id", "member_id", logged_at.desc()),
        {"extend_existing": True},
    )

    def __repr__(self) -> str:
        return (
            f"<NutritionLog(id={self.id}, organization_id={self.organization_id}, "
            f"member_id={self.member_id}, logged_at={self.logged_at})>"
        )


class BodyMetrics(Base, TimestampMixin):
    __tablename__ = "body_metrics"

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
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    weight_kg: Mapped[Optional[Numeric]] = mapped_column(Numeric(5, 2), default=None)
    body_fat_pct: Mapped[Optional[Numeric]] = mapped_column(Numeric(4, 2), default=None)
    muscle_mass_kg: Mapped[Optional[Numeric]] = mapped_column(Numeric(5, 2), default=None)
    bmi: Mapped[Optional[Numeric]] = mapped_column(Numeric(4, 2), default=None)
    waist_cm: Mapped[Optional[Numeric]] = mapped_column(Numeric(5, 2), default=None)
    chest_cm: Mapped[Optional[Numeric]] = mapped_column(Numeric(5, 2), default=None)
    arms_cm: Mapped[Optional[Numeric]] = mapped_column(Numeric(5, 2), default=None)
    hips_cm: Mapped[Optional[Numeric]] = mapped_column(Numeric(5, 2), default=None)
    thighs_cm: Mapped[Optional[Numeric]] = mapped_column(Numeric(5, 2), default=None)
    progress_photo_key: Mapped[Optional[str]] = mapped_column(Text, default=None)
    recorded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)

    __table_args__ = (
        CheckConstraint(
            "weight_kg IS NOT NULL OR body_fat_pct IS NOT NULL OR muscle_mass_kg IS NOT NULL OR bmi IS NOT NULL OR waist_cm IS NOT NULL OR chest_cm IS NOT NULL OR arms_cm IS NOT NULL OR hips_cm IS NOT NULL OR thighs_cm IS NOT NULL",
            name="ck_body_metrics_has_value",
        ),
        Index("organization_id", "member_id", recorded_at.desc()),
        {"extend_existing": True},
    )

    def __repr__(self) -> str:
        return (
            f"<BodyMetrics(id={self.id}, organization_id={self.organization_id}, "
            f"member_id={self.member_id}, recorded_at={self.recorded_at})>"
        )
