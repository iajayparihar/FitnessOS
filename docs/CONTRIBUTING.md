# Contributing Guide

## Fitness Business OS

This guide covers how to contribute code to the repository — setup, workflow, review expectations. For behavioral/decision-making guidance (especially for AI-assisted contributions), see [`CLAUDE.md`](./CLAUDE.md).

---

## 1. Before You Start

Read (at least):
- [`README.md`](./README.md) — project overview & local setup
- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — how the system is structured
- [`CODING_STANDARDS.md`](./CODING_STANDARDS.md) — how code should look
- [`ROADMAP.md`](./ROADMAP.md) — what phase we're in, so your contribution is in scope

---

## 2. Local Setup

See [`README.md`](./README.md) §4 for full setup steps. Quick version:

```bash
git clone <repo-url> fitness-business-os
cd fitness-business-os
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker compose up --build
docker compose exec backend alembic upgrade head
```

---

## 3. Branching & Workflow

- `main` — production, protected, only receives merges from `develop` or hotfix branches.
- `develop` — integration branch, auto-deployed to staging.
- Feature branches: `feature/<ticket-id>-short-description`
- Bugfix branches: `fix/<ticket-id>-short-description`
- Hotfix branches (production emergencies): `hotfix/<ticket-id>-short-description`, branched from `main`.

```bash
git checkout develop
git pull
git checkout -b feature/FIT-123-lead-follow-up-reminders
```

---

## 4. Commit Messages

Follow **Conventional Commits**:

```
feat: add lead follow-up reminder scheduling
fix: correct GST calculation on partial payments
docs: update DATABASE.md with member_freezes schema
refactor: extract tenant-scoping into base repository
test: add tenant isolation tests for billing module
chore: bump SQLAlchemy to 2.0.30
```

---

## 5. Before Opening a PR — Checklist

- [ ] Code follows [`CODING_STANDARDS.md`](./CODING_STANDARDS.md)
- [ ] New/changed tables have Alembic migrations (up + down) — see [`DATABASE.md`](./DATABASE.md)
- [ ] New tenant-scoped data has isolation tests — see [`TESTING.md`](./TESTING.md), [`SECURITY.md`](./SECURITY.md)
- [ ] New endpoints follow [`API.md`](./API.md) conventions and have RBAC checks — see [`SECURITY.md`](./SECURITY.md)
- [ ] New errors use the standard shape — see [`ERROR_HANDLING.md`](./ERROR_HANDLING.md)
- [ ] New env vars added to `.env.example` and [`ENVIRONMENT.md`](./ENVIRONMENT.md)
- [ ] Relevant docs updated (`API.md`, `DATABASE.md`, `FEATURES.md`, `CHANGELOG.md`)
- [ ] Tests pass locally (`pytest`, `vitest`/`jest`)
- [ ] Linting/type-checking passes (`ruff`, `mypy`, `eslint`, `tsc`)
- [ ] No secrets, credentials, or `.env` files committed

---

## 6. Pull Request Guidelines

- Keep PRs small and focused — one feature/fix per PR where possible.
- PR description should include:
  - What changed and why
  - Which roadmap phase / module this belongs to
  - Any new env vars, migrations, or breaking changes called out explicitly
  - Screenshots for frontend/UI changes
- Link the relevant ticket/issue.
- Target `develop`, not `main` (except approved hotfixes).

---

## 7. Code Review Expectations

- At least one approving review required before merge.
- **Security-sensitive PRs** (auth, payments, permissions/RBAC, tenancy/multi-tenant isolation) require a second reviewer with security context — see [`SECURITY.md`](./SECURITY.md).
- Reviewers check for: correctness, adherence to `CODING_STANDARDS.md`, tenant isolation, test coverage, and documentation updates — not just "does it work."
- Be direct but constructive in review comments; the goal is a better product, not gatekeeping.

---

## 8. Database Migrations in PRs

- Always generate via `alembic revision --autogenerate` and **manually review** the output before committing — autogenerate misses some cases (renames, complex constraints).
- Include both `upgrade()` and `downgrade()`.
- Never edit a migration that has already been merged — create a new one.

---

## 9. Working on Documentation

Documentation changes follow the same PR process. If your code change affects the meaning of an existing doc (`API.md`, `DATABASE.md`, `ARCHITECTURE.md`, etc.), update it **in the same PR**, not as a follow-up task.

---

## 10. Reporting Issues

- Bugs: include reproduction steps, expected vs. actual behavior, environment (local/staging), and relevant `request_id`/logs if available (see [`OBSERVABILITY.md`](./OBSERVABILITY.md)).
- Security issues: **do not open a public issue.** Report privately per the process to be defined in `SECURITY.md` once a disclosure channel is set up.

---

## 11. Questions

If scope, architecture, or priority is unclear, raise it before writing code — see the "How to Approach a New Feature Request" checklist in [`CLAUDE.md`](./CLAUDE.md). It's cheaper to ask than to rebuild.
