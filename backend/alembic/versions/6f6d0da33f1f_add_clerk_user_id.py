"""Add clerk_user_id to users

Revision ID: 6f6d0da33f1f
Revises: ad6096532df5
Create Date: 2026-09-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "6f6d0da33f1f"
down_revision: Union[str, Sequence[str], None] = "ad6096532df5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("clerk_user_id", sa.Text(), nullable=True))
    op.create_index(
        "ix_users_clerk_user_id",
        "users",
        ["clerk_user_id"],
        unique=False,
    )
    op.create_index(
        "uq_users_clerk_user_id",
        "users",
        ["clerk_user_id"],
        unique=True,
        postgresql_where=sa.text("clerk_user_id IS NOT NULL AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_users_clerk_user_id", table_name="users")
    op.drop_index("ix_users_clerk_user_id", table_name="users")
    op.drop_column("users", "clerk_user_id")
