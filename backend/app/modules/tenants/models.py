from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    func,
    Enum as sa_Enum,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.core.mixins import TimestampMixin, AuditMixin
from app.core.enums import OrganizationStatus
from app.modules.subscriptions.models import TenantSubscription

# RLS POLICY — organizations: no org filter (root table)
# RLS POLICY — organization_branches, organization_settings, organization_domains:
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
    industry: Mapped[Optional[str]] = mapped_column(Text, default=None)
    settings: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    branding: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    billing_contact: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    data_region: Mapped[Optional[str]] = mapped_column(Text, default=None)

    branches: Mapped[list["OrganizationBranch"]] = relationship(
        "OrganizationBranch",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    settings_list: Mapped[list["OrganizationSetting"]] = relationship(
        "OrganizationSetting",
        back_populates="organization",
        cascade="all, delete-orphan",
        foreign_keys="OrganizationSetting.organization_id",
    )
    domains: Mapped[list["OrganizationDomain"]] = relationship(
        "OrganizationDomain",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    subscriptions: Mapped[list["TenantSubscription"]] = relationship(
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

    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="branches",
    )
    settings: Mapped[list["OrganizationSetting"]] = relationship(
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

    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="settings_list",
    )
    branch: Mapped[Optional["OrganizationBranch"]] = relationship(
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

    organization: Mapped["Organization"] = relationship(
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
