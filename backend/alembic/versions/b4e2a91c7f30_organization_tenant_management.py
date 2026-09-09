"""Organization/tenant management: memberships, business profile, invariants.

Adds the organization_memberships table that becomes the authority on tenant
access, the organization business-profile columns needed by onboarding, and the
partial unique index enforcing at most one main branch per organization.

Existing tenancy rode on users.organization_id alone. That column is retained as
the "currently active organization" pointer, and this migration backfills a
membership row for every user that already has one, so no existing user loses
access when the application starts requiring a membership.

Revision ID: b4e2a91c7f30
Revises: 9c1f4b7a2d10
Create Date: 2026-09-09 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4e2a91c7f30"
down_revision: Union[str, Sequence[str], None] = "9c1f4b7a2d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BUSINESS_TYPE_VALUES = (
    "gym",
    "fitness_studio",
    "yoga",
    "crossfit",
    "personal_training",
    "nutrition",
    "wellness",
    "other",
)
ORG_MEMBER_ROLE_VALUES = (
    "owner",
    "admin",
    "manager",
    "trainer",
    "staff",
    "member",
)
ORG_MEMBER_STATUS_VALUES = ("active", "invited", "suspended", "removed")
# `membershipstatus` already exists for the gym-membership lifecycle, so the
# organization seat enums are namespaced to avoid silently reusing it.
# The Currency enum has no PostgreSQL type yet: the original schema stored
# currency as text, and organizations.currency is its first enum-typed column.
CURRENCY_VALUES = ("INR", "USD", "GBP", "EUR")


def upgrade() -> None:
    """Upgrade schema."""
    business_type = postgresql.ENUM(
        *BUSINESS_TYPE_VALUES, name="businesstype", create_type=False
    )
    org_member_role = postgresql.ENUM(
        *ORG_MEMBER_ROLE_VALUES, name="organizationmemberrole", create_type=False
    )
    org_member_status = postgresql.ENUM(
        *ORG_MEMBER_STATUS_VALUES, name="organizationmemberstatus", create_type=False
    )
    currency = postgresql.ENUM(*CURRENCY_VALUES, name="currency", create_type=False)
    currency.create(op.get_bind(), checkfirst=True)
    business_type.create(op.get_bind(), checkfirst=True)
    org_member_role.create(op.get_bind(), checkfirst=True)
    org_member_status.create(op.get_bind(), checkfirst=True)

    # 'archived' is a new terminal state distinct from 'cancelled', which the
    # subscription lifecycle already uses.
    op.execute("ALTER TYPE organizationstatus ADD VALUE IF NOT EXISTS 'archived'")

    # ---------------------------------------------------------------- organizations
    op.add_column(
        "organizations",
        sa.Column(
            "business_type",
            business_type,
            nullable=False,
            server_default="gym",
        ),
    )
    op.add_column("organizations", sa.Column("phone", sa.Text(), nullable=True))
    op.add_column("organizations", sa.Column("email", sa.Text(), nullable=True))
    op.add_column("organizations", sa.Column("website", sa.Text(), nullable=True))
    op.add_column(
        "organizations",
        sa.Column("timezone", sa.Text(), nullable=False, server_default="UTC"),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "currency",
            currency,
            nullable=False,
            server_default="INR",
        ),
    )
    op.add_column("organizations", sa.Column("country", sa.Text(), nullable=True))
    op.create_index(
        "ix_organizations_business_type", "organizations", ["business_type"]
    )

    # ------------------------------------------------------------------- branches
    # At most one main branch per organization. Enforced by the database so two
    # concurrent writers cannot both succeed.
    op.execute("""
        UPDATE organization_branches b
        SET is_main = FALSE
        WHERE b.is_main IS TRUE
          AND b.deleted_at IS NULL
          AND b.id <> (
              SELECT o.id FROM organization_branches o
              WHERE o.organization_id = b.organization_id
                AND o.is_main IS TRUE
                AND o.deleted_at IS NULL
              ORDER BY o.created_at, o.id
              LIMIT 1
          )
        """)
    op.create_index(
        "uq_org_branches_one_main",
        "organization_branches",
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text("is_main IS TRUE AND deleted_at IS NULL"),
    )

    # ---------------------------------------------------------------- memberships
    op.create_table(
        "organization_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", org_member_role, nullable=False),
        sa.Column("status", org_member_status, nullable=False),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_organization_memberships"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_organization_memberships_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_organization_memberships_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by"],
            ["users.id"],
            name="fk_organization_memberships_invited_by_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "uq_org_memberships_user_org",
        "organization_memberships",
        ["organization_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_org_memberships_organization_id",
        "organization_memberships",
        ["organization_id"],
    )
    op.create_index(
        "ix_org_memberships_user_id", "organization_memberships", ["user_id"]
    )
    op.create_index(
        "ix_org_memberships_org_status",
        "organization_memberships",
        ["organization_id", "status"],
    )
    op.create_index(
        "ix_org_memberships_org_created_at",
        "organization_memberships",
        ["organization_id", "created_at"],
    )

    # Backfill: every user already attached to an organization keeps access.
    # The organization's creator becomes its owner; everyone else becomes staff.
    op.execute("""
        INSERT INTO organization_memberships
            (id, organization_id, user_id, role, status, created_by, updated_by,
             version, created_at, updated_at, joined_at)
        SELECT
            gen_random_uuid(),
            u.organization_id,
            u.id,
            CASE WHEN o.created_by = u.id THEN 'owner' ELSE 'staff' END::organizationmemberrole,
            'active'::organizationmemberstatus,
            u.id,
            u.id,
            1,
            now(),
            now(),
            now()
        FROM users u
        JOIN organizations o ON o.id = u.organization_id
        WHERE u.organization_id IS NOT NULL
          AND u.deleted_at IS NULL
          AND o.deleted_at IS NULL
        """)

    # An organization whose creator is gone would otherwise have no owner at all.
    op.execute("""
        UPDATE organization_memberships m
        SET role = 'owner'::organizationmemberrole
        WHERE m.id = (
            SELECT m2.id FROM organization_memberships m2
            WHERE m2.organization_id = m.organization_id
              AND m2.deleted_at IS NULL
            ORDER BY m2.created_at, m2.id
            LIMIT 1
        )
        AND NOT EXISTS (
            SELECT 1 FROM organization_memberships owner_check
            WHERE owner_check.organization_id = m.organization_id
              AND owner_check.role = 'owner'::organizationmemberrole
              AND owner_check.deleted_at IS NULL
        )
        """)

    op.alter_column("organizations", "business_type", server_default=None)
    op.alter_column("organizations", "timezone", server_default=None)
    op.alter_column("organizations", "currency", server_default=None)


def downgrade() -> None:
    """
    Downgrade schema.

    Memberships are dropped wholesale: users.organization_id still holds the
    single-tenant assignment this migration was layered on top of, so no access
    is lost by reverting. The 'archived' organization status is left in place —
    PostgreSQL cannot drop one enum label, and rebuilding the type would require
    rewriting every organization row for no benefit.
    """
    op.drop_index(
        "ix_org_memberships_org_created_at", table_name="organization_memberships"
    )
    op.drop_index(
        "ix_org_memberships_org_status", table_name="organization_memberships"
    )
    op.drop_index("ix_org_memberships_user_id", table_name="organization_memberships")
    op.drop_index(
        "ix_org_memberships_organization_id", table_name="organization_memberships"
    )
    op.drop_index("uq_org_memberships_user_org", table_name="organization_memberships")
    op.drop_table("organization_memberships")

    op.drop_index("uq_org_branches_one_main", table_name="organization_branches")

    op.drop_index("ix_organizations_business_type", table_name="organizations")
    op.drop_column("organizations", "country")
    op.drop_column("organizations", "currency")
    op.drop_column("organizations", "timezone")
    op.drop_column("organizations", "website")
    op.drop_column("organizations", "email")
    op.drop_column("organizations", "phone")
    op.drop_column("organizations", "business_type")

    op.execute("DROP TYPE IF EXISTS organizationmemberstatus")
    op.execute("DROP TYPE IF EXISTS organizationmemberrole")
    op.execute("DROP TYPE IF EXISTS businesstype")
    op.execute("DROP TYPE IF EXISTS currency")
