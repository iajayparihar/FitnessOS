from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.exceptions import AlreadyOnboarded, InviteInvalid
from app.modules.auth.models import (
    AuthProvider,
    Invite,
    User,
    UserAuthMethod,
    UserProfile,
)
from app.modules.auth.schemas import OnboardingRequest
from app.modules.rbac.service import assign_role_to_user, ensure_owner_role
from app.modules.tenants.models import Organization
from app.modules.tenants.service import (
    create_org,
    ensure_slug_available,
    get_org_by_id,
    make_slug,
)


async def get_user_by_id(db: AsyncSession, *, user_id: uuid.UUID) -> User | None:
    """Return an active, non-deleted user by id."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.organization))
        .where(User.id == user_id, User.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def get_or_create_user_from_clerk(
    db: AsyncSession,
    *,
    claims: dict,
) -> User:
    """Resolve the local user for a Clerk identity, provisioning on first sight.

    The Clerk user id (``sub``) is stored as a ``CLERK`` auth method; ``email``
    and name claims (exposed via a Clerk JWT template) seed the local record.

    """
    clerk_uid = str(claims["sub"])
    result = await db.execute(
        select(UserAuthMethod)
        .options(selectinload(UserAuthMethod.user).selectinload(User.organization))
        .where(
            UserAuthMethod.provider == AuthProvider.CLERK,
            UserAuthMethod.provider_uid == clerk_uid,
        )
    )
    method = result.scalar_one_or_none()
    if method is not None:
        # Hot path: verified on every request, so avoid a write here.
        return method.user

    now = datetime.now(UTC)
    user = User(
        organization_id=None,
        email=(claims.get("email") or "").strip().lower(),
        email_verified=bool(claims.get("email_verified", True)),
        is_active=True,
        is_superuser=False,
        last_login_at=now,
    )
    user.auth_methods.append(
        UserAuthMethod(
            provider=AuthProvider.CLERK,
            provider_uid=clerk_uid,
            is_primary=True,
            last_used_at=now,
        )
    )
    first_name = claims.get("first_name")
    last_name = claims.get("last_name")
    if first_name or last_name:
        user.profile = UserProfile(first_name=first_name, last_name=last_name)

    db.add(user)
    await db.flush()
    await db.commit()
    await db.refresh(user)
    return user


async def onboard_organization(
    db: AsyncSession,
    *,
    user: User,
    payload: OnboardingRequest,
) -> tuple[User, Organization]:
    """Create an organization for an orgless user and make them its owner."""
    if user.organization_id is not None:
        raise AlreadyOnboarded

    slug = make_slug(payload.organization.slug or payload.organization.name)
    await ensure_slug_available(db, slug=slug)
    organization_payload = payload.organization.model_copy(update={"slug": slug})
    organization = await create_org(db, payload=organization_payload, created_by=user.id)

    user.organization_id = organization.id
    await db.flush()

    owner_role = await ensure_owner_role(db, organization_id=organization.id)
    await assign_role_to_user(
        db,
        user_id=user.id,
        role_id=owner_role.id,
        organization_id=organization.id,
        assigned_by=user.id,
    )
    await db.commit()
    await db.refresh(user)
    await db.refresh(organization)
    return user, organization


async def accept_invite(
    db: AsyncSession,
    *,
    user: User,
    token: str,
) -> tuple[User, Organization]:
    """Accept an organization invite and assign its role to the user."""
    if user.organization_id is not None:
        raise AlreadyOnboarded

    result = await db.execute(select(Invite).where(Invite.token == token))
    invite = result.scalar_one_or_none()
    now = datetime.now(UTC)
    if (
        invite is None
        or invite.accepted_at is not None
        or invite.expires_at <= now
        or invite.email.strip().lower() != user.email.strip().lower()
    ):
        raise InviteInvalid

    user.organization_id = invite.organization_id
    invite.accepted_at = now
    await db.flush()

    if invite.role_id is not None:
        await assign_role_to_user(
            db,
            user_id=user.id,
            role_id=invite.role_id,
            organization_id=invite.organization_id,
            assigned_by=invite.invited_by,
        )

    organization = await get_org_by_id(db, organization_id=invite.organization_id)
    await db.commit()
    await db.refresh(user)
    return user, organization
