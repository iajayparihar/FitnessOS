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
from app.modules.membership.models import Member


class WorkoutDifficulty(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class AssignmentStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Trainer(Base, AuditMixin):
    __tablename__ = "trainers"

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
    branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_branches.id", ondelete="SET NULL"),
        default=None,
    )
    specialties: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), default=None)
    bio: Mapped[Optional[str]] = mapped_column(Text, default=None)
    hourly_rate_cents: Mapped[Optional[int]] = mapped_column(BigInteger, default=None)
    certifications: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    workout_assignments: Mapped[list["WorkoutAssignment"]] = relationship(
        "WorkoutAssignment",
        back_populates="trainer",
        cascade="all, delete-orphan",
    )
    trainer_member_assignments: Mapped[list["TrainerMemberAssignment"]] = relationship(
        "TrainerMemberAssignment",
        back_populates="trainer",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_trainers_org_user"),
    )

    def __repr__(self) -> str:
        return (
            f"<Trainer(id={self.id}, organization_id={self.organization_id}, "
            f"user_id={self.user_id}, is_active={self.is_active})>"
        )


class ExerciseTemplate(Base, AuditMixin):
    __tablename__ = "exercise_templates"

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
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    muscle_groups: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), default=None
    )
    equipment_needed: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text), default=None
    )
    instructions: Mapped[Optional[str]] = mapped_column(Text, default=None)
    video_url: Mapped[Optional[str]] = mapped_column(Text, default=None)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(Text, default=None)
    is_global: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index(
            "uq_exercise_templates_org_name",
            "organization_id",
            func.lower(name),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_exercise_templates_organization_id_is_global", "organization_id", "is_global"),
    )

    def __repr__(self) -> str:
        return (
            f"<ExerciseTemplate(id={self.id}, organization_id={self.organization_id}, "
            f"name={self.name!r}, is_global={self.is_global})>"
        )


class WorkoutTemplate(Base, AuditMixin):
    __tablename__ = "workout_templates"

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
    difficulty: Mapped[WorkoutDifficulty] = mapped_column(
        sa_Enum(WorkoutDifficulty, name="workoutdifficulty",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    estimated_duration_minutes: Mapped[Optional[int]] = mapped_column(
        Integer, default=None
    )
    exercises: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )

    workout_assignments: Mapped[list["WorkoutAssignment"]] = relationship(
        "WorkoutAssignment",
        back_populates="workout_template",
        cascade="all, delete-orphan",
    )
    workout_logs: Mapped[list["WorkoutLog"]] = relationship(
        "WorkoutLog",
        back_populates="workout_template",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
    )

    def __repr__(self) -> str:
        return (
            f"<WorkoutTemplate(id={self.id}, organization_id={self.organization_id}, "
            f"name={self.name!r}, difficulty={self.difficulty})>"
        )


class WorkoutAssignment(Base, AuditMixin):
    __tablename__ = "workout_assignments"

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
    trainer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trainers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workout_template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workout_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    starts_on: Mapped[Date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[Optional[Date]] = mapped_column(Date, default=None)
    status: Mapped[AssignmentStatus] = mapped_column(
        sa_Enum(AssignmentStatus, name="assignmentstatus",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=AssignmentStatus.ACTIVE,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)

    trainer: Mapped[Trainer] = relationship(
        "Trainer",
        back_populates="workout_assignments",
    )
    member: Mapped["Member"] = relationship(
        "Member",
        back_populates="workout_assignments",
    )
    workout_template: Mapped[WorkoutTemplate] = relationship(
        "WorkoutTemplate",
        back_populates="workout_assignments",
    )
    workout_logs: Mapped[list["WorkoutLog"]] = relationship(
        "WorkoutLog",
        back_populates="workout_assignment",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "ends_on IS NULL OR ends_on >= starts_on",
            name="ck_workout_assignments_date_order",
        ),
        Index(
            "uq_workout_assignments_active",
            "organization_id",
            "member_id",
            "trainer_id",
            "workout_template_id",
            unique=True,
            postgresql_where=text("status = 'active' AND deleted_at IS NULL"),
        ),
        Index("ix_workout_assignments_organization_id_member_id_status", "organization_id", "member_id", "status"),
        Index("ix_workout_assignments_organization_id_trainer_id_status", "organization_id", "trainer_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<WorkoutAssignment(id={self.id}, organization_id={self.organization_id}, "
            f"member_id={self.member_id}, trainer_id={self.trainer_id}, status={self.status})>"
        )


class WorkoutLog(Base, TimestampMixin):
    __tablename__ = "workout_logs"

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
    workout_assignment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workout_assignments.id", ondelete="SET NULL"),
        default=None,
    )
    workout_template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workout_templates.id", ondelete="SET NULL"),
        default=None,
    )
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exercises_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    perceived_exertion: Mapped[Optional[int]] = mapped_column(
        SmallInteger, default=None
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)

    workout_assignment: Mapped[Optional[WorkoutAssignment]] = relationship(
        "WorkoutAssignment",
        back_populates="workout_logs",
    )
    workout_template: Mapped[Optional[WorkoutTemplate]] = relationship(
        "WorkoutTemplate",
        back_populates="workout_logs",
    )

    __table_args__ = (
        CheckConstraint(
            "perceived_exertion IS NULL OR (perceived_exertion >= 1 AND perceived_exertion <= 10)",
            name="ck_workout_logs_exertion_range",
        ),
        Index("ix_workout_logs_organization_id_member_id_logged_at", "organization_id", "member_id", logged_at.desc()),
    )

    def __repr__(self) -> str:
        return (
            f"<WorkoutLog(id={self.id}, organization_id={self.organization_id}, "
            f"member_id={self.member_id}, logged_at={self.logged_at})>"
        )


class TrainerMemberAssignment(Base, AuditMixin):
    __tablename__ = "trainer_member_assignments"

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
    trainer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trainers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_on: Mapped[Date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[Optional[Date]] = mapped_column(Date, default=None)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)

    trainer: Mapped[Trainer] = relationship(
        "Trainer",
        back_populates="trainer_member_assignments",
    )

    __table_args__ = (
        Index(
            "uq_trainer_member_assignments_primary",
            "organization_id",
            "trainer_id",
            "member_id",
            unique=True,
            postgresql_where=text("is_primary IS TRUE AND deleted_at IS NULL"),
        ),
        Index(
            "ix_trainer_member_assignments_org_member_primary",
            "organization_id",
            "member_id",
            "is_primary",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<TrainerMemberAssignment(id={self.id}, organization_id={self.organization_id}, "
            f"trainer_id={self.trainer_id}, member_id={self.member_id}, is_primary={self.is_primary})>"
        )
