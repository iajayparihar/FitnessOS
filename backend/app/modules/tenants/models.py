from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import (
    Enum as sa_Enum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    BusinessType,
    Currency,
    OrganizationMemberRole,
    OrganizationMemberStatus,
    OrganizationStatus,
)
from app.core.mixins import AuditMixin, TimestampMixin
from app.db.base import Base
from app.modules.subscriptions.models import TenantSubscription

if TYPE_CHECKING:
    from app.modules.auth.models import User

# RLS POLICY — organizations: no org filter (root table)
# RLS POLICY — organization_branches, organization_settings, organization_domains,
#   organization_memberships:
#   USING (organization_id = current_setting('app.current_organization_id')::uuid)


class Organization(Base, AuditMixin):
    """
    Root tenant entity. One Organization = one customer/tenant.
    No organization_id foreign key on this table (it IS the organization).
    """

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[OrganizationStatus] = mapped_column(
        sa_Enum(
            OrganizationStatus,
            name="organizationstatus",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=OrganizationStatus.ACTIVE,
    )
    business_type: Mapped[BusinessType] = mapped_column(
        sa_Enum(
            BusinessType,
            name="businesstype",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=BusinessType.GYM,
    )
    # Free-text label retained from the original schema; business_type is the
    # structured value that queries and reporting should use.
    industry: Mapped[Optional[str]] = mapped_column(Text, default=None)
    phone: Mapped[Optional[str]] = mapped_column(Text, default=None)
    email: Mapped[Optional[str]] = mapped_column(Text, default=None)
    website: Mapped[Optional[str]] = mapped_column(Text, default=None)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, default="UTC")
    currency: Mapped[Currency] = mapped_column(
        sa_Enum(
            Currency,
            name="currency",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=Currency.INR,
    )
    country: Mapped[Optional[str]] = mapped_column(Text, default=None)
    settings: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    branding: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    billing_contact: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    data_region: Mapped[Optional[str]] = mapped_column(Text, default=None)

    branches: Mapped[list[OrganizationBranch]] = relationship(
        "OrganizationBranch",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    settings_list: Mapped[list[OrganizationSetting]] = relationship(
        "OrganizationSetting",
        back_populates="organization",
        cascade="all, delete-orphan",
        foreign_keys="OrganizationSetting.organization_id",
    )
    memberships: Mapped[list[OrganizationMembership]] = relationship(
        "OrganizationMembership",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    domains: Mapped[list[OrganizationDomain]] = relationship(
        "OrganizationDomain",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    subscriptions: Mapped[list[TenantSubscription]] = relationship(
        "TenantSubscription",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "uq_organizations_slug",
            func.lower(slug),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_organizations_status", "status"),
        Index("ix_organizations_name_lower", func.lower(name)),
        Index("ix_organizations_business_type", "business_type"),
    )

    @classmethod
    def not_deleted(cls):
        """Return filter for non-deleted organizations."""
        return cls.deleted_at.is_(None)

    def __repr__(self) -> str:
        return (
            f"<Organization(id={self.id}, name={self.name!r}, "
            f"slug={self.slug!r}, status={self.status})>"
        )


class OrganizationBranch(Base, AuditMixin):
    """
    Physical or logical branch/location of an Organization.
    Can represent a gym location, franchise, or office.
    """

    __tablename__ = "organization_branches"

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
    code: Mapped[Optional[str]] = mapped_column(Text, default=None)
    address: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    phone: Mapped[Optional[str]] = mapped_column(Text, default=None)
    email: Mapped[Optional[str]] = mapped_column(Text, default=None)
    is_main: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    organization: Mapped[Organization] = relationship(
        "Organization",
        back_populates="branches",
    )
    settings: Mapped[list[OrganizationSetting]] = relationship(
        "OrganizationSetting",
        back_populates="branch",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "uq_org_branches_org_name",
            "organization_id",
            func.lower(name),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_org_branches_organization_id", "organization_id"),
        Index(
            "ix_org_branches_organization_id_is_active",
            "organization_id",
            "is_active",
        ),
        # At most one main branch per organization, enforced by the database so
        # concurrent writers cannot both win the race.
        Index(
            "uq_org_branches_one_main",
            "organization_id",
            unique=True,
            postgresql_where=text("is_main IS TRUE AND deleted_at IS NULL"),
        ),
    )

    @classmethod
    def not_deleted(cls):
        """Return filter for non-deleted branches."""
        return cls.deleted_at.is_(None)

    def __repr__(self) -> str:
        return (
            f"<OrganizationBranch(id={self.id}, organization_id={self.organization_id}, "
            f"name={self.name!r}, is_main={self.is_main})>"
        )


class OrganizationMembership(Base, AuditMixin):
    """
    Link between a local User and an Organization.

    This table is the authority on tenant access: a user may reach an
    organization's data only through an active membership here. ``users.
    organization_id`` is a pointer to the membership the user is currently
    operating in, and is always validated against this table before use.
    """

    __tablename__ = "organization_memberships"

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
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[OrganizationMemberRole] = mapped_column(
        sa_Enum(
            OrganizationMemberRole,
            name="organizationmemberrole",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=OrganizationMemberRole.MEMBER,
    )
    status: Mapped[OrganizationMemberStatus] = mapped_column(
        sa_Enum(
            OrganizationMemberStatus,
            name="organizationmemberstatus",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=OrganizationMemberStatus.ACTIVE,
    )
    invited_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )
    joined_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
    )

    organization: Mapped[Organization] = relationship(
        "Organization",
        back_populates="memberships",
    )
    user: Mapped[User] = relationship(
        "User",
        primaryjoin="OrganizationMembership.user_id == foreign(User.id)",
        viewonly=True,
    )

    __table_args__ = (
        # One live membership per (user, organization). Partial so a removed
        # member can be re-invited later without tripping the constraint.
        Index(
            "uq_org_memberships_user_org",
            "organization_id",
            "user_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_org_memberships_organization_id", "organization_id"),
        Index("ix_org_memberships_user_id", "user_id"),
        Index(
            "ix_org_memberships_org_status",
            "organization_id",
            "status",
        ),
        Index(
            "ix_org_memberships_org_created_at",
            "organization_id",
            "created_at",
        ),
    )

    @classmethod
    def not_deleted(cls):
        """Return filter for non-deleted memberships."""
        return cls.deleted_at.is_(None)

    def __repr__(self) -> str:
        return (
            f"<OrganizationMembership(id={self.id}, "
            f"organization_id={self.organization_id}, user_id={self.user_id}, "
            f"role={self.role}, status={self.status})>"
        )


class OrganizationSetting(Base, TimestampMixin):
    """
    Organization-wide or branch-specific configuration settings.
    Settings can be scoped to entire org (branch_id=NULL) or specific branch.
    """

    __tablename__ = "organization_settings"

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
    branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_branches.id", ondelete="SET NULL"),
        default=None,
    )
    key: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    effective_from: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )

    organization: Mapped[Organization] = relationship(
        "Organization",
        back_populates="settings_list",
    )
    branch: Mapped[Optional[OrganizationBranch]] = relationship(
        "OrganizationBranch",
        back_populates="settings",
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "branch_id",
            "key",
            name="uq_org_settings_org_branch_key",
        ),
        Index("ix_org_settings_organization_id_key", "organization_id", "key"),
    )

    def __repr__(self) -> str:
        return (
            f"<OrganizationSetting(id={self.id}, organization_id={self.organization_id}, "
            f"branch_id={self.branch_id}, key={self.key!r})>"
        )


class OrganizationDomain(Base, TimestampMixin):
    """
    Custom domain for white-label/multi-tenant support.
    Stores verification tokens and SSL provisioning status.
    """

    __tablename__ = "organization_domains"

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
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    verification_token: Mapped[Optional[str]] = mapped_column(Text, default=None)
    verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    ssl_provisioned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    organization: Mapped[Organization] = relationship(
        "Organization",
        back_populates="domains",
    )

    __table_args__ = (
        Index(
            "uq_org_domains_domain",
            func.lower(domain),
            unique=True,
        ),
        Index("ix_org_domains_organization_id", "organization_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<OrganizationDomain(id={self.id}, organization_id={self.organization_id}, "
            f"domain={self.domain!r}, is_verified={self.is_verified})>"
        )
