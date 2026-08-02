# Folder Structure

## Fitness Business OS

---

## 1. Repository Root

```
fitness-business-os/
├── backend/
├── frontend/
├── infra/
├── docs/
├── scripts/
├── .github/
│   └── workflows/
├── docker-compose.yml
├── docker-compose.prod.yml
└── README.md
```

---

## 2. Backend (`/backend`)

```
backend/
├── app/
│   ├── main.py                    # FastAPI app entrypoint
│   ├── config.py                   # Settings (env-driven, Pydantic BaseSettings)
│   ├── database.py                  # SQLAlchemy engine/session setup
│   ├── dependencies.py               # Shared DI: current_user, current_tenant, db session
│   │
│   ├── core/                          # Cross-cutting concerns
│   │   ├── security.py                 # JWT, password hashing
│   │   ├── permissions.py               # RBAC permission definitions & checks
│   │   ├── tenancy.py                    # Tenant context, RLS session var setup
│   │   ├── exceptions.py                  # Base exception classes + handlers
│   │   ├── logging.py                      # Structured logging setup
│   │   └── pagination.py                    # Shared pagination utilities
│   │
│   ├── modules/                         # One folder per business module
│   │   ├── auth/
│   │   ├── tenants/
│   │   ├── users/
│   │   ├── crm/
│   │   ├── membership/
│   │   ├── attendance/
│   │   ├── billing/
│   │   ├── trainer/
│   │   ├── nutrition/
│   │   ├── inventory/
│   │   ├── expenses/
│   │   ├── dashboard/
│   │   ├── notifications/
│   │   └── ...                          # ai/, marketplace/, enterprise/ added per roadmap phase
│   │
│   ├── tasks/                             # Celery task definitions
│   │   ├── celery_app.py
│   │   └── notification_tasks.py
│   │
│   └── tests/
│       ├── conftest.py                      # Shared fixtures (test DB, tenant factories)
│       └── ...                               # Mirrors module structure
│
├── alembic/
│   ├── versions/
│   └── env.py
├── alembic.ini
├── pyproject.toml                            # Dependencies, tool config (black/ruff/mypy)
├── requirements.txt / poetry.lock
├── Dockerfile
├── .env.example
└── scripts/
    └── seed_demo.py
```

Each item under `modules/` follows the structure defined in `CODING_STANDARDS.md` (`models.py`, `schemas.py`, `service.py`, `router.py`, `dependencies.py`, `exceptions.py`, `tests/`).

---

## 3. Frontend (`/frontend`)

```
frontend/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── routes/                       # Route definitions, route guards
│   │
│   ├── app/                            # App-level setup
│   │   ├── theme.ts                       # MUI theme (supports white-label future)
│   │   ├── queryClient.ts                  # React Query setup
│   │   └── store.ts                         # Global client state (if needed)
│   │
│   ├── shared/                          # Cross-feature shared code
│   │   ├── components/                    # Buttons, tables, modals, layout
│   │   ├── hooks/
│   │   ├── utils/
│   │   ├── types/
│   │   └── api/
│   │       └── client.ts                     # Base typed API client (axios instance)
│   │
│   ├── features/                          # One folder per module, mirrors backend
│   │   ├── auth/
│   │   ├── crm/
│   │   ├── membership/
│   │   ├── attendance/
│   │   ├── billing/
│   │   ├── trainer/
│   │   ├── nutrition/
│   │   ├── inventory/
│   │   ├── expenses/
│   │   ├── dashboard/
│   │   └── notifications/
│   │
│   └── assets/
│
├── public/
├── index.html
├── vite.config.ts
├── tsconfig.json
├── package.json
├── Dockerfile
└── .env.example
```

Each item under `features/` follows the structure defined in `CODING_STANDARDS.md` (`api/`, `components/`, `hooks/`, `types.ts`, `pages/`).

---

## 4. Infra (`/infra`)

```
infra/
├── nginx/
│   ├── nginx.conf
│   └── conf.d/
├── docker/
│   └── (shared base images, if any)
├── ci/
│   └── (shared CI scripts/config beyond .github/workflows)
└── deploy/
    ├── staging/
    └── production/
```

---

## 5. Docs (`/docs`)

```
docs/
├── README.md
├── CLAUDE.md
├── PRD.md
├── ARCHITECTURE.md
├── TECH_STACK.md
├── DATABASE.md
├── API.md
├── CODING_STANDARDS.md
├── FOLDER_STRUCTURE.md
├── SECURITY.md
├── DEPLOYMENT.md
├── TESTING.md
├── FEATURES.md
├── ROADMAP.md
├── CHANGELOG.md
├── DECISIONS.md
├── ENVIRONMENT.md
├── ERROR_HANDLING.md
├── OBSERVABILITY.md
└── CONTRIBUTING.md
```

---

## 6. Scripts (`/scripts`)

```
scripts/
├── setup.sh              # One-shot local dev bootstrap
├── seed_demo_data.py       # Seed a demo tenant with realistic data
├── backup_db.sh              # Manual backup trigger
└── lint_all.sh                 # Run all linters/formatters across backend+frontend
```

---

## 7. Rules

- New business modules are added under `backend/app/modules/<name>/` and `frontend/src/features/<name>/` with matching names — no orphaned or misplaced module code.
- Nothing business-logic-related lives directly in `main.py`, `App.tsx`, or `core/`/`shared/` — those are strictly cross-cutting/infrastructure.
- Any new top-level folder at the repo root requires a note in this file explaining its purpose.
