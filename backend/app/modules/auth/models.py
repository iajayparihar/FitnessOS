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
from app.modules.tenants.models import Organization


class AuthProvider(str, enum.Enum):
    PASSWORD = "password"
    GOOGLE = "google"
    APPLE = "apple"
    TOTP = "totp"
    SAML = "saml"
    MAGICLINK = "magiclink"


class User(Base, AuditMixin):
    __tablename__ = "users"

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
    email: Mapped[str] = mapped_column(Text, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    metadata_: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        name="metadata",
        default=None,
    )

    organization: Mapped[Optional["Organization"]] = relationship(
        "Organization",
        primaryjoin="User.organization_id == foreign(Organization.id)",
        viewonly=True,
    )
    profile: Mapped[Optional["UserProfile"]] = relationship(
        "UserProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    auth_methods: Mapped[list["UserAuthMethod"]] = relationship(
        "UserAuthMethod",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    if TYPE_CHECKING:
        from app.modules.trainer.models import Trainer
        from app.modules.expenses.models import PayrollEmployee

    trainer_profile: Mapped[Optional["Trainer"]] = relationship(
        "Trainer",
        primaryjoin="User.id == foreign(Trainer.user_id)",
        uselist=False,
        viewonly=True,
    )

    payroll_employee: Mapped[Optional["PayrollEmployee"]] = relationship(
        "PayrollEmployee",
        primaryjoin="User.id == foreign(PayrollEmployee.user_id)",
        uselist=False,
        viewonly=True,
    )

    __table_args__ = (
        Index("ix_users_organization_id", "organization_id"),
        Index("ix_users_email_lower", func.lower(email)),
        Index(
            "uq_users_org_email",
            func.lower(email),
            unique=True,
            postgresql_where=text("organization_id IS NOT NULL AND deleted_at IS NULL"),
        ),
        Index(
            "uq_users_platform_email",
            func.lower(email),
            unique=True,
            postgresql_where=text("organization_id IS NULL AND deleted_at IS NULL"),
        ),
    )

    @classmethod
    def not_deleted(cls):
        return cls.deleted_at.is_(None)

    def __repr__(self) -> str:
        return (
            f"<User(id={self.id}, email={self.email!r}, "
            f"organization_id={self.organization_id}, is_superuser={self.is_superuser})>"
        )


class UserProfile(Base, TimestampMixin):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    first_name: Mapped[Optional[str]] = mapped_column(Text, default=None)
    last_name: Mapped[Optional[str]] = mapped_column(Text, default=None)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, default=None)
    phone: Mapped[Optional[str]] = mapped_column(Text, default=None)
    bio: Mapped[Optional[str]] = mapped_column(Text, default=None)
    date_of_birth: Mapped[Optional[datetime]] = mapped_column(Date, default=None)

    user: Mapped[User] = relationship(
        "User",
        back_populates="profile",
    )

    def __repr__(self) -> str:
        return (
            f"<UserProfile(id={self.id}, user_id={self.user_id}, "
            f"first_name={self.first_name!r}, last_name={self.last_name!r})>"
        )


class UserAuthMethod(Base, TimestampMixin):
    __tablename__ = "user_auth_methods"

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
    provider: Mapped[AuthProvider] = mapped_column(
        sa_Enum(AuthProvider, name="authprovider"),
        nullable=False,
    )
    provider_uid: Mapped[Optional[str]] = mapped_column(Text, default=None)
    password_hash: Mapped[Optional[str]] = mapped_column(Text, default=None)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )

    user: Mapped[User] = relationship(
        "User",
        back_populates="auth_methods",
    )

    __table_args__ = (
        CheckConstraint(
            "(provider != 'password') OR (password_hash IS NOT NULL)",
            name="ck_auth_method_password_hash",
        ),
        Index(
            "ix_user_auth_methods_user_id",
            "user_id",
        ),
        Index(
            "ix_user_auth_methods_provider_uid",
            "provider",
            "provider_uid",
            postgresql_where=text("provider_uid IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<UserAuthMethod(id={self.id}, user_id={self.user_id}, "
            f"provider={self.provider}, is_primary={self.is_primary})>"
        )


class Session(Base, TimestampMixin):
    __tablename__ = "sessions"

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
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        default=None,
    )
    refresh_token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    ip_address: Mapped[Optional[str]] = mapped_column(Text, default=None)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, default=None)
    device_info: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)

    user: Mapped[User] = relationship(
        "User",
        back_populates="sessions",
    )

    __table_args__ = (
        UniqueConstraint("refresh_token_hash", name="uq_sessions_refresh_token_hash"),
        Index("ix_sessions_user_id", "user_id"),
        Index("ix_sessions_expires_at", "expires_at"),
        Index(
            "ix_sessions_organization_id_not_null",
            "organization_id",
            postgresql_where=text("organization_id IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Session(id={self.id}, user_id={self.user_id}, "
            f"expires_at={self.expires_at}, revoked_at={self.revoked_at})>"
        )


class Invite(Base, TimestampMixin):
    __tablename__ = "invites"

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
    email: Mapped[str] = mapped_column(Text, nullable=False)
    invited_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )
    role_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), default=None
    )
    token: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    accepted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )

    __table_args__ = (
        Index(
            "uq_invites_pending_email",
            "organization_id",
            func.lower(email),
            unique=True,
            postgresql_where=text("accepted_at IS NULL"),
        ),
        Index("ix_invites_organization_id", "organization_id"),
        Index("ix_invites_token", "token"),
    )

    def __repr__(self) -> str:
        return (
            f"<Invite(id={self.id}, organization_id={self.organization_id}, "
            f"email={self.email!r}, expires_at={self.expires_at})>"
        )
