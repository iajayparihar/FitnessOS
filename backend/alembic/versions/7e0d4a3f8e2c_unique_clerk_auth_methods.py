"""Add unique provider_uid index for auth methods.

Revision ID: 7e0d4a3f8e2c
Revises: 6f6d0da33f1f
Create Date: 2026-09-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "7e0d4a3f8e2c"
down_revision: Union[str, Sequence[str], None] = "6f6d0da33f1f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "uq_user_auth_methods_provider_uid",
        "user_auth_methods",
        ["provider", "provider_uid"],
        unique=True,
        postgresql_where=sa.text("provider_uid IS NOT NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_user_auth_methods_provider_uid", table_name="user_auth_methods")
