from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError

logger = logging.getLogger("app.error")

# Maps Starlette HTTPException status codes to the standard error codes in
# docs/ERROR_HANDLING.md so existing routers that raise HTTPException still emit
# the standard envelope.
_STATUS_TO_CODE = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "BUSINESS_RULE_VIOLATION",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or [],
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


def _validation_details(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for error in errors:
        location = [str(part) for part in error.get("loc", []) if part != "body"]
        details.append(
            {"field": ".".join(location) or "body", "issue": error.get("msg", "Invalid.")}
        )
    return details


def register_error_handlers(app: FastAPI) -> None:
    """Translate exceptions into the standard error envelope."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        logger.log(
            logging.ERROR if exc.status_code >= 500 else logging.INFO,
            "app_error code=%s status=%s message=%s",
            exc.code,
            exc.status_code,
            exc.message,
        )
        return _error_response(
            request,
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=400,
            code="VALIDATION_ERROR",
            message="One or more fields are invalid.",
            details=_validation_details(exc.errors()),
        )

    @app.exception_handler(RateLimitExceeded)
    async def handle_rate_limit(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return _error_response(
            request,
            status_code=429,
            code="RATE_LIMITED",
            message="Too many requests. Please slow down.",
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = _STATUS_TO_CODE.get(exc.status_code, "INTERNAL_ERROR")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return _error_response(
            request,
            status_code=exc.status_code,
            code=code,
            message=message,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_error", exc_info=exc)
        return _error_response(
            request,
            status_code=500,
            code="INTERNAL_ERROR",
            message="An unexpected error occurred.",
        )
