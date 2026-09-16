"""Clerk auth: add clerk provider, drop sessions and local passwords.

Clerk becomes the identity provider, so the backend no longer issues its own
refresh sessions or stores password hashes. This adds the ``clerk`` value to the
``authprovider`` enum and drops the ``sessions`` table and the
``user_auth_methods.password_hash`` column (and its check constraint).

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b1f2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "ad6096532df5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Clerk identities are stored as an auth method provider.
    op.execute("ALTER TYPE authprovider ADD VALUE IF NOT EXISTS 'clerk'")

    # No local passwords under Clerk.
    op.drop_constraint(
        "ck_user_auth_methods_ck_auth_method_password_hash",
        "user_auth_methods",
        type_="check",
    )
    op.drop_column("user_auth_methods", "password_hash")

    # Clerk manages sessions; drop our refresh-session store.
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_index(
        "ix_sessions_organization_id_not_null",
        table_name="sessions",
        postgresql_where=sa.text("organization_id IS NOT NULL"),
    )
    op.drop_index("ix_sessions_expires_at", table_name="sessions")
    op.drop_table("sessions")


def downgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("refresh_token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("device_info", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        sa.UniqueConstraint("refresh_token_hash", name="uq_sessions_refresh_token_hash"),
    )
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"], unique=False)
    op.create_index(
        "ix_sessions_organization_id_not_null",
        "sessions",
        ["organization_id"],
        unique=False,
        postgresql_where=sa.text("organization_id IS NOT NULL"),
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)

    op.add_column(
        "user_auth_methods",
        sa.Column("password_hash", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_user_auth_methods_ck_auth_method_password_hash",
        "user_auth_methods",
        "(provider != 'password') OR (password_hash IS NOT NULL)",
    )
    # Note: the 'clerk' enum value is intentionally left in place; PostgreSQL
    # cannot drop an enum value without recreating the type.
