from __future__ import annotations

import logging
import uuid

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import TokenExpired, decode_jwt
from app.db.session import get_db
from app.integrations.clerk.authentication import authenticate_clerk_session
from app.integrations.clerk.exceptions import (
    ClerkAuthenticationError,
    ClerkConfigurationError,
    ClerkIdentityConflict,
)
from app.modules.auth.context import AuthenticatedContext, build_authenticated_context
from app.modules.auth.exceptions import InactiveUser, InvalidCredentials
from app.modules.auth.models import User
from app.modules.auth.service import get_user_by_id, get_valid_session_by_id

logger = logging.getLogger("app.auth")

bearer_scheme = HTTPBearer(auto_error=False)

LEGACY_JWT_ALGORITHM = "HS256"


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def _log_auth_failure(request: Request | None, *, category: str) -> None:
    """Record an authentication failure without ever touching the credential."""
    logger.info(
        "auth.failed",
        extra={
            "failure_category": category,
            "endpoint": request.url.path if request is not None else None,
            "request_id": (
                request.headers.get("x-request-id") if request is not None else None
            ),
        },
    )


def _log_auth_success(request: Request | None, *, user: User, method: str) -> None:
    logger.info(
        "auth.succeeded",
        extra={
            "auth_method": method,
            "user_id": str(user.id),
            "organization_id": (
                str(user.organization_id) if user.organization_id else None
            ),
            "endpoint": request.url.path if request is not None else None,
            "request_id": (
                request.headers.get("x-request-id") if request is not None else None
            ),
        },
    )


def _is_legacy_token(token: str) -> bool:
    """
    Route a bearer token to the legacy verifier by its signing algorithm.

    Reading the unverified header only decides which verifier runs; both paths
    verify the signature in full before the token is trusted.
    """
    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        return False
    return header.get("alg") == LEGACY_JWT_ALGORITHM


async def _authenticate_legacy_session(db: AsyncSession, *, token: str) -> User:
    """Authenticate a legacy FitnessOS access token against a server-side session."""
    try:
        payload = decode_jwt(token)
        if payload.get("type") != "access":
            raise ValueError("Expected access token.")
        user_id = uuid.UUID(str(payload["sub"]))
        session_id = uuid.UUID(str(payload["sid"]))
    except TokenExpired as exc:
        raise _unauthorized("Access token has expired.") from exc
    except (KeyError, ValueError) as exc:
        raise _unauthorized("Invalid access token.") from exc

    session = await get_valid_session_by_id(db, session_id=session_id)
    if session is None or session.user_id != user_id:
        raise _unauthorized("Invalid access token.")

    user = await get_user_by_id(db, user_id=user_id)
    if user is None or not user.is_active:
        raise _unauthorized("Invalid access token.")
    return user


async def get_current_user(
    request: Request = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Resolve the authenticated FitnessOS user from a bearer token.

    Clerk is the authentication authority. The legacy password/session token path
    runs only while LEGACY_PASSWORD_AUTH_ENABLED is set, and is selected by the
    token's signing algorithm rather than by falling back after a failure, so the
    two verifiers never compete over the same token.
    """
    if credentials is None:
        _log_auth_failure(request, category="missing_credentials")
        raise _unauthorized("Authentication required.")

    token = credentials.credentials
    if not token or not token.strip():
        _log_auth_failure(request, category="malformed_credentials")
        raise _unauthorized("Authentication required.")

    if settings.legacy_password_auth_enabled and _is_legacy_token(token):
        try:
            user = await _authenticate_legacy_session(db, token=token)
        except HTTPException:
            _log_auth_failure(request, category="legacy_token_rejected")
            raise
        _log_auth_success(request, user=user, method="legacy_password")
        return user

    try:
        user = await authenticate_clerk_session(db, token=token)
    except ClerkConfigurationError as exc:
        logger.error("auth.clerk_misconfigured", extra={"failure_category": str(exc)})
        _log_auth_failure(request, category="clerk_misconfigured")
        raise _unauthorized("Invalid access token.") from exc
    except ClerkIdentityConflict as exc:
        _log_auth_failure(request, category="clerk_identity_conflict")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except (ClerkAuthenticationError, InvalidCredentials) as exc:
        _log_auth_failure(request, category="clerk_token_rejected")
        raise _unauthorized("Invalid access token.") from exc
    except InactiveUser as exc:
        _log_auth_failure(request, category="inactive_user")
        raise _unauthorized("Invalid access token.") from exc

    _log_auth_success(request, user=user, method="clerk")
    return user


async def get_auth_context(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuthenticatedContext:
    """Resolve identity plus FitnessOS tenant, role and permission state."""
    return await build_authenticated_context(db, user=current_user)


async def require_organization(
    context: AuthenticatedContext = Depends(get_auth_context),
) -> AuthenticatedContext:
    """Require that the authenticated user belongs to a tenant."""
    if context.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization membership required.",
        )
    return context
