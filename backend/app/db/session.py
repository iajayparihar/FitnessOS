from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.echo,
)

async_session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


async def get_db():
    async with async_session_maker() as session:
        yield session


def get_database_url() -> str:
    return settings.database_url