# API Standards & Contracts

## Fitness Business OS

---

## 1. General Principles

- **API-first**: the API is a first-class product surface (used by web, mobile apps, and future public/marketplace API), not an afterthought to the frontend.
- RESTful JSON over HTTPS.
- Versioned from day one: `/api/v1/...`.
- Auto-documented via FastAPI's OpenAPI/Swagger at `/docs` and `/redoc`.
- Consistent, predictable shapes — a frontend or third-party developer should be able to guess the response format of an endpoint they haven't seen yet.

---

## 2. Base URL & Versioning

```
https://api.fitnessbusinessos.com/api/v1/
```

- Breaking changes require a new version (`/api/v2/`), never a silent breaking change to `v1`.
- Non-breaking additions (new optional fields, new endpoints) do not require a version bump.

---

## 3. Authentication

- Bearer JWT in the `Authorization` header: `Authorization: Bearer <access_token>`.
- Access tokens: short-lived (e.g., 15 min). Refresh tokens: long-lived, rotated on use, stored hashed server-side.

```
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
POST /api/v1/auth/register        (tenant/owner signup)
POST /api/v1/auth/verify-email
POST /api/v1/auth/forgot-password
POST /api/v1/auth/reset-password
```

---

## 4. Resource Naming

- Plural nouns, `kebab-case` for multi-word resources: `/members`, `/lead-follow-ups`, `/membership-plans`.
- Nesting only where the child is meaningless without the parent: `/members/{member_id}/documents`.
- Actions that don't fit CRUD use a verb sub-resource: `POST /members/{id}/freeze`, `POST /invoices/{id}/refund`.

---

## 5. Standard Endpoint Shape (Per Resource)

```
GET    /api/v1/members              # list (paginated, filterable, sortable)
POST   /api/v1/members              # create
GET    /api/v1/members/{id}         # retrieve
PATCH  /api/v1/members/{id}         # partial update
DELETE /api/v1/members/{id}         # soft delete
```

- `PATCH` preferred over `PUT` (partial updates are the norm).
- `DELETE` triggers a soft delete (`deleted_at`) per `DATABASE.md`, not a hard delete, unless explicitly documented otherwise for a specific resource.

---

## 6. Request Conventions

- All request bodies are JSON, validated via Pydantic schemas.
- Every list endpoint supports:
  - **Pagination:** `?page=1&page_size=20` (or cursor-based for high-volume tables — decide per resource, document the choice)
  - **Filtering:** `?status=active&trainer_id=...`
  - **Sorting:** `?sort=-created_at` (`-` prefix = descending)
  - **Search:** `?q=...` where free-text search is meaningful

---

## 7. Response Conventions

### Single resource
```json
{
  "data": {
    "id": "uuid",
    "...": "..."
  }
}
```

### List / paginated resource
```json
{
  "data": [ { "...": "..." } ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total_count": 137,
    "total_pages": 7
  }
}
```

### Error response — see full spec in `ERROR_HANDLING.md`
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "One or more fields are invalid.",
    "details": [
      { "field": "email", "issue": "Invalid email format." }
    ],
    "request_id": "req_01HXYZ..."
  }
}
```

---

## 8. HTTP Status Codes

| Code | Meaning |
|---|---|
| 200 | Success (GET, PATCH, action endpoints) |
| 201 | Created (POST) |
| 204 | Success, no body (DELETE) |
| 400 | Bad request / validation error |
| 401 | Unauthenticated |
| 403 | Authenticated but not authorized (RBAC) |
| 404 | Resource not found (or not visible to this tenant) |
| 409 | Conflict (e.g., duplicate email, double booking) |
| 422 | Semantic validation error (well-formed but business-rule invalid) |
| 429 | Rate limited |
| 500 | Unhandled server error |

**Tenant isolation rule:** if a resource exists but belongs to a different tenant, the API returns `404`, never `403` — to avoid leaking existence of cross-tenant data.

---

## 9. Authorization (RBAC) Per Endpoint

Every endpoint declares its required permission(s) explicitly via a FastAPI dependency, e.g.:

```python
@router.delete("/payments/{payment_id}")
async def delete_payment(
    payment_id: UUID,
    _: User = Depends(require_permission("payments:delete")),
):
    ...
```

No endpoint is permission-less by default except explicitly public ones (auth, health check). See `SECURITY.md` for the full permission matrix.

---

## 10. Idempotency

- All state-changing endpoints that may be retried by clients (payments, notifications) should accept an optional `Idempotency-Key` header to prevent duplicate side effects (e.g., double-charging).

---

## 11. Rate Limiting

- Applied per tenant and per IP at the Nginx/API-gateway layer.
- Sensible defaults (e.g., 100 req/min per user) with stricter limits on auth endpoints to prevent brute force.
- Documented per-endpoint exceptions (e.g., higher limits for dashboard polling) as they're introduced.

---

## 12. File Uploads

- Uploaded via pre-signed URLs to object storage (S3/Spaces) where possible, rather than proxying large files through the API.
- Endpoints return a pre-signed upload URL; client uploads directly; a confirmation callback/endpoint registers the file metadata against the resource (e.g., member document, progress photo).

---

## 13. Webhooks (Future — Payment Gateway, WhatsApp, etc.)

- Inbound webhooks verified via provider signature before processing.
- All webhook events logged and processed idempotently (safe to receive the same event twice).

---

## 14. Public/Partner API (Future — Enterprise Phase)

- Will reuse the same `/api/v1/` surface with API-key-based auth (in addition to JWT for first-party apps) and per-key rate limiting/scoping.
- Full spec to be added when Phase 17 (Enterprise) begins.

---

## 15. Documentation Requirement

Every new endpoint must have:
- A clear FastAPI route docstring (renders in `/docs`)
- Pydantic request/response models with field descriptions
- An entry (if it introduces a new resource) added to this file's module-by-module endpoint index (to be expanded as modules are built)
