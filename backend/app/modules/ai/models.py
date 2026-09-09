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
from app.core.mixins import (
    TimestampMixin,
    AuditMixin,
    TenantScopedMixin,
    SoftDeleteMixin,
)


class AIFeatureType(str, enum.Enum):
    WORKOUT_GENERATION = "workout_generation"
    DIET_GENERATION = "diet_generation"
    CHAT_ASSISTANT = "chat_assistant"
    BUSINESS_INSIGHT = "business_insight"
    CHURN_PREDICTION = "churn_prediction"
    REVENUE_FORECAST = "revenue_forecast"


class AIFeatureUsage(Base):
    __tablename__ = "ai_feature_usage"

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
    feature_type: Mapped[AIFeatureType] = mapped_column(
        sa_Enum(AIFeatureType, name="aifeaturetype",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    model_code: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_used: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cost_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    member_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="SET NULL"),
        default=None,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )
    request_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "tokens_used >= 0", name="ck_ai_feature_usage_tokens_non_negative"
        ),
        CheckConstraint(
            "cost_paise >= 0", name="ck_ai_feature_usage_cost_non_negative"
        ),
        Index(
            "ix_ai_feature_usage_organization_id_recorded_at",
            "organization_id",
            recorded_at.desc(),
        ),
        Index(
            "ix_ai_usage_org_feature_time",
            "organization_id",
            "feature_type",
            recorded_at,
        ),
        Index(
            "ix_ai_usage_org_member_id",
            "organization_id",
            "member_id",
            postgresql_where=member_id.isnot(None),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AIFeatureUsage(id={self.id}, organization_id={self.organization_id}, "
            f"feature_type={self.feature_type}, model_code={self.model_code!r})>"
        )
