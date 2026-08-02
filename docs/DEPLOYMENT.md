# Deployment Guide

## Fitness Business OS

---

## 1. Environments

| Environment | Purpose | URL (example) |
|---|---|---|
| **Local** | Individual developer machines | `localhost` |
| **Staging** | Pre-prod validation, QA, demos | `staging.fitnessbusinessos.com` |
| **Production** | Live customer traffic | `app.fitnessbusinessos.com` / `api.fitnessbusinessos.com` |

Every environment runs the same Docker images built by CI — no environment-specific code branches, only environment-specific configuration via environment variables (`ENVIRONMENT.md`).

---

## 2. Deployment Topology (Target)

```
                     ┌────────────────────┐
                     │   DNS / CDN (Cloudflare) │
                     └───────────┬────────────┘
                                 ▼
                     ┌────────────────────┐
                     │  Load Balancer / Nginx │
                     │      (TLS termination)   │
                     └───────────┬────────────┘
                                 ▼
                ┌────────────────┴─────────────────┐
                ▼                                    ▼
     ┌────────────────────┐               ┌────────────────────┐
     │  Backend containers    │               │  Frontend (static)     │
     │  (FastAPI, N replicas)   │               │  served via CDN/Nginx    │
     └───────────┬────────────┘               └────────────────────┘
                 │
     ┌───────────┼──────────────┐
     ▼                           ▼
┌──────────┐             ┌──────────────┐
│ PostgreSQL │             │  Redis          │
│ (managed)    │             │  (managed)        │
└──────────┘             └──────────────┘
                                 │
                                 ▼
                     ┌────────────────────┐
                     │  Celery Workers        │
                     │  (N replicas)             │
                     └────────────────────┘
```

- **Backend:** containerized FastAPI app, run via Gunicorn + Uvicorn workers, horizontally scaled behind the load balancer.
- **Database:** managed PostgreSQL (AWS RDS or DigitalOcean Managed Database) — not self-hosted, to offload backups/HA/patching.
- **Redis:** managed Redis (ElastiCache / DigitalOcean Managed Redis).
- **Frontend:** built as static assets (Vite build), served via CDN or Nginx.
- **Workers:** Celery workers as a separate deployable, scaled independently from the API.

Final cloud provider decision (AWS vs. DigitalOcean) to be logged in `DECISIONS.md`.

---

## 3. CI/CD Pipeline (GitHub Actions)

### On every PR:
1. Lint (Ruff/Black/mypy for backend, ESLint/Prettier/tsc for frontend)
2. Run test suites (backend + frontend) — see `TESTING.md`
3. Build Docker images (validate build succeeds)
4. Dependency vulnerability scan

### On merge to `develop`:
1. All PR checks
2. Deploy automatically to **Staging**
3. Run smoke tests against staging

### On merge/tag to `main`:
1. All PR checks
2. Build production images, tag with commit SHA + semantic version
3. Push to container registry
4. Run database migrations against production (with manual approval gate)
5. Rolling deploy to production (zero-downtime)
6. Run post-deploy smoke tests
7. Notify team (Slack/email) of deploy status

Manual approval gate required before any production deploy — no fully automatic prod deploys until the team has enough confidence in the pipeline and test coverage.

---

## 4. Database Migrations in Production

- Migrations run as a distinct CI/CD step **before** the new application version receives traffic.
- All migrations must be backward-compatible with the previous app version for at least one deploy cycle (to support zero-downtime rolling deploys) — i.e., avoid dropping a column in the same deploy that stops writing to it.
- Migration rollback plan documented for any risky/large migration.

---

## 5. Zero-Downtime Deployment Strategy

- Rolling deploys: new containers started and health-checked before old ones are terminated.
- Health check endpoint: `GET /health` (checks DB connectivity, Redis connectivity).
- Readiness vs. liveness probes configured for the orchestrator (e.g., Docker Swarm, ECS, or Kubernetes — final choice pending, see `DECISIONS.md`).

---

## 6. Backup & Disaster Recovery

- Automated daily database backups with point-in-time recovery (managed DB feature).
- Backup restore drills performed periodically (documented cadence to be defined) to verify backups are actually restorable.
- Object storage (documents, photos) versioned/replicated per provider defaults.
- Recovery Time Objective (RTO) and Recovery Point Objective (RPO) targets to be defined before general availability launch.

---

## 7. Secrets & Configuration in Deployment

- Secrets injected via the cloud provider's secrets manager / CI secret store — never baked into Docker images or committed to the repo.
- See `ENVIRONMENT.md` for the full list of required variables per environment.

---

## 8. Rollback Procedure

1. Identify the last known-good image tag/commit SHA.
2. Redeploy that tagged image via the same CI/CD pipeline (rollback is just a deploy of an older, known-good artifact).
3. If a migration must be rolled back, run the corresponding `alembic downgrade` **only if safe** (verify no destructive/irreversible step was involved) — otherwise, forward-fix with a new migration.
4. Post-incident: log a summary in `DECISIONS.md` or an incidents log if the rollback was due to a production issue.

---

## 9. Monitoring Post-Deploy

- Error rate, latency (p50/p95/p99), and request volume monitored immediately after each deploy (see `OBSERVABILITY.md`).
- Automated alert if error rate spikes above baseline within N minutes of a deploy — triggers investigation/rollback consideration.

---

## 10. Local Development Deployment (Reference)

```bash
docker compose up --build
docker compose exec backend alembic upgrade head
```

See `README.md` for the full local setup guide and `ENVIRONMENT.md` for required local `.env` values.
