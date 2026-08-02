# Security Requirements

## Fitness Business OS

Security is treated as a first-class, non-negotiable requirement — not something bolted on before launch. This is a multi-tenant SaaS handling PII, health/medical data, and payment information.

---

## 1. Threat Model Summary

Primary risks for this platform:
- **Cross-tenant data leakage** (Gym A seeing Gym B's members/payments) — highest priority risk given the shared-schema multi-tenant model.
- Unauthorized access to member PII (contact info, medical details, documents, photos).
- Payment data exposure / payment fraud.
- Account takeover (weak auth, token theft).
- Privilege escalation (Receptionist gaining Owner-level access).
- Abuse of public-facing endpoints (signup, check-in, marketplace) — bots, scraping, brute force.

---

## 2. Authentication

- Passwords hashed with **bcrypt or Argon2** — never plaintext, never reversible encryption.
- Minimum password policy enforced (length, complexity) at signup/reset.
- **JWT access tokens**: short-lived (~15 min), signed with a strong secret/asymmetric key, contain `user_id`, `tenant_id`, `role`, minimal claims only.
- **Refresh tokens**: long-lived, stored hashed in DB, rotated on every use, revocable (logout invalidates), one-time-use (reuse of an old refresh token revokes the whole token family — replay-attack protection).
- Email verification required before full account activation.
- Account lockout / exponential backoff after repeated failed login attempts.
- Multi-factor authentication (MFA) — planned for Owner/Admin roles, tracked in `ROADMAP.md`.

---

## 3. Authorization — RBAC

### Roles (Tenant-Scoped, Except Super Admin)
Super Admin (platform) · Gym Owner · Manager · Receptionist · Trainer · Nutritionist · Member

### Principles
- **Default-deny.** Every endpoint requires an explicit permission check; nothing is accessible by default.
- Permissions are granular and resource-action based, e.g. `members:read`, `members:write`, `payments:delete`, `reports:export`.
- Roles are collections of permissions; permissions are checked, not roles directly, so role composition can change without touching endpoint code.
- Example matrix (expand as modules are built):

| Permission | Owner | Manager | Receptionist | Trainer | Nutritionist | Member |
|---|---|---|---|---|---|---|
| `members:read` | ✓ | ✓ | ✓ | ✓ (assigned only) | ✓ (assigned only) | self only |
| `members:write` | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| `payments:read` | ✓ | ✓ | ✓ | ✗ | ✗ | self only |
| `payments:delete` | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `workouts:assign` | ✓ | ✓ | ✗ | ✓ | ✗ | ✗ |
| `subscription:change` | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `tenant_settings:write` | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |

- Permission checks are implemented as FastAPI dependencies (`Depends(require_permission("members:write"))`), never inline `if` checks scattered through business logic.
- Frontend UI hides/disables actions the user lacks permission for, but this is **UX only** — the backend is the actual enforcement point, always.

---

## 4. Multi-Tenant Isolation

- Every tenant-scoped query is automatically filtered by `tenant_id`, enforced at both the ORM layer and via PostgreSQL Row-Level Security (defense in depth) — see `DATABASE.md`.
- Cross-tenant resource access attempts return `404`, not `403` (no existence leakage).
- Tenant isolation is covered by dedicated automated tests for every module (see `TESTING.md`) — this is treated as a security control, not just a functional one.
- Super Admin cross-tenant access is explicit, logged, and audited (see Audit Logging below).

---

## 5. Data Protection

- **In transit:** TLS everywhere (enforced via Nginx, HSTS enabled).
- **At rest:** database encryption at rest (managed Postgres default), encrypted object storage for documents/photos.
- **Sensitive fields** (medical details, payment identifiers) are minimized in logs and never returned in error messages.
- **PII minimization:** only collect what's needed for the stated feature; medical/emergency contact info access restricted by RBAC beyond general member read.
- File uploads (documents, photos) validated for type/size, scanned where feasible, stored in access-controlled object storage with signed, time-limited URLs — never public buckets.

---

## 6. Payment Security

- No raw card data ever touches our servers — payment gateway hosted fields/tokenization only (PCI SAQ-A scope target).
- Payment gateway webhooks verified via provider signature.
- Refunds, discounts, and payment deletions restricted to Owner-level permission and logged in the audit trail.

---

## 7. Input Validation & Injection Protection

- All input validated via Pydantic schemas — no unvalidated data reaches the service layer.
- SQLAlchemy ORM/parameterized queries only — no string-concatenated SQL.
- Output encoding on the frontend prevents XSS; React's default escaping relied upon, `dangerouslySetInnerHTML` banned except for explicitly sanitized, reviewed cases.
- CSRF: mitigated by using JWT bearer tokens (not cookies) for API auth where practical; if cookies are used for refresh tokens, `SameSite=Strict`/`Lax` + CSRF tokens required.

---

## 8. Rate Limiting & Abuse Prevention

- Rate limiting per IP and per authenticated user/tenant at the gateway layer, stricter on auth endpoints (`/login`, `/forgot-password`).
- CAPTCHA or equivalent on public signup if abuse is observed.
- Audit alerts on anomalous patterns (e.g., mass export attempts, repeated 403s).

---

## 9. Audit Logging

- All security-sensitive actions logged with actor, tenant, timestamp, and action: login, logout, permission changes, payment deletions/refunds, data exports, Super Admin cross-tenant access.
- Audit logs are immutable (append-only) and retained per the retention policy (see below).
- Full observability/log pipeline details in `OBSERVABILITY.md`.

---

## 10. Secrets Management

- No secrets in source control, ever.
- All secrets via environment variables (see `ENVIRONMENT.md`), sourced from a secrets manager in production (e.g., AWS Secrets Manager / DigitalOcean equivalent), not plain `.env` files on servers.
- Secrets rotated periodically; immediate rotation on suspected compromise.

---

## 11. Dependency & Infrastructure Security

- Automated dependency vulnerability scanning in CI (e.g., `pip-audit`, `npm audit`, GitHub Dependabot).
- Base Docker images kept minimal and patched regularly.
- Principle of least privilege for all infra service accounts/IAM roles.

---

## 12. Compliance & Data Retention

- Data retention policy to be finalized (relevant to Indian data protection law — DPDP Act — and financial record retention for GST/billing data). Tracked as an open item; log the final policy as an ADR in `DECISIONS.md`.
- Tenant data export and deletion ("right to be forgotten" / offboarding) must be supported before general availability launch.

---

## 13. Incident Response (Baseline)

- Any suspected data breach or cross-tenant leak is treated as Sev-1: immediate investigation, affected tenants notified per legal requirements, root cause logged as a postmortem in `DECISIONS.md` or a dedicated incidents log.
- Security-sensitive PRs (auth, payments, permissions, tenancy) require a second reviewer with security context, per `CONTRIBUTING.md`.
