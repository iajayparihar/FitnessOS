# Fitness Business OS

> **Not a Gym Management Software. A Fitness Business Operating System.**
> Think "Shopify for Fitness Businesses."

Fitness Business OS is a cloud-based, multi-tenant SaaS platform that helps gym owners, studio owners, and fitness professionals run and grow their entire business from a single platform — leads, memberships, billing, attendance, trainers, nutrition, inventory, expenses, analytics, marketing, and more.

This is being built as a **production-grade SaaS company**, not a portfolio project. Every decision should optimize for scalability, security, multi-tenancy, and long-term maintainability over the next 5–10 years.

---

## 1. Vision

Help fitness business owners:

- Increase revenue
- Increase member retention
- Reduce manual work
- Automate operations
- Improve trainer productivity
- Improve customer experience
- Get real business intelligence
- Scale to multiple branches

See [`PRD.md`](./PRD.md) for the full product vision and [`ROADMAP.md`](./ROADMAP.md) for the phased build plan.

---

## 2. Tech Stack (Summary)

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python), SQLAlchemy, Alembic |
| Database | PostgreSQL |
| Cache / Queue | Redis, Celery |
| Frontend | React, TypeScript, Material UI |
| Infra | Docker, Docker Compose, Nginx, GitHub Actions |
| Cloud | AWS or DigitalOcean |
| Architecture | Modular Monolith (not microservices, initially) |

Full details, versions, and rationale: [`TECH_STACK.md`](./TECH_STACK.md).

---

## 3. Repository Structure

See [`FOLDER_STRUCTURE.md`](./FOLDER_STRUCTURE.md) for the full layout. High level:

```
fitness-business-os/
├── backend/          # FastAPI modular monolith
├── frontend/          # React + TypeScript SPA
├── infra/             # Docker, nginx, CI/CD, deployment configs
├── docs/               # All project documentation (this folder)
└── scripts/            # Dev / ops helper scripts
```

---

## 4. Getting Started (Local Development)

### Prerequisites

- Docker & Docker Compose
- Python 3.12+
- Node.js 20+ (LTS)
- Make (optional, for shortcuts)

### Setup

```bash
# 1. Clone the repo
git clone <repo-url> fitness-business-os
cd fitness-business-os

# 2. Copy environment templates
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# 3. Start the full stack (Postgres, Redis, backend, frontend, worker)
docker compose up --build

# 4. Run database migrations
docker compose exec backend alembic upgrade head

# 5. (Optional) Seed demo data
docker compose exec backend python -m scripts.seed_demo
```

- Backend API: `http://localhost:8000`
- API Docs (Swagger): `http://localhost:8000/docs`
- Frontend: `http://localhost:5173`

See [`ENVIRONMENT.md`](./ENVIRONMENT.md) for all required environment variables and [`DEPLOYMENT.md`](./DEPLOYMENT.md) for staging/production setup.

---

## 5. Documentation Map

| Document | Purpose |
|---|---|
| [`CLAUDE.md`](./CLAUDE.md) | How Claude (or any AI assistant) should work on this repo |
| [`PRD.md`](./PRD.md) | Product Requirements Document |
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | System architecture |
| [`TECH_STACK.md`](./TECH_STACK.md) | Technologies and versions |
| [`DATABASE.md`](./DATABASE.md) | Schema and DB conventions |
| [`API.md`](./API.md) | API contracts and standards |
| [`CODING_STANDARDS.md`](./CODING_STANDARDS.md) | Coding style and best practices |
| [`FOLDER_STRUCTURE.md`](./FOLDER_STRUCTURE.md) | Directory organization |
| [`SECURITY.md`](./SECURITY.md) | Security requirements |
| [`DEPLOYMENT.md`](./DEPLOYMENT.md) | Deployment instructions |
| [`TESTING.md`](./TESTING.md) | Testing strategy |
| [`FEATURES.md`](./FEATURES.md) | Feature list and status |
| [`ROADMAP.md`](./ROADMAP.md) | Planned work by phase |
| [`CHANGELOG.md`](./CHANGELOG.md) | Release history |
| [`DECISIONS.md`](./DECISIONS.md) | Architecture Decision Records (ADR) |
| [`ENVIRONMENT.md`](./ENVIRONMENT.md) | Environment variables |
| [`ERROR_HANDLING.md`](./ERROR_HANDLING.md) | Error response standards |
| [`OBSERVABILITY.md`](./OBSERVABILITY.md) | Logging, metrics, tracing |
| [`CONTRIBUTING.md`](./CONTRIBUTING.md) | Contribution workflow |

---

## 6. Core Principle

Every feature must answer **"What problem does the business owner have?"** — not "what feature should we build?"

A feature only belongs in scope if it increases at least one of: **Revenue, Retention, Automation, Productivity, or Customer Satisfaction.**

---

## 7. License & Ownership

Proprietary — All rights reserved. This is a commercial SaaS product under active development.
