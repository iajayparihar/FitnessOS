from logging.config import fileConfig
import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.db.base import Base as BaseModel
from app.db.session import get_database_url  # noqa: F401

# Import all models so Alembic autogeneration can detect table metadata.
import app.modules.ai.models  # noqa: F401
import app.modules.analytics.models  # noqa: F401
import app.modules.attendance.models  # noqa: F401
import app.modules.auth.models  # noqa: F401
import app.modules.billing.models  # noqa: F401
import app.modules.crm.models  # noqa: F401
import app.modules.expenses.models  # noqa: F401
import app.modules.integrations.models  # noqa: F401
import app.modules.inventory.models  # noqa: F401
import app.modules.membership.models  # noqa: F401
import app.modules.notifications.models  # noqa: F401
import app.modules.nutrition.models  # noqa: F401
import app.modules.rbac.models  # noqa: F401
import app.modules.subscriptions.models  # noqa: F401
import app.modules.tenants.models  # noqa: F401
import app.modules.trainer.models


# Alembic Config object
config = context.config

# Prefer the application database URL if alembic.ini doesn't set one
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", settings.database_url)

# Configure logging from alembic.ini
fileConfig(config.config_file_name)

# Target metadata for 'autogenerate' support
target_metadata = getattr(BaseModel, "metadata", None)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode using an async engine."""
    connectable = create_async_engine(
        get_database_url(),
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
