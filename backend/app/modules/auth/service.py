from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.enums import NotificationChannel, NotificationStatus
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_secret,
    verify_password,
)
from app.modules.analytics.service import log_audit_event
from app.modules.auth.exceptions import (
    AuthActionRateLimited,
    InactiveUser,
    InvalidAuthActionToken,
    InvalidCredentials,
)
from app.modules.auth.models import (
    AuthActionToken,
    AuthActionTokenPurpose,
    AuthProvider,
    Session,
    User,
    UserAuthMethod,
    UserProfile,
)
from app.modules.auth.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from app.modules.notifications.models import Notification, RecipientType
from app.modules.rbac.service import assign_role_to_user, ensure_owner_role
from app.modules.tenants.models import Organization
from app.modules.tenants.service import create_org, ensure_slug_available, make_slug

ACTION_TOKEN_BYTES = 48


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

    owner_role = await ensure_owner_role(db, organization_id=organization.id)
    await assign_role_to_user(
        db,
        user_id=user.id,
        role_id=owner_role.id,
        organization_id=organization.id,
        assigned_by=user.id,
    )
    access_token, refresh_token = await create_session_tokens(db, user=user)
    await request_email_verification_for_user(db, user=user, commit=False)
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
    if user.organization is not None and user.organization.created_by == user.id:
        owner_role = await ensure_owner_role(db, organization_id=user.organization_id)
        await assign_role_to_user(
            db,
            user_id=user.id,
            role_id=owner_role.id,
            organization_id=user.organization_id,
            assigned_by=user.id,
        )
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


def generate_action_token() -> str:
    """Create a high-entropy raw auth action token."""
    return secrets.token_urlsafe(ACTION_TOKEN_BYTES)


def hash_action_token(token: str) -> str:
    """Hash an auth action token for storage and lookup."""
    return hash_secret(token)


def _frontend_url(path: str, token: str) -> str:
    base_url = settings.auth_frontend_base_url.rstrip("/")
    return f"{base_url}/{path.lstrip('/')}?token={token}"


def _token_expires_at(purpose: AuthActionTokenPurpose) -> datetime:
    now = datetime.now(UTC)
    if purpose == AuthActionTokenPurpose.PASSWORD_RESET:
        return now + timedelta(minutes=settings.password_reset_token_expire_minutes)
    return now + timedelta(hours=settings.email_verification_token_expire_hours)


async def _resolve_active_user_for_email(
    db: AsyncSession,
    *,
    email: str,
    organization_id: uuid.UUID | None,
) -> User | None:
    conditions = [
        func.lower(User.email) == email.strip().lower(),
        User.deleted_at.is_(None),
        User.is_active.is_(True),
        User.organization_id.isnot(None),
    ]
    if organization_id is not None:
        conditions.append(User.organization_id == organization_id)

    result = await db.execute(
        select(User)
        .options(selectinload(User.auth_methods), selectinload(User.organization))
        .where(*conditions)
    )
    users = list(result.scalars())
    if len(users) != 1:
        return None
    return users[0]


async def invalidate_previous_action_tokens(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    purpose: AuthActionTokenPurpose,
    now: datetime,
) -> None:
    """Mark previous unused tokens unusable before issuing a replacement."""
    await db.execute(
        update(AuthActionToken)
        .where(
            AuthActionToken.user_id == user_id,
            AuthActionToken.purpose == purpose,
            AuthActionToken.used_at.is_(None),
        )
        .values(used_at=now)
    )


async def _recent_action_token_exists(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    purpose: AuthActionTokenPurpose,
    now: datetime,
) -> bool:
    result = await db.execute(
        select(AuthActionToken.id)
        .where(
            AuthActionToken.user_id == user_id,
            AuthActionToken.purpose == purpose,
            AuthActionToken.created_at
            >= now - timedelta(seconds=settings.auth_action_token_cooldown_seconds),
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def create_action_token(
    db: AsyncSession,
    *,
    user: User,
    purpose: AuthActionTokenPurpose,
    now: datetime,
) -> tuple[str, AuthActionToken]:
    """Invalidate older tokens and create a new hashed one-time token."""
    await invalidate_previous_action_tokens(
        db,
        user_id=user.id,
        purpose=purpose,
        now=now,
    )
    raw_token = generate_action_token()
    action_token = AuthActionToken(
        user_id=user.id,
        organization_id=user.organization_id,
        purpose=purpose,
        token_hash=hash_action_token(raw_token),
        expires_at=_token_expires_at(purpose),
    )
    db.add(action_token)
    await db.flush()
    return raw_token, action_token


async def validate_action_token(
    db: AsyncSession,
    *,
    token: str,
    purpose: AuthActionTokenPurpose,
    now: datetime,
) -> AuthActionToken:
    """Return a usable action token or raise a generic token error."""
    result = await db.execute(
        select(AuthActionToken)
        .options(selectinload(AuthActionToken.user).selectinload(User.auth_methods))
        .where(
            AuthActionToken.token_hash == hash_action_token(token),
            AuthActionToken.purpose == purpose,
            AuthActionToken.used_at.is_(None),
            AuthActionToken.expires_at > now,
        )
    )
    action_token = result.scalar_one_or_none()
    if (
        action_token is None
        or action_token.user is None
        or not action_token.user.is_active
        or action_token.user.deleted_at is not None
        or action_token.user.organization_id != action_token.organization_id
    ):
        raise InvalidAuthActionToken
    return action_token


async def _create_auth_notification(
    db: AsyncSession,
    *,
    user: User,
    action: str,
    url: str,
    expires_at: datetime,
) -> Notification:
    notification = Notification(
        organization_id=user.organization_id,
        channel=NotificationChannel.EMAIL,
        recipient_type=RecipientType.USER,
        recipient_id=user.id,
        recipient_contact=user.email,
        payload={
            "action": action,
            "url": url,
            "expires_at": expires_at.isoformat(),
        },
        status=NotificationStatus.PENDING,
    )
    db.add(notification)
    await db.flush()
    return notification


async def request_password_reset(
    db: AsyncSession,
    *,
    payload: ForgotPasswordRequest,
) -> None:
    """Create a password reset token and email outbox entry when safe to do so."""
    user = await _resolve_active_user_for_email(
        db,
        email=payload.email,
        organization_id=payload.organization_id,
    )
    if user is None:
        return

    now = datetime.now(UTC)
    if await _recent_action_token_exists(
        db,
        user_id=user.id,
        purpose=AuthActionTokenPurpose.PASSWORD_RESET,
        now=now,
    ):
        return

    raw_token, action_token = await create_action_token(
        db,
        user=user,
        purpose=AuthActionTokenPurpose.PASSWORD_RESET,
        now=now,
    )
    await _create_auth_notification(
        db,
        user=user,
        action="password_reset",
        url=_frontend_url("reset-password", raw_token),
        expires_at=action_token.expires_at,
    )
    await log_audit_event(
        db,
        action="auth.password_reset.requested",
        organization_id=user.organization_id,
        actor_id=user.id,
        target_type="user",
        target_id=user.id,
    )
    await db.commit()


async def reset_password(
    db: AsyncSession,
    *,
    payload: ResetPasswordRequest,
) -> None:
    """Reset a password, consume the token, and revoke sessions atomically."""
    now = datetime.now(UTC)
    action_token = await validate_action_token(
        db,
        token=payload.token,
        purpose=AuthActionTokenPurpose.PASSWORD_RESET,
        now=now,
    )
    user = action_token.user
    password_method = next(
        (
            method
            for method in user.auth_methods
            if method.provider == AuthProvider.PASSWORD
        ),
        None,
    )
    if password_method is None:
        raise InvalidAuthActionToken

    password_method.password_hash = hash_password(payload.new_password)
    password_method.last_used_at = None
    action_token.used_at = now
    await db.execute(
        update(Session)
        .where(Session.user_id == user.id, Session.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await log_audit_event(
        db,
        action="auth.password_reset.completed",
        organization_id=user.organization_id,
        actor_id=user.id,
        target_type="user",
        target_id=user.id,
    )
    await db.commit()


async def request_email_verification_for_user(
    db: AsyncSession,
    *,
    user: User,
    commit: bool = True,
    audit_action: str | None = "auth.email_verification.requested",
) -> None:
    """Create an email verification token and notification for an unverified user."""
    if user.email_verified or user.organization_id is None:
        if commit:
            await db.commit()
        return

    now = datetime.now(UTC)
    raw_token, action_token = await create_action_token(
        db,
        user=user,
        purpose=AuthActionTokenPurpose.EMAIL_VERIFICATION,
        now=now,
    )
    await _create_auth_notification(
        db,
        user=user,
        action="email_verification",
        url=_frontend_url("verify-email", raw_token),
        expires_at=action_token.expires_at,
    )
    if audit_action is not None:
        await log_audit_event(
            db,
            action=audit_action,
            organization_id=user.organization_id,
            actor_id=user.id,
            target_type="user",
            target_id=user.id,
        )
    if commit:
        await db.commit()


async def resend_email_verification(
    db: AsyncSession,
    *,
    payload: ResendVerificationRequest,
) -> None:
    """Resend verification email for an unverified user without enumeration."""
    user = await _resolve_active_user_for_email(
        db,
        email=payload.email,
        organization_id=payload.organization_id,
    )
    if user is None or user.email_verified:
        return

    now = datetime.now(UTC)
    if await _recent_action_token_exists(
        db,
        user_id=user.id,
        purpose=AuthActionTokenPurpose.EMAIL_VERIFICATION,
        now=now,
    ):
        raise AuthActionRateLimited

    await request_email_verification_for_user(
        db,
        user=user,
        commit=False,
        audit_action="auth.email_verification.resent",
    )
    await db.commit()


async def verify_email(
    db: AsyncSession,
    *,
    payload: VerifyEmailRequest,
) -> None:
    """Verify a user's email with a one-time token."""
    now = datetime.now(UTC)
    action_token = await validate_action_token(
        db,
        token=payload.token,
        purpose=AuthActionTokenPurpose.EMAIL_VERIFICATION,
        now=now,
    )
    user = action_token.user
    user.email_verified = True
    action_token.used_at = now
    await log_audit_event(
        db,
        action="auth.email_verified",
        organization_id=user.organization_id,
        actor_id=user.id,
        target_type="user",
        target_id=user.id,
    )
    await db.commit()
