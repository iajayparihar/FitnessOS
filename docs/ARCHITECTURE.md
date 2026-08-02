# System Architecture

## Fitness Business OS

---

## 1. Architectural Style

**Modular Monolith.** Not microservices, initially.

- Single deployable backend application, internally organized into strict, decoupled modules (bounded contexts).
- Each module owns its own models, schemas, services, and routes.
- Modules communicate through well-defined service-layer interfaces or internal events — never by reaching into another module's database tables directly.
- This gives most of the maintainability benefits of microservices (clear boundaries) without the operational cost (distributed systems complexity, network calls, eventual consistency) that a small team can't yet support.
- Microservices are only introduced later, per a documented ADR, when a specific module has scaling or team-ownership needs that the monolith can no longer satisfy.

Rationale documented in [`DECISIONS.md`](./DECISIONS.md) (ADR-0001).

---

## 2. High-Level System Diagram

```
                         ┌─────────────────────┐
                         │      Frontend        │
                         │  React + TypeScript  │
                         │   (Owner/Staff Web)   │
                         └──────────┬───────────┘
                                    │ HTTPS / REST (JSON)
                                    ▼
                         ┌─────────────────────┐
                         │        Nginx          │
                         │  (reverse proxy, TLS)  │
                         └──────────┬───────────┘
                                    ▼
                         ┌─────────────────────┐
                         │     FastAPI App        │
                         │  (Modular Monolith)     │
                         │ ┌───────────────────┐ │
                         │ │ Auth & Tenancy      │ │
                         │ │ CRM                 │ │
                         │ │ Membership          │ │
                         │ │ Billing             │ │
                         │ │ Attendance          │ │
                         │ │ Trainer             │ │
                         │ │ Nutrition           │ │
                         │ │ Inventory           │ │
                         │ │ Expenses            │ │
                         │ │ Notifications        │ │
                         │ │ Dashboard/Analytics  │ │
                         │ └───────────────────┘ │
                         └───┬─────────┬─────────┘
                             │         │
                  ┌──────────┘         └──────────┐
                  ▼                                ▼
         ┌────────────────┐              ┌──────────────────┐
         │   PostgreSQL     │              │      Redis         │
         │ (tenant-scoped    │              │ (cache, sessions,   │
         │  relational data)  │              │  Celery broker)     │
         └────────────────┘              └──────────────────┘
                                                    │
                                                    ▼
                                          ┌──────────────────┐
                                          │  Celery Workers    │
                                          │ (notifications,     │
                                          │  reports, async jobs)│
                                          └──────────────────┘
```

Mobile apps (Member/Trainer/Owner) and external integrations (payment gateways, WhatsApp/SMS providers) talk to the same FastAPI backend over versioned REST APIs.

---

## 3. Layered Structure (Per Module)

Every module follows the same internal layering:

```
Router (API layer)
   ↓ calls
Service (business logic layer)
   ↓ calls
Repository / SQLAlchemy models (data access layer)
   ↓
PostgreSQL (tenant-scoped tables)
```

- **Router**: Request/response handling, input validation via Pydantic schemas, auth/RBAC dependency injection. No business logic.
- **Service**: All business rules live here. Orchestrates repositories, enforces tenant scoping, emits events/notifications.
- **Repository/Models**: SQLAlchemy ORM models and query logic. No business rules.

Routers must never query the database directly — always go through the service layer. See [`CODING_STANDARDS.md`](./CODING_STANDARDS.md).

---

## 4. Multi-Tenancy Model

**Approach:** Shared database, shared schema, with a `tenant_id` (organization_id) column on every tenant-scoped table — enforced at the ORM/query layer with a mandatory tenant filter.

- Chosen over "database per tenant" or "schema per tenant" for operational simplicity at MVP scale, with a documented migration path if a large enterprise customer requires stronger isolation later (ADR-0002).
- Every request is resolved to a `tenant_id` via the authenticated user's JWT claims.
- A base repository/service class automatically injects `tenant_id` filters into every query — no query is allowed to skip this without an explicit, reviewed exception (e.g., Super Admin cross-tenant reporting).
- Row-level isolation is additionally enforced via PostgreSQL Row-Level Security (RLS) policies as a defense-in-depth layer.

Full data model conventions: [`DATABASE.md`](./DATABASE.md). Enforcement details: [`SECURITY.md`](./SECURITY.md).

---

## 5. Authentication & Authorization

- **AuthN:** JWT access tokens (short-lived) + refresh tokens (long-lived, rotated, stored hashed).
- **AuthZ:** Role-Based Access Control (RBAC) with granular permissions per role, evaluated per-endpoint via FastAPI dependencies.
- Roles are tenant-scoped except Super Admin (platform-level).

Details: [`SECURITY.md`](./SECURITY.md).

---

## 6. Asynchronous Processing

Celery + Redis handle anything that shouldn't block the request/response cycle:

- Sending notifications (email/SMS/WhatsApp/push)
- Generating reports/exports
- Scheduled jobs (renewal reminders, birthday wishes, churn scoring)
- Future AI workloads (workout/diet generation, forecasting)

Redis also serves as the application cache (e.g., dashboard aggregates, rate limiting).

---

## 7. Frontend Architecture

- React + TypeScript SPA, Material UI component library.
- Feature-folder structure mirroring backend modules (see `FOLDER_STRUCTURE.md`).
- API access via a typed client layer (generated or hand-maintained from OpenAPI schema) — no raw fetch calls scattered through components.
- Role-aware routing/rendering driven by the authenticated user's permissions.

---

## 8. Infrastructure

- **Containerization:** Docker for all services; Docker Compose for local dev.
- **Reverse proxy/TLS:** Nginx.
- **CI/CD:** GitHub Actions (lint, test, build, deploy).
- **Hosting:** AWS or DigitalOcean (decision pending — see `DECISIONS.md`).
- **Database:** Managed PostgreSQL where available; automated backups.

Full deployment topology: [`DEPLOYMENT.md`](./DEPLOYMENT.md).

---

## 9. Observability

Structured logging, metrics, and tracing are first-class from Phase 2 onward — not bolted on later. See [`OBSERVABILITY.md`](./OBSERVABILITY.md).

---

## 10. Evolution Path

| Trigger | Likely Architectural Change |
|---|---|
| A single module (e.g., Notifications) needs independent scaling | Extract as a standalone service behind an internal API/queue |
| Enterprise customer requires hard data isolation | Move that tenant to a dedicated schema or database |
| AI workloads become compute-heavy | Extract AI module to a separate service with its own infra (GPU, model serving) |
| Marketplace grows into its own ecosystem | Split into a separate product surface with its own team |

Each of these transitions requires an ADR before implementation — see [`DECISIONS.md`](./DECISIONS.md).
