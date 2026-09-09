"""Add the clerk value to the authprovider enum.

The Clerk integration writes UserAuthMethod rows with provider='clerk', but the
initial schema created the authprovider enum without that label, so every Clerk
sign-in failed with InvalidTextRepresentationError. This migration adds the
missing value.

Revision ID: 9c1f4b7a2d10
Revises: 7e0d4a3f8e2c
Create Date: 2026-09-09 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c1f4b7a2d10"
down_revision: Union[str, Sequence[str], None] = "7e0d4a3f8e2c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE authprovider ADD VALUE IF NOT EXISTS 'clerk'")


def downgrade() -> None:
    """
    Downgrade schema.

    PostgreSQL cannot drop a single enum label, so the type is rebuilt without
    'clerk'. Rows still using it are removed first, because there is no valid
    value to migrate them to once Clerk identities are no longer representable.
    """
    op.execute("DELETE FROM user_auth_methods WHERE provider = 'clerk'")
    # The check constraint is bound to the enum type by OID, so it must be
    # dropped before the type is swapped and recreated afterwards.
    op.execute(
        "ALTER TABLE user_auth_methods "
        "DROP CONSTRAINT IF EXISTS ck_user_auth_methods_ck_auth_method_password_hash"
    )
    op.execute("ALTER TYPE authprovider RENAME TO authprovider_old")
    op.execute(
        "CREATE TYPE authprovider AS ENUM "
        "('password', 'google', 'apple', 'totp', 'saml', 'magiclink')"
    )
    op.execute(
        "ALTER TABLE user_auth_methods "
        "ALTER COLUMN provider TYPE authprovider "
        "USING provider::text::authprovider"
    )
    op.execute("DROP TYPE authprovider_old")
    op.execute(
        "ALTER TABLE user_auth_methods ADD CONSTRAINT "
        "ck_user_auth_methods_ck_auth_method_password_hash "
        "CHECK ((provider != 'password') OR (password_hash IS NOT NULL))"
    )
