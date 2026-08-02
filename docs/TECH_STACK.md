# Tech Stack

## Fitness Business OS

This document lists the chosen technologies, target versions, and the rationale for each. Version numbers should be reviewed and bumped periodically; update this file whenever a core dependency changes (and log the reasoning as an ADR in `DECISIONS.md` for major changes).

---

## 1. Backend

| Technology | Version (target) | Purpose |
|---|---|---|
| Python | 3.12+ | Core language |
| FastAPI | 0.11x+ | API framework — async, typed, auto OpenAPI docs |
| Pydantic | v2 | Request/response validation and settings management |
| SQLAlchemy | 2.x (async) | ORM |
| Alembic | latest | Database migrations |
| PostgreSQL | 16+ | Primary relational database |
| Redis | 7+ | Cache, session store, Celery broker/result backend |
| Celery | 5.x | Background/async task processing |
| Uvicorn / Gunicorn | latest | ASGI server (Uvicorn workers behind Gunicorn in prod) |
| python-jose / PyJWT | latest | JWT issuing/verification |
| passlib (bcrypt/argon2) | latest | Password hashing |
| pytest / pytest-asyncio | latest | Testing |
| httpx | latest | Async HTTP client (tests + outbound calls) |

**Why FastAPI over Django/Flask:** async-first performance, native Pydantic validation, automatic OpenAPI schema generation (critical for a typed frontend client and future public API/marketplace), and a clean dependency-injection model that maps well to RBAC/tenancy middleware.

---

## 2. Frontend

| Technology | Version (target) | Purpose |
|---|---|---|
| React | 18+ | UI library |
| TypeScript | 5+ | Type safety |
| Vite | latest | Build tool/dev server |
| Material UI (MUI) | v5/v6 | Component library, design system |
| React Router | v6+ | Client-side routing |
| React Query (TanStack Query) | latest | Server-state management, caching, data fetching |
| Zustand or Redux Toolkit | latest | Client-state management (decision pending — see `DECISIONS.md`) |
| React Hook Form + Zod | latest | Form handling and validation |
| Axios | latest | HTTP client |

**Why MUI:** fast to build a professional, consistent admin/dashboard UI with strong accessibility defaults, while still allowing full theming for future white-label branding.

---

## 3. Mobile (Future — Phase 14)

| Technology | Purpose |
|---|---|
| React Native (or Flutter — decision pending) | Cross-platform Member/Trainer/Owner apps |

Decision to be finalized and logged in `DECISIONS.md` before Phase 14.

---

## 4. Infrastructure & DevOps

| Technology | Purpose |
|---|---|
| Docker | Containerization |
| Docker Compose | Local development orchestration |
| Nginx | Reverse proxy, TLS termination, static asset serving |
| GitHub Actions | CI/CD pipelines |
| AWS or DigitalOcean | Cloud hosting (decision pending) |
| Terraform (future) | Infrastructure as code, once infra grows beyond manual setup |
| Sentry | Error tracking |
| Prometheus + Grafana (or hosted equivalent) | Metrics and dashboards |
| Loki / ELK / hosted logging | Centralized log aggregation |

---

## 5. Third-Party Services (To Be Finalized)

| Category | Candidates | Status |
|---|---|---|
| Payment Gateway | Razorpay, Stripe, Cashfree | Pending — India-first likely favors Razorpay/Cashfree |
| SMS | MSG91, Twilio | Pending |
| WhatsApp Business API | Interakt, Gupshup, Meta Cloud API (direct) | Pending |
| Email | SendGrid, Amazon SES, Postmark | Pending |
| Object Storage (docs, photos) | AWS S3 / DigitalOcean Spaces | Pending |
| Push Notifications | Firebase Cloud Messaging | Likely, for mobile apps |

All final selections must be logged as ADRs in `DECISIONS.md` with pricing/reliability rationale.

---

## 6. Development Tooling

| Tool | Purpose |
|---|---|
| Ruff / Black / isort | Python linting/formatting |
| mypy | Static type checking (backend) |
| ESLint / Prettier | JS/TS linting/formatting |
| pre-commit | Git hooks to enforce standards before commit |
| Postman / Insomnia (optional) | Manual API testing alongside `/docs` |

---

## 7. Versioning Policy

- Pin exact versions in `requirements.txt`/`pyproject.toml` and `package.json` (lockfiles committed).
- Review and bump dependencies monthly (security patches) with a documented review before major version upgrades.
- Breaking dependency upgrades (e.g., SQLAlchemy 1.x → 2.x, React major versions) require an ADR.
