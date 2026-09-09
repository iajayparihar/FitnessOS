from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.db.session import get_db
from app.integrations.clerk.client import reset_jwks_cache
from app.main import create_app

TEST_SCHEMA = "fitnessos_test"
TEST_ISSUER = "https://tests.clerk.accounts.dev"
TEST_AUTHORIZED_PARTY = "http://localhost:3000"


# --------------------------------------------------------------------------- #
# OpenAPI-only client, retained for the route-registration tests.
# --------------------------------------------------------------------------- #


class OpenAPIResponse:
    """Minimal response helper for OpenAPI route registration tests."""

    def json(self):
        return create_app().openapi()


class OpenAPIClient:
    """Minimal client helper for tests that only read OpenAPI."""

    def get(self, path: str):
        if path != "/openapi.json":
            raise ValueError(f"Unsupported test path: {path}")
        return OpenAPIResponse()


@pytest.fixture
def client():
    return OpenAPIClient()


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Rate-limit budgets are process-wide, so clear them between tests."""
    from app.modules.auth.router import onboarding_rate_limit

    onboarding_rate_limit.limiter.reset()
    yield
    onboarding_rate_limit.limiter.reset()


# --------------------------------------------------------------------------- #
# Clerk token minting.
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="session")
def rsa_key_pair() -> tuple[str, str]:
    """Return a (private PEM, public PEM) pair standing in for Clerk's signing key."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


@pytest.fixture
def clerk_settings(monkeypatch, rsa_key_pair):
    """Configure the Clerk integration to trust the test signing key."""
    _, public_pem = rsa_key_pair
    monkeypatch.setattr(settings, "clerk_jwt_key", public_pem)
    monkeypatch.setattr(settings, "clerk_jwks_url", None)
    monkeypatch.setattr(settings, "clerk_issuer", TEST_ISSUER)
    monkeypatch.setattr(settings, "clerk_authorized_parties", [TEST_AUTHORIZED_PARTY])
    monkeypatch.setattr(settings, "clerk_link_existing_users_by_email", False)
    monkeypatch.setattr(settings, "legacy_password_auth_enabled", False)
    reset_jwks_cache()
    return settings


@pytest.fixture
def make_clerk_token(rsa_key_pair):
    """
    Return a factory that mints Clerk-shaped session tokens.

    The default claim set matches a real Clerk session token: `azp` identifies the
    frontend origin and there is deliberately no `aud` claim.
    """
    private_pem, _ = rsa_key_pair

    def _make(
        *,
        subject: str = "user_test_default",
        issuer: str = TEST_ISSUER,
        authorized_party: str | None = TEST_AUTHORIZED_PARTY,
        expires_in: timedelta = timedelta(minutes=5),
        issued_at: datetime | None = None,
        key: str | None = None,
        algorithm: str = "RS256",
        extra_claims: dict | None = None,
        drop_claims: tuple[str, ...] = (),
    ) -> str:
        now = issued_at or datetime.now(UTC)
        claims: dict = {
            "sub": subject,
            "iss": issuer,
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + expires_in).timestamp()),
            "sid": f"sess_{uuid.uuid4().hex[:12]}",
            "v": 2,
        }
        if authorized_party is not None:
            claims["azp"] = authorized_party
        claims.update(extra_claims or {})
        for claim in drop_claims:
            claims.pop(claim, None)
        return jwt.encode(claims, key or private_pem, algorithm=algorithm)

    return _make


# --------------------------------------------------------------------------- #
# Database fixtures.
# --------------------------------------------------------------------------- #


def _test_database_url() -> str | None:
    """
    Return the database to run schema-backed tests against.

    Falls back to the configured application database, but every table lives in a
    dedicated schema that is dropped afterwards, so the application's own schema
    is never touched.
    """
    return (
        os.environ.get("TEST_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or getattr(settings, "database_url", None)
    )


def _run_alembic(command: str) -> None:
    """Run the migration chain inside the dedicated test schema."""
    env = dict(os.environ)
    env["ALEMBIC_SEARCH_PATH"] = TEST_SCHEMA
    env.setdefault("DATABASE_URL", settings.database_url)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", command],
        cwd=Path(__file__).resolve().parent.parent,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"alembic upgrade {command} failed:\n{result.stdout}\n{result.stderr}"
        )


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """
    Provide an engine bound to a dedicated schema built by the Alembic chain.

    Tests run against real PostgreSQL because the schema relies on JSONB, array
    columns, enum types and partial unique indexes. Building the schema with
    Alembic rather than ``create_all`` means every test run also exercises the
    migrations. The DB-backed suite is skipped when no database is reachable,
    rather than silently passing.
    """
    url = _test_database_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL/DATABASE_URL is not set.")

    admin_engine = create_async_engine(url, echo=False)
    try:
        async with admin_engine.begin() as connection:
            await connection.execute(
                text(f'DROP SCHEMA IF EXISTS "{TEST_SCHEMA}" CASCADE')
            )
            await connection.execute(text(f'CREATE SCHEMA "{TEST_SCHEMA}"'))
    except Exception as exc:  # pragma: no cover - environment dependent.
        await admin_engine.dispose()
        pytest.skip(f"Test database is unavailable: {exc}")

    try:
        _run_alembic("head")
    except RuntimeError as exc:  # pragma: no cover - surfaced as a hard failure.
        await admin_engine.dispose()
        pytest.fail(str(exc))

    schema_engine = create_async_engine(
        url,
        echo=False,
        connect_args={"server_settings": {"search_path": TEST_SCHEMA}},
    )
    try:
        yield schema_engine
    finally:
        await schema_engine.dispose()
        async with admin_engine.begin() as connection:
            await connection.execute(
                text(f'DROP SCHEMA IF EXISTS "{TEST_SCHEMA}" CASCADE')
            )
        await admin_engine.dispose()


async def _truncate_all(engine) -> None:
    """Empty every table in the test schema between tests."""
    async with engine.begin() as connection:
        result = await connection.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = :schema"),
            {"schema": TEST_SCHEMA},
        )
        tables = [row[0] for row in result.fetchall() if row[0] != "alembic_version"]
        if not tables:
            return
        joined = ", ".join(f'"{TEST_SCHEMA}"."{name}"' for name in tables)
        await connection.execute(
            text(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE")
        )


@pytest_asyncio.fixture(autouse=True)
async def reset_database(request):
    """
    Empty the test schema after every test.

    Truncation is autouse, so it is torn down last — after every session-holding
    fixture has closed. Doing it inside those fixtures instead deadlocks: TRUNCATE
    takes an exclusive lock, and a sibling fixture whose session is still
    idle-in-transaction holds a conflicting one.
    """
    yield
    if "db_engine" not in request.fixturenames:
        return
    await _truncate_all(request.getfixturevalue("db_engine"))


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Yield a session against an empty schema."""
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as session:
        try:
            yield session
        finally:
            await session.rollback()


@pytest_asyncio.fixture
async def api_client(db_engine, clerk_settings):
    """Yield an HTTP client wired to the app with the test database session."""
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http

    app.dependency_overrides.clear()
