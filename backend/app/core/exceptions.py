from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base application error rendered by the centralized error handler.

    Subclasses set ``code`` and ``status_code``; ``message`` and ``details`` can
    be overridden per raise. Routers should raise these instead of building error
    responses by hand (see ``docs/ERROR_HANDLING.md``).

    """

    code: str = "INTERNAL_ERROR"
    status_code: int = 500
    message: str = "Something went wrong."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details or []
        super().__init__(self.message)


class ValidationError(AppError):
    code = "VALIDATION_ERROR"
    status_code = 400
    message = "One or more fields are invalid."


class UnauthenticatedError(AppError):
    code = "UNAUTHENTICATED"
    status_code = 401
    message = "Authentication required."


class ForbiddenError(AppError):
    code = "FORBIDDEN"
    status_code = 403
    message = "You do not have permission to perform this action."


class NotFoundError(AppError):
    code = "NOT_FOUND"
    status_code = 404
    message = "The requested resource was not found."


class ConflictError(AppError):
    code = "CONFLICT"
    status_code = 409
    message = "The resource conflicts with an existing one."


class BusinessRuleError(AppError):
    code = "BUSINESS_RULE_VIOLATION"
    status_code = 422
    message = "The request violates a business rule."
