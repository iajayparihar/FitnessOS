# Fitness Business OS

A modern, multi-tenant fitness business management platform built with FastAPI, React, and PostgreSQL.

## Table of Contents

- [Project Overview](#project-overview)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Local Development Setup](#local-development-setup)
- [Database Migrations](#database-migrations)
- [Running the Application](#running-the-application)
- [Testing](#testing)
- [Docker & Deployment](#docker--deployment)
- [Documentation](#documentation)
- [Contributing](#contributing)

---

## Project Overview

**Fitness Business OS** is a comprehensive SaaS platform for managing fitness businesses, including:

- **CRM**: Lead management and customer relationship management
- **Membership**: Membership plans, subscriptions, and member lifecycle management
- **Attendance**: QR code check-in and attendance tracking
- **Billing**: Invoicing, payments, discounts, and financial management
- **Trainer**: Workout templates, assignments, and progress tracking
- **Nutrition**: Meal plans and body measurements
- **Inventory**: Stock management and purchase orders
- **Notifications**: Multi-channel notifications (Email, SMS, WhatsApp)
- **RBAC**: Role-based access control (Owner, Manager, Receptionist, Trainer)

### Key Features

- **Multi-tenant Architecture**: Complete tenant isolation at application and database levels
- **Async-first Backend**: Built on FastAPI with async/await for high performance
- **Type-Safe**: Full TypeScript frontend and typed Python backend with Pydantic
- **Professional UI**: React + Material UI for a polished admin dashboard
- **API-Driven**: RESTful API with automatic OpenAPI documentation
- **Scalable**: Redis caching, Celery background tasks, connection pooling

---

## Tech Stack

### Backend
- **Python 3.12+** with **FastAPI** web framework
- **SQLAlchemy 2.x** (async ORM) + **PostgreSQL 16+** database
- **Alembic** for database migrations
- **Pydantic v2** for data validation and settings management
- **Celery** + **Redis** for background job processing
- **Pytest** for testing (unit, integration, tenant isolation tests)

### Frontend
- **React 18+** with **TypeScript 5+**
- **Vite** for fast bundling and dev experience
- **Material UI (MUI)** for component library and design system
- **React Query** for server state management
- **React Hook Form** + **Zod** for form handling

### Infrastructure
- **Docker** & **Docker Compose** for containerization
- **Nginx** for reverse proxy and TLS termination
- **GitHub Actions** for CI/CD
- **AWS / DigitalOcean** (deployment target, see [DEPLOYMENT.md](docs/DEPLOYMENT.md))

For detailed tech decisions and rationale, see [TECH_STACK.md](docs/TECH_STACK.md).

---

## Quick Start

### Prerequisites

- **Python 3.12+** (tested on 3.12.11)
- **PostgreSQL 16+** running locally or via Docker
- **Redis 7+** for caching and Celery (optional for local development, required for production)
- **uv** — fast Python package manager (recommended; see [uv documentation](https://docs.astral.sh/uv/))
- **Node.js 18+** and **npm** or **pnpm** (for frontend, Phase 2+)

### Setup Backend (5 minutes)

```bash
# Clone the repository
git clone <repo-url>
cd Fitness_business_os

# Create and activate Python environment (uv will do this automatically)
# Install dependencies using uv
uv sync

# Copy environment file and update with your settings
cp backend/.env.example backend/.env

# Start PostgreSQL (if using Docker)
docker run -d \
  -e POSTGRES_USER=fitness_user \
  -e POSTGRES_PASSWORD=123 \
  -e POSTGRES_DB=fitness_db \
  -p 5432:5432 \
  postgres:16

# Apply database migrations
cd backend
uv run python -m alembic -c alembic.ini upgrade head
cd ..

# Seed demo data (optional)
cd backend
uv run python scripts/seed_demo.py
cd ..

# Start the backend development server
uv run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000` with interactive docs at `http://localhost:8000/docs`.

---

## Local Development Setup

### 1. Clone & Install

```bash
git clone <repo-url>
cd Fitness_business_os

# Install all project dependencies with uv
uv sync

# Create .env files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env  # if frontend exists
```

### 2. Environment Configuration

See [ENVIRONMENT.md](docs/ENVIRONMENT.md) for a complete list of environment variables.

**Minimum required for local development** (`backend/.env`):

```env
# App
APP_ENV=local
APP_DEBUG=true
APP_SECRET_KEY=your-secret-key-here-change-in-production

# Database (example with Docker PostgreSQL)
DATABASE_URL=postgresql+asyncpg://fitness_user:123@localhost:5432/fitness_db

# Redis (if running Celery locally)
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1

# JWT
JWT_SECRET_KEY=your-jwt-secret-here-change-in-production
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30
```

### 3. Start Services

#### PostgreSQL

```bash
# Option 1: Docker
docker run -d \
  --name fitness_postgres \
  -e POSTGRES_USER=fitness_user \
  -e POSTGRES_PASSWORD=123 \
  -e POSTGRES_DB=fitness_db \
  -p 5432:5432 \
  postgres:16

# Option 2: Using docker-compose
docker-compose up -d postgres
```

#### Redis (for Celery)

```bash
# Option 1: Docker
docker run -d \
  --name fitness_redis \
  -p 6379:6379 \
  redis:7

# Option 2: Using docker-compose
docker-compose up -d redis
```

---

## Database Migrations

### Understanding Migrations

Database migrations manage schema changes safely and reversibly using **Alembic** (SQLAlchemy migration tool). Every migration:

- Has an `upgrade()` function (apply the change) and `downgrade()` function (revert it)
- Can be reviewed before application
- Must be backward-compatible with the previous app version (for zero-downtime deploys)

For detailed database conventions, see [DATABASE.md](docs/DATABASE.md).

### Common Migration Tasks

#### View current database revision

```bash
cd backend
uv run python -m alembic -c alembic.ini current
```

#### View migration history

```bash
cd backend
uv run python -m alembic -c alembic.ini history
```

#### Apply all pending migrations

```bash
cd backend
uv run python -m alembic -c alembic.ini upgrade head
```

#### Apply specific number of migrations

```bash
cd backend
# Apply next 2 migrations
uv run python -m alembic -c alembic.ini upgrade +2

# Apply to a specific revision
uv run python -m alembic -c alembic.ini upgrade <revision_id>
```

#### Create a new migration (automatically generated)

After modifying models in `backend/app/`, generate a migration:

```bash
cd backend
uv run python -m alembic -c alembic.ini revision --autogenerate -m "add member_freezes table"

# Review the generated file: backend/alembic/versions/<revision>.py
# Edit if needed for data migrations or non-standard ORM changes

# Apply it
uv run python -m alembic -c alembic.ini upgrade head
```

#### Rollback one migration

```bash
cd backend
uv run python -m alembic -c alembic.ini downgrade -1
```

### Migration Best Practices

1. **Always review auto-generated migrations** — Alembic is smart but not perfect
2. **Test both `upgrade` and `downgrade`** before committing
3. **Keep migrations small and focused** — one feature per migration
4. **Never edit a migration after it's been deployed** — create a fix-up migration instead
5. **Ensure migrations are backward-compatible** for rolling deploys

See [DEPLOYMENT.md](docs/DEPLOYMENT.md#4-database-migrations-in-production) for production migration strategy.

---

## Running the Application

### Backend Only

```bash
cd backend
uv run python -m alembic -c alembic.ini upgrade head  # Apply migrations
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Access API docs at: `http://localhost:8000/docs` (Swagger UI)

### Backend + Frontend (Docker Compose)

```bash
# Build and start all services
docker-compose up --build

# In another terminal, apply migrations
docker-compose exec backend uv run python -m alembic -c alembic.ini upgrade head

# Optional: Seed demo data
docker-compose exec backend uv run python scripts/seed_demo.py
```

**Services:**
- Backend API: `http://localhost:8000`
- Frontend: `http://localhost:5173` (Vite dev server)
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

### Running Celery Workers (Background Tasks)

In a separate terminal:

```bash
cd backend
uv run celery -A app.tasks.celery_app worker -l info
```

For monitoring:

```bash
cd backend
uv run celery -A app.tasks.celery_app events
```

---

## Testing

### Backend Testing

We use **pytest** for comprehensive testing. See [TESTING.md](docs/TESTING.md) for the full testing philosophy and strategy.

#### Run all tests

```bash
cd backend
uv run pytest

# With verbose output
uv run pytest -v

# With coverage report
uv run pytest --cov=app --cov-report=html
```

#### Run specific test file

```bash
cd backend
uv run pytest tests/test_auth/test_router.py
```

#### Run specific test function

```bash
cd backend
uv run pytest tests/test_auth/test_router.py::test_login_success -v
```

#### Run tests matching a pattern

```bash
cd backend
uv run pytest -k "tenant_isolation" -v
```

#### Run with live database output

```bash
cd backend
uv run pytest -s  # Captures and prints stdout/stderr
```

### Test Categories

1. **Unit Tests** — Service logic, utilities, validators (fast, mocked dependencies)
2. **Integration Tests** — API endpoints with a real test database
3. **Tenant Isolation Tests** — Verify Tenant A cannot access Tenant B's data (security-critical)
4. **RBAC Tests** — Verify permission gates work (Receptionist cannot delete payments, etc.)

### Test Structure

```
backend/tests/
├── conftest.py                          # Shared fixtures (test DB, client, factories)
├── factories/                           # Test data factories
│   ├── user_factory.py
│   ├── tenant_factory.py
│   └── member_factory.py
├── test_auth/
│   ├── test_router.py                   # API endpoint tests
│   └── test_service.py                  # Service logic tests
├── test_billing/
│   ├── test_router.py
│   ├── test_service.py
│   └── test_tenant_isolation.py         # Mandatory isolation test per module
└── ... (other modules)
```

### Coverage Target

- Minimum **80%** coverage on service-layer code (guidelines; critical paths like billing/auth should approach 100%)
- Coverage reports: `htmlcov/index.html` after running with `--cov-report=html`

---

## Docker & Deployment

### Local Development with Docker Compose

```bash
# Start all services (backend, frontend, postgres, redis)
docker-compose up --build

# Run migrations
docker-compose exec backend uv run python -m alembic -c alembic.ini upgrade head

# Seed demo data
docker-compose exec backend uv run python scripts/seed_demo.py

# Run tests
docker-compose exec backend uv run pytest

# Stop services
docker-compose down

# Remove volumes (reset database)
docker-compose down -v
```

### Production Deployment

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for:

- Deployment topology (load balancer, Nginx, containerized services)
- CI/CD pipeline setup (GitHub Actions)
- Database backup & recovery procedures
- Zero-downtime rolling deploys
- Rollback procedures
- Post-deploy monitoring

Quick production checklist:
1. All secrets injected from secrets manager (not in code)
2. Database migrations applied with approval gate
3. Health check endpoints verified (`GET /health`)
4. Rollback plan documented for risky migrations
5. Backups tested and restorable

---

## Documentation

Comprehensive documentation located in `docs/` folder:

| Document | Purpose |
|---|---|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, component interactions |
| [API.md](docs/API.md) | API endpoints, request/response schemas (auto-generated from FastAPI) |
| [DATABASE.md](docs/DATABASE.md) | Schema design, naming conventions, multi-tenancy model |
| [ENVIRONMENT.md](docs/ENVIRONMENT.md) | All environment variables and their descriptions |
| [TESTING.md](docs/TESTING.md) | Testing strategy, pyramid, fixtures, best practices |
| [TECH_STACK.md](docs/TECH_STACK.md) | Technology choices and rationale for each tool |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | CI/CD, production deployment, backup & recovery |
| [SECURITY.md](docs/SECURITY.md) | Authentication, authorization, data protection, compliance |
| [CODING_STANDARDS.md](docs/CODING_STANDARDS.md) | Code style, naming conventions, patterns |
| [DECISIONS.md](docs/DECISIONS.md) | Architecture Decision Records (ADRs) and major choices |
| [ERROR_HANDLING.md](docs/ERROR_HANDLING.md) | Exception handling patterns and error responses |
| [OBSERVABILITY.md](docs/OBSERVABILITY.md) | Logging, monitoring, performance profiling |

**Key for new developers:**
- Start with [PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md) for business and technical overview
- Read [ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design
- Follow [CODING_STANDARDS.md](docs/CODING_STANDARDS.md) for code patterns
- Check [DATABASE.md](docs/DATABASE.md) before writing models

---

## Common Workflows

### Add a New Feature

1. Create a new module directory under `backend/app/modules/<feature_name>/`
2. Define models in `models.py`
3. Create database migration: `alembic revision --autogenerate -m "add <feature> table"`
4. Implement service logic in `service.py` (business rules)
5. Implement API endpoints in `router.py`
6. **Add comprehensive tests** in `backend/tests/test_<feature>/` (unit, integration, tenant isolation, RBAC)
7. Update `API.md` with new endpoints
8. Create PR with all tests passing

### Fix a Bug

1. Write a failing test that reproduces the bug
2. Fix the bug in the service/router
3. Verify the test passes
4. Ensure all existing tests still pass: `pytest`
5. Create PR with failing test → fix commit

### Optimize a Slow Query

1. Identify the slow query via [OBSERVABILITY.md](docs/OBSERVABILITY.md) recommendations or `EXPLAIN ANALYZE`
2. Add an index or refactor the query
3. Create a database migration for index changes
4. Run load/performance tests to verify improvement
5. Document the change in commit message and [DECISIONS.md](docs/DECISIONS.md) if it's a significant architectural choice

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'asyncpg'"

Make sure you've run `uv sync` and that `asyncpg` is installed for async PostgreSQL support.

```bash
uv add asyncpg
```

### "FAILED: Path doesn't exist: alembic"

Run Alembic from the `backend/` directory:

```bash
cd backend
uv run python -m alembic -c alembic.ini upgrade head
```

### Database connection refused

Ensure PostgreSQL is running:

```bash
# Check if container is running
docker ps | grep postgres

# Start if not running
docker run -d -e POSTGRES_USER=fitness_user -e POSTGRES_PASSWORD=123 -e POSTGRES_DB=fitness_db -p 5432:5432 postgres:16
```

### Tests fail with "permission denied"

Ensure the test database is accessible and migrations are applied:

```bash
cd backend
uv run python -m alembic -c alembic.ini upgrade head
uv run pytest
```

### "VIRTUAL_ENV mismatch" warning from uv

This warning is harmless — uv is managing its own environment and will ignore system `VIRTUAL_ENV`. You can suppress it by running from the root directory and letting uv manage the environment automatically.

---

## Contributing

1. **Read [CONTRIBUTING.md](docs/CONTRIBUTING.md)** for guidelines on PRs, commits, and collaboration
2. **Follow [CODING_STANDARDS.md](docs/CODING_STANDARDS.md)** for code style and patterns
3. **Write tests for every feature** — see [TESTING.md](docs/TESTING.md)
4. **Ensure all tests pass** before submitting a PR: `cd backend && uv run pytest`
5. **Update documentation** if you change APIs or architecture

---

## License

[Add license info here]

---

## Support & Contact

[Add contact info or support channel here]
