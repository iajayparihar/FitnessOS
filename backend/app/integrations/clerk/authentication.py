from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.integrations.clerk.client import clerk_client
from app.integrations.clerk.exceptions import (
    ClerkAuthenticationError,
    ClerkIdentityConflict,
)
from app.modules.auth.exceptions import InactiveUser
from app.modules.auth.models import AuthProvider, User, UserAuthMethod

logger = logging.getLogger("app.auth")

# Writing last_login_at on every authenticated request would add a write to each
# API call; a coarse threshold keeps the signal useful without the cost.
LAST_LOGIN_REFRESH_INTERVAL = timedelta(minutes=15)


@dataclass(frozen=True)
class ClerkIdentity:
    """A verified Clerk identity, independent of any FitnessOS record."""

    clerk_user_id: str
    email: str | None
    email_verified: bool
    session_id: str | None

    @property
    def fallback_email(self) -> str:
        """Return a stable placeholder for Clerk tokens that carry no email claim."""
        return f"clerk-{self.clerk_user_id}@local.invalid"

    @property
    def local_email(self) -> str:
        """Return the email to store on a newly provisioned local user."""
        return (
            self.email or self.fallback_email
        ).strip().lower() or self.fallback_email


def identity_from_claims(claims: dict[str, Any]) -> ClerkIdentity:
    """Build a ClerkIdentity from verified session-token claims."""
    clerk_user_id = str(claims.get("sub") or "").strip()
    if not clerk_user_id:
        raise ClerkAuthenticationError("Clerk token did not contain a user id.")

    raw_email = claims.get("email") or claims.get("primary_email")
    email = str(raw_email).strip().lower() if raw_email else None
    email_verified = bool(
        claims.get("email_verified") or claims.get("is_email_verified")
    )
    session_id = claims.get("sid")
    return ClerkIdentity(
        clerk_user_id=clerk_user_id,
        email=email or None,
        email_verified=email_verified,
        session_id=str(session_id) if session_id else None,
    )


async def get_user_by_clerk_id(db: AsyncSession, *, clerk_user_id: str) -> User | None:
    """Return the local FitnessOS user mapped to a Clerk identity."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.organization), selectinload(User.auth_methods))
        .where(
            User.clerk_user_id == clerk_user_id,
            User.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


def ensure_clerk_auth_method(*, user: User, clerk_user_id: str) -> None:
    """
    Bind exactly one Clerk auth method to the user.

    The caller must have loaded ``user.auth_methods`` eagerly.
    """
    for auth_method in user.auth_methods:
        if auth_method.provider == AuthProvider.CLERK:
            if auth_method.provider_uid != clerk_user_id:
                auth_method.provider_uid = clerk_user_id
            auth_method.last_used_at = datetime.now(UTC)
            return

    user.auth_methods.append(
        UserAuthMethod(
            provider=AuthProvider.CLERK,
            provider_uid=clerk_user_id,
            is_primary=True,
            last_used_at=datetime.now(UTC),
        )
    )


async def _find_linkable_user_by_email(
    db: AsyncSession,
    *,
    identity: ClerkIdentity,
) -> User | None:
    """
    Return an unlinked local user matching a verified Clerk email.

    This is the controlled migration path for users that predate Clerk. It is off
    unless CLERK_LINK_EXISTING_USERS_BY_EMAIL is enabled, and it refuses to act on
    an unverified email so that a Clerk sign-up cannot claim someone else's
    account by asserting their address.
    """
    if not settings.clerk_link_existing_users_by_email:
        return None
    if not identity.email or not identity.email_verified:
        return None

    result = await db.execute(
        select(User)
        .options(selectinload(User.organization), selectinload(User.auth_methods))
        .where(
            func.lower(User.email) == identity.email,
            User.clerk_user_id.is_(None),
            User.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def _reject_conflicting_email(
    db: AsyncSession,
    *,
    identity: ClerkIdentity,
) -> None:
    """
    Refuse to provision when another local user already owns the email.

    Reached only after linking has been declined, so the alternatives would be to
    take over an account this identity has not proven it owns, or to store a
    placeholder email that misrepresents the user. Both are worse than refusing
    and surfacing the collision to an operator.
    """
    result = await db.execute(
        select(User.id).where(
            func.lower(User.email) == identity.local_email,
            User.deleted_at.is_(None),
        )
    )
    if result.scalar_one_or_none() is not None:
        logger.warning(
            "clerk.user.email_conflict",
            extra={"clerk_user_id": identity.clerk_user_id},
        )
        raise ClerkIdentityConflict(
            "This email is already registered to a different FitnessOS account."
        )


async def provision_user_from_identity(
    db: AsyncSession,
    *,
    identity: ClerkIdentity,
) -> User:
    """
    Return the local user for a Clerk identity, creating it when absent.

    Idempotent: concurrent first-time sign-ins converge on a single row because
    the partial unique index on ``users.clerk_user_id`` rejects the loser, which
    then re-reads the winner's record.
    """
    existing_user = await get_user_by_clerk_id(db, clerk_user_id=identity.clerk_user_id)
    if existing_user is not None:
        return existing_user

    linked_user = await _find_linkable_user_by_email(db, identity=identity)
    if linked_user is not None:
        linked_user.clerk_user_id = identity.clerk_user_id
        ensure_clerk_auth_method(user=linked_user, clerk_user_id=identity.clerk_user_id)
        await db.commit()
        logger.info(
            "clerk.user.linked",
            extra={
                "clerk_user_id": identity.clerk_user_id,
                "user_id": str(linked_user.id),
                "organization_id": (
                    str(linked_user.organization_id)
                    if linked_user.organization_id
                    else None
                ),
            },
        )
        return linked_user

    await _reject_conflicting_email(db, identity=identity)

    user = User(
        clerk_user_id=identity.clerk_user_id,
        email=identity.local_email,
        email_verified=identity.email_verified,
        is_active=True,
        is_superuser=False,
        last_login_at=datetime.now(UTC),
    )
    ensure_clerk_auth_method(user=user, clerk_user_id=identity.clerk_user_id)
    db.add(user)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        user = await get_user_by_clerk_id(db, clerk_user_id=identity.clerk_user_id)
        if user is None:
            raise ClerkAuthenticationError(
                "Clerk user could not be provisioned reliably."
            ) from None
        return user

    logger.info(
        "clerk.user.provisioned",
        extra={
            "clerk_user_id": identity.clerk_user_id,
            "user_id": str(user.id),
            "organization_id": None,
        },
    )
    return user


async def _touch_last_login(db: AsyncSession, *, user: User) -> None:
    """Refresh last_login_at at most once per LAST_LOGIN_REFRESH_INTERVAL."""
    now = datetime.now(UTC)
    last_login_at = user.last_login_at
    if last_login_at is not None and last_login_at.tzinfo is None:
        last_login_at = last_login_at.replace(tzinfo=UTC)
    if last_login_at is not None and now - last_login_at < LAST_LOGIN_REFRESH_INTERVAL:
        return

    user.last_login_at = now
    await db.commit()


async def authenticate_clerk_session(db: AsyncSession, *, token: str) -> User:
    """Verify a Clerk session token and resolve the local FitnessOS user."""
    claims = clerk_client.verify_session_token(token)
    identity = identity_from_claims(claims)

    user = await provision_user_from_identity(db, identity=identity)
    if not user.is_active:
        raise InactiveUser

    await _touch_last_login(db, user=user)
    return user
