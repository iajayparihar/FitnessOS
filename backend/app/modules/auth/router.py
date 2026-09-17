from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.dev_auth import mint_dev_token
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.exceptions import AlreadyOnboarded, InviteInvalid
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    AccountData,
    AccountResponse,
    DevLoginRequest,
    DevTokenData,
    DevTokenResponse,
    InviteAcceptRequest,
    OnboardingRequest,
    UserEnvelope,
)
from app.modules.auth.service import accept_invite, onboard_organization

router = APIRouter()


@router.post("/dev/login", response_model=DevTokenResponse)
async def dev_login(payload: DevLoginRequest) -> DevTokenResponse:
    """Issue a local dev session token (only when DEV_AUTH_ENABLED)."""
    if not settings.dev_auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found.",
        )
    token = mint_dev_token(
        email=payload.email,
        first_name=payload.first_name,
        last_name=payload.last_name,
    )
    return DevTokenResponse(data=DevTokenData(access_token=token))


@router.get("/me", response_model=UserEnvelope)
async def me(current_user: User = Depends(get_current_user)) -> UserEnvelope:
    """Return the authenticated user."""
    return UserEnvelope(data=current_user)


@router.post(
    "/onboarding",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(settings.rate_limit_sensitive)
async def onboarding(
    request: Request,
    payload: OnboardingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AccountResponse:
    """Create an organization and make the current user its owner."""
    try:
        user, organization = await onboard_organization(
            db,
            user=current_user,
            payload=payload,
        )
    except AlreadyOnboarded as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already belongs to an organization.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization already exists.",
        ) from exc

    return AccountResponse(data=AccountData(user=user, organization=organization))


@router.post("/invites/accept", response_model=AccountResponse)
@limiter.limit(settings.rate_limit_sensitive)
async def accept_invitation(
    request: Request,
    payload: InviteAcceptRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AccountResponse:
    """Accept an organization invite and join with the invited role."""
    try:
        user, organization = await accept_invite(
            db,
            user=current_user,
            token=payload.token,
        )
    except AlreadyOnboarded as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already belongs to an organization.",
        ) from exc
    except InviteInvalid as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invite is invalid or expired.",
        ) from exc

    return AccountResponse(data=AccountData(user=user, organization=organization))
