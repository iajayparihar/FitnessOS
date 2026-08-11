from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.exceptions import InactiveUser, InvalidCredentials
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    AuthData,
    AuthResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    UserEnvelope,
)
from app.modules.auth.service import (
    login,
    refresh_tokens,
    register_owner,
    revoke_refresh_token,
)

router = APIRouter()


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Create an owner account and organization tenant."""
    try:
        user, organization, access_token, refresh_token = await register_owner(
            db,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
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


@router.post("/login", response_model=AuthResponse)
async def password_login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Authenticate with email and password."""
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


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Rotate a refresh token and issue a new token pair."""
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


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Revoke a refresh token."""
    await revoke_refresh_token(db, refresh_token=payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserEnvelope)
async def me(current_user: User = Depends(get_current_user)) -> UserEnvelope:
    """Return the authenticated user."""
    return UserEnvelope(data=current_user)
