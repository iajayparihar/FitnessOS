# Coding Standards

## Fitness Business OS

---

## 1. General Philosophy

- Optimize for **readability and maintainability** over cleverness.
- Explicit is better than implicit. Boring, obvious code is preferred over clever one-liners.
- Every module should be understandable by a new engineer in under 30 minutes.
- Consistency across the codebase matters more than any individual developer's personal style preference.

---

## 2. Backend (Python / FastAPI)

### Formatting & Linting
- **Black** for formatting (line length 88 or 100 — pick one, enforce via config).
- **Ruff** for linting (replaces flake8/isort in one tool).
- **mypy** for static type checking — all new code must be fully typed; no untyped `def`.
- Enforced via **pre-commit** hooks and CI — no PR merges with lint/type failures.

### Naming
- `snake_case` for variables, functions, modules.
- `PascalCase` for classes (models, schemas, services).
- Constants in `UPPER_SNAKE_CASE`.
- Boolean variables/functions read as a question: `is_active`, `has_permission(...)`.

### Structure Per Module
```
app/modules/<module_name>/
├── __init__.py
├── models.py         # SQLAlchemy models
├── schemas.py         # Pydantic request/response schemas
├── service.py          # Business logic
├── router.py            # FastAPI routes (thin)
├── dependencies.py      # Module-specific DI (permissions, lookups)
├── exceptions.py         # Module-specific exceptions
└── tests/
    ├── test_service.py
    └── test_router.py
```

### Rules
- **Routers are thin.** No business logic, no direct DB queries in routers — only request/response handling and calling the service layer.
- **Services own business logic.** All validation beyond basic schema shape, all tenant-scoping enforcement, all orchestration.
- **No raw SQL** except in rare, documented, reviewed performance-critical paths (goes through the repository layer, and even then, uses SQLAlchemy Core, not string concatenation).
- **Every service method that touches tenant data requires an explicit `tenant_id` parameter** — never inferred from a global/thread-local without it being visible in the function signature (makes tenant scoping auditable at a glance).
- Use **dependency injection** (FastAPI `Depends`) for auth, current user, current tenant, and permission checks — not manual header parsing scattered around.
- Custom exceptions per module (e.g., `MemberNotFoundError`), caught centrally and translated to the standard error response shape (see `ERROR_HANDLING.md`).
- Docstrings required on all public service methods and route handlers — explain *why*, not just *what*, when the code isn't self-evident.
- Avoid deep nesting — prefer early returns / guard clauses.
Docstring Rules:
- Use Google-style docstrings.
- Wrap every docstring line to a maximum of 88 characters.
- Keep the summary on one short line.
- Wrap descriptions, Args, Returns, Raises, and Examples to 88 characters.
- Never produce docstrings with lines longer than 88 characters.
---

## 3. Frontend (React / TypeScript)

### Formatting & Linting
- **Prettier** for formatting.
- **ESLint** (with TypeScript + React + accessibility plugins) for linting.
- Enforced via pre-commit and CI.

### Naming
- Components: `PascalCase` (`MemberListPage.tsx`).
- Hooks: `camelCase`, prefixed `use` (`useMembers.ts`).
- Files/folders otherwise `kebab-case` or `camelCase` — pick one and stay consistent (recommend `kebab-case` for files, `PascalCase` for component files).

### Structure (Feature-Folder, Mirrors Backend Modules)
```
src/features/members/
├── api/            # typed API calls for this feature
├── components/       # feature-specific components
├── hooks/              # feature-specific hooks
├── types.ts              # feature-specific types
└── pages/                 # route-level pages
```

### Rules
- **No `any`.** Use proper types or `unknown` with narrowing.
- All API calls go through a typed client layer (`api/`), never raw `fetch`/`axios` calls inside components.
- Server state (data from the API) managed via React Query — not duplicated into local component state unless genuinely local/derived.
- Forms use React Hook Form + Zod schemas shared/mirrored with backend Pydantic validation rules where practical.
- Components should be small and single-purpose; extract subcomponents rather than growing one file past ~200–300 lines.
- No inline styles except for truly one-off, dynamic cases — use MUI's `sx` prop or theme-based styling for consistency.
- Role/permission-gated UI elements use a shared `<RequirePermission>` wrapper or hook — not ad hoc `if (user.role === 'admin')` scattered around.

---

## 4. Git & Version Control

- **Branching:** `main` (production), `develop` (integration), `feature/<ticket-id>-short-description`.
- **Commit messages:** Conventional Commits style — `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`.
- **PRs:** small, focused, reviewed before merge. Include a summary of what/why, link to the relevant roadmap phase or issue.
- No direct commits to `main`.

---

## 5. Comments & Documentation

- Comment *why*, not *what* — the code should explain what it does; comments explain non-obvious reasoning, tradeoffs, or business rules.
- Every module gets a short docstring/README explaining its purpose if it's non-obvious from the name.
- TODOs must reference a ticket/issue, not float unowned: `# TODO(FIT-123): handle partial refund edge case`.

---

## 6. Testing Expectations

Covered fully in `TESTING.md`. Summary: every service method has unit tests; every endpoint has at least one integration test including a tenant-isolation test; no PR merges with failing or skipped tests without justification.

---

## 7. Security-Sensitive Code

- Never log secrets, tokens, passwords, or full payment details.
- Never hardcode credentials — always via environment variables (`ENVIRONMENT.md`).
- Any code touching auth, payments, or permissions requires an additional reviewer familiar with `SECURITY.md`.

---

## 8. Performance Basics

- N+1 queries are a bug — use eager loading (`selectinload`/`joinedload`) deliberately, not by accident.
- Paginate everything that can grow unbounded.
- Cache expensive, slow-changing aggregates (e.g., dashboard KPIs) in Redis with a sane TTL rather than recomputing on every request.
