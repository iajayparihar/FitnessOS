"""Factories for FitnessOS users and their Clerk identity mapping."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import AuthProvider, User, UserAuthMethod


async def create_clerk_user(
    db: AsyncSession,
    *,
    clerk_user_id: str | None = None,
    email: str | None = None,
    organization_id: uuid.UUID | None = None,
    is_active: bool = True,
    is_superuser: bool = False,
) -> User:
    """Create a local user backed by a Clerk identity."""
    clerk_user_id = clerk_user_id or f"user_{uuid.uuid4().hex[:12]}"
    user = User(
        clerk_user_id=clerk_user_id,
        email=email or f"{clerk_user_id}@example.com",
        email_verified=True,
        is_active=is_active,
        is_superuser=is_superuser,
        organization_id=organization_id,
    )
    user.auth_methods.append(
        UserAuthMethod(
            provider=AuthProvider.CLERK,
            provider_uid=clerk_user_id,
            is_primary=True,
        )
    )
    db.add(user)
    await db.commit()
    return user
