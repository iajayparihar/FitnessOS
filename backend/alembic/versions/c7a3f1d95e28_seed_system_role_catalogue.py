"""Seed the system role catalogue and migrate per-organization owner roles.

Adds the platform-wide permission catalogue and six system roles (owner, admin,
manager, trainer, staff, member) with ``organization_id IS NULL``. Assignments in
``user_roles`` carry the tenant, so one role row serves every organization.

Organizations created before this migration each had their own "Owner" role. Those
assignments are repointed at the shared system owner role and the per-organization
copies are soft-deleted, so no organization ends up with two Owner roles.

The catalogue is written out literally rather than imported from application code,
because a migration must keep reproducing the same schema as the code evolves.

Revision ID: c7a3f1d95e28
Revises: b4e2a91c7f30
Create Date: 2026-09-09 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7a3f1d95e28"
down_revision: Union[str, Sequence[str], None] = "b4e2a91c7f30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMISSIONS: tuple[tuple[str, str, str], ...] = (
    ("tenants:read", "Read current organization information.", "tenants"),
    ("tenants:manage", "Manage organization settings and lifecycle.", "tenants"),
    ("branches:read", "Read organization branches.", "tenants"),
    ("branches:manage", "Create, update and remove branches.", "tenants"),
    ("users:read", "Read organization users and memberships.", "users"),
    ("users:manage", "Add, update and remove organization members.", "users"),
    ("rbac:read", "Read roles and permissions.", "rbac"),
    ("rbac:manage", "Create roles and assign permissions.", "rbac"),
    ("crm:read", "Read leads and CRM activity.", "crm"),
    ("crm:manage", "Manage CRM data.", "crm"),
    ("membership:read", "Read members, plans and memberships.", "membership"),
    ("membership:manage", "Manage members and memberships.", "membership"),
    ("attendance:read", "Read attendance records.", "attendance"),
    ("attendance:manage", "Manage attendance.", "attendance"),
    ("billing:read", "Read invoices, payments and refunds.", "billing"),
    ("billing:manage", "Manage invoices and payments.", "billing"),
    ("trainer:read", "Read trainer profiles and schedules.", "trainer"),
    ("trainer:manage", "Manage trainers, schedules and sessions.", "trainer"),
    ("nutrition:read", "Read nutrition plans.", "nutrition"),
    ("nutrition:manage", "Manage nutrition plans and assignments.", "nutrition"),
    ("inventory:read", "Read products, stock and suppliers.", "inventory"),
    ("inventory:manage", "Manage products, stock and purchase orders.", "inventory"),
    ("expenses:read", "Read expenses and payroll.", "expenses"),
    ("expenses:manage", "Manage expenses and payroll.", "expenses"),
    ("notifications:read", "Read notification history.", "notifications"),
    ("notifications:manage", "Send and configure notifications.", "notifications"),
    (
        "subscriptions:read",
        "Read the organization's platform subscription.",
        "subscriptions",
    ),
    (
        "subscriptions:manage",
        "Manage the organization's platform subscription.",
        "subscriptions",
    ),
    ("analytics:read", "Read dashboards and reports.", "analytics"),
)

SYSTEM_ROLES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "owner",
        "Owner",
        "Full control of the organization, including roles and billing.",
        (
            "tenants:read",
            "tenants:manage",
            "branches:read",
            "branches:manage",
            "users:read",
            "users:manage",
            "rbac:read",
            "rbac:manage",
            "crm:read",
            "crm:manage",
            "membership:read",
            "membership:manage",
            "attendance:read",
            "attendance:manage",
            "billing:read",
            "billing:manage",
            "trainer:read",
            "trainer:manage",
            "nutrition:read",
            "nutrition:manage",
            "inventory:read",
            "inventory:manage",
            "expenses:read",
            "expenses:manage",
            "notifications:read",
            "notifications:manage",
            "subscriptions:read",
            "subscriptions:manage",
            "analytics:read",
        ),
    ),
    (
        "admin",
        "Admin",
        "Runs the business day to day. Everything except role management, organization lifecycle and platform subscription.",
        (
            "tenants:read",
            "branches:read",
            "branches:manage",
            "users:read",
            "users:manage",
            "rbac:read",
            "crm:read",
            "crm:manage",
            "membership:read",
            "membership:manage",
            "attendance:read",
            "attendance:manage",
            "billing:read",
            "billing:manage",
            "trainer:read",
            "trainer:manage",
            "nutrition:read",
            "nutrition:manage",
            "inventory:read",
            "inventory:manage",
            "expenses:read",
            "expenses:manage",
            "notifications:read",
            "notifications:manage",
            "subscriptions:read",
            "analytics:read",
        ),
    ),
    (
        "manager",
        "Manager",
        "Runs floor operations. Full member, trainer and inventory control; financial data is read-only.",
        (
            "tenants:read",
            "branches:read",
            "users:read",
            "crm:read",
            "crm:manage",
            "membership:read",
            "membership:manage",
            "attendance:read",
            "attendance:manage",
            "billing:read",
            "trainer:read",
            "trainer:manage",
            "nutrition:read",
            "nutrition:manage",
            "inventory:read",
            "inventory:manage",
            "expenses:read",
            "notifications:read",
            "notifications:manage",
            "analytics:read",
        ),
    ),
    (
        "trainer",
        "Trainer",
        "Coaches members: marks attendance and manages training and nutrition plans. No access to money or staff administration.",
        (
            "tenants:read",
            "branches:read",
            "crm:read",
            "membership:read",
            "attendance:read",
            "attendance:manage",
            "trainer:read",
            "nutrition:read",
            "nutrition:manage",
        ),
    ),
    (
        "staff",
        "Staff",
        "Front desk: registers members, captures leads and records check-ins. Billing is read-only.",
        (
            "tenants:read",
            "branches:read",
            "crm:read",
            "crm:manage",
            "membership:read",
            "membership:manage",
            "attendance:read",
            "attendance:manage",
            "billing:read",
            "trainer:read",
            "inventory:read",
            "notifications:read",
        ),
    ),
    (
        "member",
        "Member",
        "A gym-goer. Holds no organization-wide read access; self-service requires object-level scoping that does not exist yet.",
        ("tenants:read",),
    ),
)


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()

    for code, description, category in PERMISSIONS:
        connection.execute(
            sa.text("""
                INSERT INTO permissions (id, code, description, category, is_active,
                                         created_at, updated_at)
                VALUES (gen_random_uuid(), :code, :description, :category, TRUE,
                        now(), now())
                ON CONFLICT (code) DO UPDATE
                    SET description = EXCLUDED.description,
                        category = EXCLUDED.category,
                        is_active = TRUE
                """),
            {"code": code, "description": description, "category": category},
        )

    for slug, name, description, permission_codes in SYSTEM_ROLES:
        connection.execute(
            sa.text("""
                INSERT INTO roles (id, organization_id, name, slug, description,
                                   is_system, is_active, created_at, updated_at)
                SELECT gen_random_uuid(), NULL, :name, :slug, :description,
                       TRUE, TRUE, now(), now()
                WHERE NOT EXISTS (
                    SELECT 1 FROM roles
                    WHERE organization_id IS NULL AND lower(slug) = lower(:slug)
                )
                """),
            {"slug": slug, "name": name, "description": description},
        )
        connection.execute(
            sa.text("""
                INSERT INTO role_permissions (role_id, permission_id, granted, created_at)
                SELECT r.id, p.id, TRUE, now()
                FROM roles r
                JOIN permissions p ON p.code = ANY(:codes)
                WHERE r.organization_id IS NULL
                  AND lower(r.slug) = lower(:slug)
                ON CONFLICT (role_id, permission_id) DO UPDATE SET granted = TRUE
                """),
            {"slug": slug, "codes": list(permission_codes)},
        )
        # Revoke anything not in the definition, so the catalogue stays exact.
        connection.execute(
            sa.text("""
                DELETE FROM role_permissions rp
                USING roles r, permissions p
                WHERE rp.role_id = r.id
                  AND rp.permission_id = p.id
                  AND r.organization_id IS NULL
                  AND lower(r.slug) = lower(:slug)
                  AND NOT (p.code = ANY(:codes))
                """),
            {"slug": slug, "codes": list(permission_codes)},
        )

    # Repoint existing per-organization Owner assignments at the system role,
    # skipping any user that would collide with an assignment they already hold.
    connection.execute(sa.text("""
            UPDATE user_roles ur
            SET role_id = sys.id
            FROM roles legacy, roles sys
            WHERE ur.role_id = legacy.id
              AND legacy.organization_id IS NOT NULL
              AND lower(legacy.slug) = 'owner'
              AND sys.organization_id IS NULL
              AND lower(sys.slug) = 'owner'
              AND NOT EXISTS (
                  SELECT 1 FROM user_roles existing
                  WHERE existing.user_id = ur.user_id
                    AND existing.role_id = sys.id
                    AND existing.organization_id = ur.organization_id
                    AND existing.branch_id IS NOT DISTINCT FROM ur.branch_id
              )
            """))
    # Drop assignments that could not be repointed because the target already exists.
    connection.execute(sa.text("""
            DELETE FROM user_roles ur
            USING roles legacy
            WHERE ur.role_id = legacy.id
              AND legacy.organization_id IS NOT NULL
              AND lower(legacy.slug) = 'owner'
            """))
    connection.execute(sa.text("""
            UPDATE roles
            SET deleted_at = now(), is_active = FALSE
            WHERE organization_id IS NOT NULL
              AND lower(slug) = 'owner'
              AND deleted_at IS NULL
            """))


def downgrade() -> None:
    """
    Downgrade schema.

    Recreates a per-organization Owner role for every organization that has an
    owner assignment, repoints those assignments at it, then removes the system
    roles. Permissions are left in place: they are additive reference data, and
    other roles may already grant them.
    """
    connection = op.get_bind()

    connection.execute(sa.text("""
            INSERT INTO roles (id, organization_id, name, slug, description,
                               is_system, is_active, created_at, updated_at)
            SELECT gen_random_uuid(), ur.organization_id, 'Owner', 'owner',
                   'Full organization owner access.', FALSE, TRUE, now(), now()
            FROM user_roles ur
            JOIN roles sys ON sys.id = ur.role_id
            WHERE sys.organization_id IS NULL AND lower(sys.slug) = 'owner'
              AND NOT EXISTS (
                  SELECT 1 FROM roles r
                  WHERE r.organization_id = ur.organization_id
                    AND lower(r.slug) = 'owner'
                    AND r.deleted_at IS NULL
              )
            GROUP BY ur.organization_id
            """))
    connection.execute(sa.text("""
            UPDATE user_roles ur
            SET role_id = legacy.id
            FROM roles sys, roles legacy
            WHERE ur.role_id = sys.id
              AND sys.organization_id IS NULL
              AND lower(sys.slug) = 'owner'
              AND legacy.organization_id = ur.organization_id
              AND lower(legacy.slug) = 'owner'
              AND legacy.deleted_at IS NULL
            """))
    connection.execute(sa.text("""
            DELETE FROM user_roles ur
            USING roles sys
            WHERE ur.role_id = sys.id
              AND sys.organization_id IS NULL
              AND sys.is_system IS TRUE
            """))
    connection.execute(sa.text("""
            DELETE FROM role_permissions rp
            USING roles r
            WHERE rp.role_id = r.id
              AND r.organization_id IS NULL
              AND r.is_system IS TRUE
            """))
    connection.execute(
        sa.text("DELETE FROM roles WHERE organization_id IS NULL AND is_system IS TRUE")
    )
