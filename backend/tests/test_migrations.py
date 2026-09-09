"""Alembic migration tests for the Clerk identity schema changes."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings

MIGRATION_SCHEMA = "fitnessos_migration_test"
BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _alembic(*args: str) -> None:
    env = dict(os.environ)
    env["ALEMBIC_SEARCH_PATH"] = MIGRATION_SCHEMA
    env.setdefault("DATABASE_URL", settings.database_url)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"alembic {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}"
        )


@pytest_asyncio.fixture(scope="module")
async def migration_engine():
    """Build an isolated schema that the migration chain is applied to."""
    engine = create_async_engine(settings.database_url, echo=False)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(f'DROP SCHEMA IF EXISTS "{MIGRATION_SCHEMA}" CASCADE')
            )
            await connection.execute(text(f'CREATE SCHEMA "{MIGRATION_SCHEMA}"'))
    except Exception as exc:  # pragma: no cover - environment dependent.
        await engine.dispose()
        pytest.skip(f"Test database is unavailable: {exc}")

    try:
        yield engine
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text(f'DROP SCHEMA IF EXISTS "{MIGRATION_SCHEMA}" CASCADE')
            )
        await engine.dispose()


async def _column_exists(engine, table: str, column: str) -> bool:
    async with engine.begin() as connection:
        result = await connection.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = :schema AND table_name = :table "
                "AND column_name = :column"
            ),
            {"schema": MIGRATION_SCHEMA, "table": table, "column": column},
        )
        return result.first() is not None


async def _index_exists(engine, index: str) -> bool:
    async with engine.begin() as connection:
        result = await connection.execute(
            text(
                "SELECT 1 FROM pg_indexes "
                "WHERE schemaname = :schema AND indexname = :index"
            ),
            {"schema": MIGRATION_SCHEMA, "index": index},
        )
        return result.first() is not None


async def _enum_labels(engine, type_name: str) -> set[str]:
    async with engine.begin() as connection:
        result = await connection.execute(
            text(
                "SELECT e.enumlabel FROM pg_enum e "
                "JOIN pg_type t ON t.oid = e.enumtypid "
                "JOIN pg_namespace n ON n.oid = t.typnamespace "
                "WHERE t.typname = :name AND n.nspname = :schema"
            ),
            {"name": type_name, "schema": MIGRATION_SCHEMA},
        )
        return {row[0] for row in result}


async def test_upgrade_head_applies_cleanly(migration_engine):
    _alembic("upgrade", "head")

    assert await _column_exists(migration_engine, "users", "clerk_user_id")


async def test_clerk_user_id_is_uniquely_indexed(migration_engine):
    _alembic("upgrade", "head")

    assert await _index_exists(migration_engine, "uq_users_clerk_user_id")
    assert await _index_exists(migration_engine, "ix_users_clerk_user_id")


async def test_auth_provider_enum_accepts_clerk(migration_engine):
    """Regression: the enum shipped without 'clerk', breaking every Clerk sign-in."""
    _alembic("upgrade", "head")

    assert "clerk" in await _enum_labels(migration_engine, "authprovider")


async def test_user_uuid_primary_key_is_untouched(migration_engine):
    """Clerk is an external identity mapping, never the domain primary key."""
    _alembic("upgrade", "head")

    async with migration_engine.begin() as connection:
        result = await connection.execute(
            text(
                "SELECT a.attname, format_type(a.atttypid, a.atttypmod) "
                "FROM pg_index i "
                "JOIN pg_attribute a ON a.attrelid = i.indrelid "
                "AND a.attnum = ANY(i.indkey) "
                "WHERE i.indrelid = CAST(:table AS regclass) AND i.indisprimary"
            ),
            {"table": f"{MIGRATION_SCHEMA}.users"},
        )
        primary_key = result.all()

    assert primary_key == [("id", "uuid")]


async def test_clerk_migrations_round_trip(migration_engine):
    """Downgrading past the Clerk changes and re-upgrading must both succeed."""
    _alembic("upgrade", "head")
    _alembic("downgrade", "ad6096532df5")

    assert not await _column_exists(migration_engine, "users", "clerk_user_id")
    assert "clerk" not in await _enum_labels(migration_engine, "authprovider")

    _alembic("upgrade", "head")

    assert await _column_exists(migration_engine, "users", "clerk_user_id")
    assert "clerk" in await _enum_labels(migration_engine, "authprovider")
