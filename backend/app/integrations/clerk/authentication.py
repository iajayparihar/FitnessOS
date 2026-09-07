from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.clerk.client import clerk_client
from app.integrations.clerk.exceptions import ClerkAuthenticationError
from app.modules.auth.exceptions import InactiveUser, InvalidCredentials
from app.modules.auth.models import User


async def get_user_by_clerk_id(db: AsyncSession, *, clerk_user_id: str) -> User | None:
    """Return the local FitnessOS user mapped to a Clerk identity."""
    result = await db.execute(
        select(User).where(
            User.clerk_user_id == clerk_user_id,
            User.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def provision_user_from_clerk_claims(
    db: AsyncSession,
    *,
    claims: dict,
) -> User:
    """Create an idempotent local user for a valid Clerk identity."""
    clerk_user_id = str(claims.get("sub") or "").strip()
    if not clerk_user_id:
        raise ClerkAuthenticationError("Clerk token did not contain a user id.")

    existing_user = await get_user_by_clerk_id(db, clerk_user_id=clerk_user_id)
    if existing_user is not None:
        return existing_user

    email = claims.get("email") or claims.get("primary_email") or f"clerk-{clerk_user_id}@local.invalid"
    normalized_email = str(email).strip().lower()
    if normalized_email == "":
        normalized_email = f"clerk-{clerk_user_id}@local.invalid"

    result = await db.execute(
        select(User).where(
            func.lower(User.email) == normalized_email,
            User.deleted_at.is_(None),
        )
    )
    existing_email_user = result.scalar_one_or_none()
    if existing_email_user is not None:
        existing_email_user.clerk_user_id = clerk_user_id
        await db.flush()
        return existing_email_user

    user = User(
        clerk_user_id=clerk_user_id,
        email=normalized_email,
        email_verified=bool(claims.get("email_verified") or claims.get("is_email_verified")),
        is_active=True,
        is_superuser=False,
        last_login_at=datetime.now(UTC),
    )
    db.add(user)
    await db.flush()
    return user


async def authenticate_clerk_session(
    db: AsyncSession,
    *,
    token: str,
) -> User:
    """Validate a Clerk-issued session token and resolve the local user."""
    claims = clerk_client.verify_session_token(token)
    clerk_user_id = str(claims.get("sub") or "").strip()
    if not clerk_user_id:
        raise InvalidCredentials

    user = await get_user_by_clerk_id(db, clerk_user_id=clerk_user_id)
    if user is None:
        user = await provision_user_from_clerk_claims(db, claims=claims)
        await db.commit()
    else:
        user.last_login_at = datetime.now(UTC)
        await db.flush()

    if user is None or not user.is_active:
        raise InactiveUser

    return user
