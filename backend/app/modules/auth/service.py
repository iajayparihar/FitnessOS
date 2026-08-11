from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_secret,
    verify_password,
)
from app.modules.auth.exceptions import InactiveUser, InvalidCredentials
from app.modules.auth.models import AuthProvider, Session, User, UserAuthMethod, UserProfile
from app.modules.auth.schemas import LoginRequest, RegisterRequest
from app.modules.tenants.models import Organization
from app.modules.tenants.service import create_org, ensure_slug_available, make_slug


async def get_user_by_id(db: AsyncSession, *, user_id: uuid.UUID) -> User | None:
    """Return an active, non-deleted user by id."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.organization))
        .where(User.id == user_id, User.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def register_owner(
    db: AsyncSession,
    *,
    payload: RegisterRequest,
) -> tuple[User, Organization, str, str]:
    """Create an organization and its first owner user."""
    slug = make_slug(payload.organization.slug or payload.organization.name)
    await ensure_slug_available(db, slug=slug)
    organization_payload = payload.organization.model_copy(update={"slug": slug})
    organization = await create_org(db, payload=organization_payload)

    user = User(
        organization_id=organization.id,
        email=payload.email.strip().lower(),
        email_verified=False,
        is_active=True,
        is_superuser=False,
    )
    user.auth_methods.append(
        UserAuthMethod(
            provider=AuthProvider.PASSWORD,
            password_hash=hash_password(payload.password),
            is_primary=True,
        )
    )
    if payload.first_name or payload.last_name:
        user.profile = UserProfile(
            first_name=payload.first_name,
            last_name=payload.last_name,
        )

    db.add(user)
    await db.flush()
    organization.created_by = user.id
    organization.updated_by = user.id
    access_token, refresh_token = await create_session_tokens(db, user=user)
    await db.commit()
    await db.refresh(user)
    await db.refresh(organization)
    return user, organization, access_token, refresh_token


async def login(
    db: AsyncSession,
    *,
    payload: LoginRequest,
) -> tuple[User, str, str]:
    """Authenticate a password user and create a refresh session."""
    conditions = [
        func.lower(User.email) == payload.email.strip().lower(),
        User.deleted_at.is_(None),
    ]
    if payload.organization_id is not None:
        conditions.append(User.organization_id == payload.organization_id)

    result = await db.execute(
        select(User)
        .options(selectinload(User.auth_methods), selectinload(User.organization))
        .where(*conditions)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise InvalidCredentials
    if not user.is_active:
        raise InactiveUser

    password_method = next(
        (
            method
            for method in user.auth_methods
            if method.provider == AuthProvider.PASSWORD
        ),
        None,
    )
    if password_method is None or not verify_password(
        payload.password,
        password_method.password_hash,
    ):
        raise InvalidCredentials

    now = datetime.now(UTC)
    user.last_login_at = now
    password_method.last_used_at = now
    access_token, refresh_token = await create_session_tokens(db, user=user)
    await db.commit()
    await db.refresh(user)
    return user, access_token, refresh_token


async def create_session_tokens(
    db: AsyncSession,
    *,
    user: User,
) -> tuple[str, str]:
    """Create an access token and persist a hashed refresh token."""
    refresh_token = create_refresh_token()
    session = Session(
        user_id=user.id,
        organization_id=user.organization_id,
        refresh_token_hash=hash_secret(refresh_token),
        expires_at=datetime.now(UTC)
        + timedelta(days=settings.jwt_refresh_token_expire_days),
    )
    db.add(session)
    await db.flush()
    access_token = create_access_token(
        subject=user.id,
        organization_id=user.organization_id,
        is_superuser=user.is_superuser,
        session_id=session.id,
    )
    return access_token, refresh_token


async def get_valid_session_by_id(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
) -> Session | None:
    """Return a non-revoked, non-expired session by id."""
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.revoked_at.is_(None),
            Session.expires_at > datetime.now(UTC),
        )
    )
    return result.scalar_one_or_none()


async def refresh_tokens(
    db: AsyncSession,
    *,
    refresh_token: str,
) -> tuple[User, str, str]:
    """Rotate a valid refresh token and return a new token pair."""
    result = await db.execute(
        select(Session)
        .options(selectinload(Session.user).selectinload(User.organization))
        .where(Session.refresh_token_hash == hash_secret(refresh_token))
    )
    session = result.scalar_one_or_none()
    now = datetime.now(UTC)
    if (
        session is None
        or session.revoked_at is not None
        or session.expires_at <= now
        or not session.user.is_active
        or session.user.deleted_at is not None
    ):
        raise InvalidCredentials

    session.revoked_at = now
    access_token, new_refresh_token = await create_session_tokens(db, user=session.user)
    await db.commit()
    await db.refresh(session.user)
    return session.user, access_token, new_refresh_token


async def revoke_refresh_token(
    db: AsyncSession,
    *,
    refresh_token: str,
) -> None:
    """Revoke a refresh token if it exists."""
    result = await db.execute(
        select(Session).where(Session.refresh_token_hash == hash_secret(refresh_token))
    )
    session = result.scalar_one_or_none()
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
        await db.commit()
