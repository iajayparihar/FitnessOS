from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.modules.auth.context import AuthenticatedContext
from app.modules.auth.dependencies import get_auth_context, get_current_user
from app.modules.auth.exceptions import (
    AlreadyOnboarded,
    InactiveUser,
    InvalidCredentials,
)
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    AuthContextData,
    AuthContextResponse,
    AuthData,
    AuthResponse,
    LoginRequest,
    LogoutRequest,
    OnboardingData,
    OnboardingRequest,
    OnboardingResponse,
    RefreshRequest,
    RegisterRequest,
    UserEnvelope,
)
from app.modules.auth.service import (
    login,
    onboard_clerk_user,
    refresh_tokens,
    register_owner,
    revoke_refresh_token,
)

router = APIRouter()

# Onboarding provisions a tenant, so it is the one authenticated route worth
# throttling; ordinary authenticated gym traffic is deliberately left alone.
onboarding_rate_limit = rate_limit(
    limit=10,
    window_seconds=60.0,
    scope="auth.onboarding",
)


async def require_legacy_password_auth() -> None:
    """
    Gate the pre-Clerk password endpoints behind an explicit feature flag.

    Clerk owns authentication. These routes stay in the schema for migration
    compatibility but answer 404 unless LEGACY_PASSWORD_AUTH_ENABLED is set, so
    the old credentials path cannot be reached by accident.
    """
    if not settings.legacy_password_auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found.",
        )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    deprecated=True,
    dependencies=[Depends(require_legacy_password_auth)],
)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Create an owner account and organization tenant (legacy password flow)."""
    try:
        user, organization, access_token, refresh_token = await register_owner(
            db,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User or organization already exists.",
        ) from exc

    return AuthResponse(
        data=AuthData(
            access_token=access_token,
            refresh_token=refresh_token,
            user=user,
            organization=organization,
        )
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    deprecated=True,
    dependencies=[Depends(require_legacy_password_auth)],
)
async def password_login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Authenticate with email and password (legacy password flow)."""
    try:
        user, access_token, refresh_token = await login(db, payload=payload)
    except (InactiveUser, InvalidCredentials) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        ) from exc

    return AuthResponse(
        data=AuthData(
            access_token=access_token,
            refresh_token=refresh_token,
            user=user,
            organization=user.organization,
        )
    )


@router.post(
    "/refresh",
    response_model=AuthResponse,
    deprecated=True,
    dependencies=[Depends(require_legacy_password_auth)],
)
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Rotate a legacy refresh token and issue a new token pair."""
    try:
        user, access_token, refresh_token = await refresh_tokens(
            db,
            refresh_token=payload.refresh_token,
        )
    except InvalidCredentials as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token.",
        ) from exc

    return AuthResponse(
        data=AuthData(
            access_token=access_token,
            refresh_token=refresh_token,
            user=user,
            organization=user.organization,
        )
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    deprecated=True,
    dependencies=[Depends(require_legacy_password_auth)],
)
async def logout(
    payload: LogoutRequest,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Revoke a legacy refresh token.

    Clerk sessions are ended by the frontend calling Clerk's signOut(); revoking a
    FitnessOS refresh token does not end a Clerk session.
    """
    await revoke_refresh_token(db, refresh_token=payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/onboarding",
    response_model=OnboardingResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(onboarding_rate_limit)],
)
async def onboarding(
    payload: OnboardingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingResponse:
    """Provision an organization tenant for the authenticated Clerk user."""
    try:
        user, organization = await onboard_clerk_user(
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
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization already exists.",
        ) from exc

    return OnboardingResponse(data=OnboardingData(user=user, organization=organization))


@router.get("/me", response_model=UserEnvelope)
async def me(current_user: User = Depends(get_current_user)) -> UserEnvelope:
    """Return the authenticated user."""
    return UserEnvelope(data=current_user)


@router.get("/context", response_model=AuthContextResponse)
async def auth_context(
    context: AuthenticatedContext = Depends(get_auth_context),
) -> AuthContextResponse:
    """Return the authenticated identity with its FitnessOS authorization state."""
    return AuthContextResponse(
        data=AuthContextData(
            user=context.user,
            organization=context.user.organization,
            role_slugs=list(context.role_slugs),
            permissions=sorted(context.permissions),
        )
    )
