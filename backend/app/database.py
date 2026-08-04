from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# Create Async Engine
engine = create_async_engine(
    settings.database_url,
    echo=True,  # False in production
    pool_pre_ping=True,
)

# Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# Base Model
class Base(DeclarativeBase):
    pass
