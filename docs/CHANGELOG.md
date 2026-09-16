# Changelog

## Fitness Business OS

All notable changes to this project are documented here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/), and this project intends to follow [Semantic Versioning](https://semver.org/) once versioned releases begin.

Categories used: `Added`, `Changed`, `Fixed`, `Removed`, `Security`, `Docs`.

---

## [Unreleased]

### Added
- Clerk-based authentication: backend verifies Clerk session JWTs and provisions users just-in-time; `POST /auth/onboarding` (create org + become owner) and `POST /auth/invites/accept` (join via invite) endpoints.
- In-app API rate limiting (`slowapi`), with a tighter limit on onboarding/invite endpoints.

### Changed
- Authentication delegated to Clerk as the identity provider (see ADR-0006). RBAC and multi-tenant isolation are unchanged.

### Removed
- Custom self-issued JWT/refresh-token auth, PBKDF2 password hashing, password login/register/refresh/logout endpoints, and the `sessions` table (password reset, email verification, MFA, and login lockout are now handled by Clerk).

### Security
- Login-side throttling/lockout handled by Clerk; our API adds per-IP rate limiting.

### Docs
- Added full project documentation set: `README.md`, `CLAUDE.md`, `PRD.md`, `ARCHITECTURE.md`, `TECH_STACK.md`, `DATABASE.md`, `API.md`, `CODING_STANDARDS.md`, `FOLDER_STRUCTURE.md`, `SECURITY.md`, `DEPLOYMENT.md`, `TESTING.md`, `FEATURES.md`, `ROADMAP.md`, `CHANGELOG.md`, `DECISIONS.md`, `ENVIRONMENT.md`, `ERROR_HANDLING.md`, `OBSERVABILITY.md`, `CONTRIBUTING.md`.
- Updated `SECURITY.md`, `ENVIRONMENT.md`, and added ADR-0006 for the Clerk auth model.

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
