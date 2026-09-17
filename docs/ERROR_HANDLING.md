# Error Handling Standards

## Fitness Business OS

---

## 1. Goals

- Every error response has a **consistent, predictable shape** across the entire API.
- Errors are actionable for frontend developers (and future third-party API consumers) — they can branch on `error.code`, not parse `error.message` strings.
- No internal details (stack traces, SQL, file paths) ever leak to the client.
- Every error is traceable back to a specific request via a `request_id`, correlated with server-side logs (`OBSERVABILITY.md`).

---

## 2. Standard Error Response Shape

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "One or more fields are invalid.",
    "details": [
      { "field": "email", "issue": "Invalid email format." }
    ],
    "request_id": "req_01HXYZ1234ABCD"
  }
}
```

| Field | Description |
|---|---|
| `code` | Machine-readable, stable error code (SCREAMING_SNAKE_CASE) — frontend/clients branch on this |
| `message` | Human-readable summary, safe to display or log (no internals) |
| `details` | Optional array of field-level or context-specific issues |
| `request_id` | Correlates this response to server-side logs/traces |

---

## 3. Standard Error Codes

| Code | HTTP Status | Meaning |
|---|---|---|
| `VALIDATION_ERROR` | 400 | Request body/params failed schema validation |
| `UNAUTHENTICATED` | 401 | Missing/invalid/expired auth token |
| `FORBIDDEN` | 403 | Authenticated but lacks permission |
| `NOT_FOUND` | 404 | Resource doesn't exist or isn't visible to this tenant |
| `CONFLICT` | 409 | Duplicate/conflicting resource (e.g., email already exists) |
| `BUSINESS_RULE_VIOLATION` | 422 | Semantically invalid per business rules (e.g., can't freeze an already-frozen membership) |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Unhandled server error |
| `SERVICE_UNAVAILABLE` | 503 | Dependency (DB, payment gateway) temporarily unavailable |

New module-specific codes should extend this list (e.g., `PAYMENT_GATEWAY_ERROR`, `MEMBERSHIP_ALREADY_ACTIVE`) — document additions here as they're introduced, grouped by module.

### Module-Specific Codes

**CRM**

| Code | HTTP Status | Meaning |
|---|---|---|
| `LEAD_ALREADY_CONVERTED` | 422 | The lead has already been converted and can't be re-converted or marked lost |
| `FOLLOW_UP_ALREADY_COMPLETED` | 422 | The follow-up is already completed |

---

## 4. Backend Implementation Pattern

### Custom Exceptions (Per Module)

```python
# app/modules/membership/exceptions.py
class MembershipError(AppError):
    """Base exception for the membership module."""


class MembershipAlreadyFrozenError(MembershipError):
    code = "MEMBERSHIP_ALREADY_FROZEN"
    status_code = 409
    message = "This membership is already frozen."
```

### Centralized Exception Handler

All custom exceptions inherit from a shared `AppError` base and are caught by a single FastAPI exception handler that translates them into the standard response shape — **individual routers never manually construct error JSON.**

```python
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": request.state.request_id,
            }
        },
    )
```

- Pydantic validation errors are automatically caught and translated into `VALIDATION_ERROR` with per-field `details`.
- Unhandled exceptions are caught by a catch-all handler, logged with full stack trace server-side, and returned to the client as a generic `INTERNAL_ERROR` with **no internal details exposed**.

---

## 5. Frontend Handling Pattern

- The typed API client layer (see `CODING_STANDARDS.md`) normalizes all error responses into a shared `ApiError` type.
- UI components branch on `error.code` for specific handling (e.g., show inline field errors for `VALIDATION_ERROR`, redirect to login for `UNAUTHENTICATED`), and fall back to a generic toast/message using `error.message` for anything unrecognized.
- Never show raw `error.message` from `INTERNAL_ERROR` responses if it might contain unexpected content — always have a safe generic fallback copy for 500s.

---

## 6. Logging Errors

- Every error response includes a `request_id`, generated per-request and attached to all log lines for that request (see `OBSERVABILITY.md`).
- 4xx errors (client errors) are logged at `INFO`/`WARNING` level — expected traffic, not incidents.
- 5xx errors are logged at `ERROR` level with full stack trace and trigger alerting (Sentry) — treated as incidents requiring investigation.

---

## 7. Rules

- Never return raw exception messages or stack traces to the client.
- Never use generic `Exception` catches that swallow errors silently — always log and re-raise or translate.
- Every new module-specific exception must be documented in this file's code table when introduced.
- Error messages are written for the **end user reading them in the UI**, not for developers — keep them clear and non-technical where they'll be surfaced directly.
