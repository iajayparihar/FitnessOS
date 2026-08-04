"""This module contains the dependencies for the FastAPI application, including the database session dependency."""

from app.database import AsyncSessionLocal


async def get_db():
    """This function is a FastAPI dependency that provides an asynchronous database session for each request."""
    async with AsyncSessionLocal() as session:
        """This context manager ensures that the session is properly closed after the request is completed."""
        yield session
