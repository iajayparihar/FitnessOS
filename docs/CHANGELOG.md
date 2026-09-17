# Changelog

## Fitness Business OS

All notable changes to this project are documented here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/), and this project intends to follow [Semantic Versioning](https://semver.org/) once versioned releases begin.

Categories used: `Added`, `Changed`, `Fixed`, `Removed`, `Security`, `Docs`.

---

## [Unreleased]

### Added
- Clerk-based authentication: backend verifies Clerk session JWTs and provisions users just-in-time; `POST /auth/onboarding` (create org + become owner) and `POST /auth/invites/accept` (join via invite) endpoints.
- In-app API rate limiting (`slowapi`), with a tighter limit on onboarding/invite endpoints.
- Standard error envelope (`{"error": {code, message, details, request_id}}`) via centralized exception handlers, plus a request-id middleware that sets `X-Request-ID` on every response.
- CRM module (Phase 4): lead sources, leads (create, list with filters + pagination, get, update, convert, mark-lost), and follow-ups (schedule, list, complete). New `crm:read` permission.
- Frontend testing console (`frontend/`): Vite + React + TS + MUI app that exercises login/onboarding/CRM/RBAC with a live request/response panel. Uses Clerk when `VITE_CLERK_PUBLISHABLE_KEY` is set, otherwise a dev login.
- Local dev auth issuer (`POST /auth/dev/login`, gated by `DEV_AUTH_ENABLED`) that mints RS256 tokens verified through the normal Clerk path — lets the stack be tested without a Clerk account.
- CORS support (`CORS_ORIGINS`) and a working `docker-compose` stack (Postgres + backend-with-migrations + frontend) for one-command local runs.

### Changed
- Authentication delegated to Clerk as the identity provider (see ADR-0006). RBAC and multi-tenant isolation are unchanged.
- Backend `Dockerfile` rewritten to use `uv` and run migrations on start; root `docker-compose.yml` now defines the full stack.
- Existing auth/RBAC/tenant endpoints now emit the standard error envelope automatically (HTTPExceptions are translated centrally — no router changes).

### Removed
- Custom self-issued JWT/refresh-token auth, PBKDF2 password hashing, password login/register/refresh/logout endpoints, and the `sessions` table (password reset, email verification, MFA, and login lockout are now handled by Clerk).

### Security
- Login-side throttling/lockout handled by Clerk; our API adds per-IP rate limiting.

### Docs
- Added full project documentation set: `README.md`, `CLAUDE.md`, `PRD.md`, `ARCHITECTURE.md`, `TECH_STACK.md`, `DATABASE.md`, `API.md`, `CODING_STANDARDS.md`, `FOLDER_STRUCTURE.md`, `SECURITY.md`, `DEPLOYMENT.md`, `TESTING.md`, `FEATURES.md`, `ROADMAP.md`, `CHANGELOG.md`, `DECISIONS.md`, `ENVIRONMENT.md`, `ERROR_HANDLING.md`, `OBSERVABILITY.md`, `CONTRIBUTING.md`.
- Updated `SECURITY.md`, `ENVIRONMENT.md`, and added ADR-0006 for the Clerk auth model.
- Added CRM error codes to `ERROR_HANDLING.md`; updated `FEATURES.md` for the CRM endpoints and the error/request-id foundation.

---

## How to Use This File

- Every merged PR that changes behavior (not pure refactors/docs-only, though docs changes can be noted too) should add an entry under `[Unreleased]`.
- When a release is cut, `[Unreleased]` is renamed to the version number and date, and a fresh empty `[Unreleased]` section is added above it.
- Entries should be user/business-facing where possible ("Added member freeze functionality"), not raw commit messages ("fixed bug in service.py").

### Template for a New Release

```markdown
## [0.1.0] - YYYY-MM-DD

### Added
- ...

### Changed
- ...

### Fixed
- ...

### Security
- ...
```

---

## Versioning Policy

- Pre-1.0: `0.x.y` — breaking changes possible between minor versions while the platform stabilizes.
- Post-1.0 (first paying customers live): standard SemVer — breaking API changes require a major version bump and a new `/api/v2/` surface (see `API.md`).
