from __future__ import annotations

import uuid
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
    text,
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

# RLS POLICY — roles: organization_id = current OR is_system = true
# RLS POLICY — user_roles, api_keys: organization_id = current
# RLS POLICY — permissions, role_permissions: no filter (global read)


class Role(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "roles"

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
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index(
            "uq_roles_org_slug",
            "organization_id",
            func.lower(slug),
            unique=True,
            postgresql_where=text("organization_id IS NOT NULL AND deleted_at IS NULL"),
        ),
        Index(
            "uq_roles_system_slug",
            func.lower(slug),
            unique=True,
            postgresql_where=text("organization_id IS NULL"),
        ),
        Index("ix_roles_organization_id", "organization_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Role(id={self.id}, organization_id={self.organization_id}, "
            f"slug={self.slug!r}, is_system={self.is_system})>"
        )


class Permission(Base, TimestampMixin):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("ix_permissions_code", "code"),
    )

    def __repr__(self) -> str:
        return f"<Permission(id={self.id}, code={self.code!r}, category={self.category!r})>"


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_role_permissions_permission_id", "permission_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<RolePermission(role_id={self.role_id}, permission_id={self.permission_id}, "
            f"granted={self.granted})>"
        )


class UserRole(Base):
    __tablename__ = "user_roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_branches.id", ondelete="SET NULL"),
        default=None,
    )
    assigned_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "role_id",
            "organization_id",
            "branch_id",
            name="uq_user_roles_assignment",
        ),
        Index("ix_user_roles_organization_id_user_id", "organization_id", "user_id"),
        Index("ix_user_roles_role_id", "role_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserRole(id={self.id}, user_id={self.user_id}, role_id={self.role_id}, "
            f"organization_id={self.organization_id})>"
        )


class ApiKey(Base, AuditMixin):
    __tablename__ = "api_keys"

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
    key_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    role_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="SET NULL"),
        default=None,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("key_hash", name="uq_api_keys_hash"),
        Index("ix_api_keys_organization_id_is_active", "organization_id", "is_active"),
    )

    @classmethod
    def not_deleted(cls):
        return cls.deleted_at.is_(None)

    def is_expired(self) -> bool:
        return bool(
            self.expires_at and self.expires_at < datetime.now(self.expires_at.tzinfo)
        )

    def __repr__(self) -> str:
        return (
            f"<ApiKey(id={self.id}, organization_id={self.organization_id}, "
            f"name={self.name!r}, is_active={self.is_active})>"
        )
