from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from app.config import get_settings


def get_database_url() -> str:
    """Construct async PostgreSQL database URL."""
    settings = get_settings()
    user = settings.db_user
    password = settings.db_password
    host = settings.db_host
    port = settings.db_port
    database = settings.db_name
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"


def create_engine() -> AsyncEngine:
    """Create async SQLAlchemy engine."""
    database_url = get_database_url()
    return create_async_engine(
        database_url,
        echo=False,
        pool_size=20,
        max_overflow=40,
        pool_pre_ping=True,
        pool_recycle=3600,
        future=True,
    )


engine: AsyncEngine = create_engine()

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    future=True,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency to get async database session.
    Usage: async def my_route(db: AsyncSession = Depends(get_db)):
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
