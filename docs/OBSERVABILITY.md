# Observability

## Fitness Business OS

Logging, metrics, and tracing are built in from Phase 2 (Foundation) onward — not retrofitted after launch. A multi-tenant SaaS handling money and PII needs to know quickly when something is wrong, for whom, and why.

---

## 1. Pillars

| Pillar | Purpose | Tooling (target) |
|---|---|---|
| **Logging** | What happened, structured and searchable | Structured JSON logs → centralized aggregator (ELK / Loki / hosted) |
| **Metrics** | System health trends over time | Prometheus + Grafana (or hosted equivalent) |
| **Tracing** | Follow a request across layers/services | OpenTelemetry (added as complexity grows beyond the initial monolith) |
| **Error Tracking** | Catch and triage exceptions | Sentry |

---

## 2. Structured Logging

- All logs are **structured JSON**, not free-text strings — enables filtering/querying in the log aggregator.
- Every log line includes, at minimum:
  - `timestamp`
  - `level` (DEBUG/INFO/WARNING/ERROR/CRITICAL)
  - `request_id` (correlates to a specific API request, see `ERROR_HANDLING.md`)
  - `tenant_id` (when applicable — critical for tenant-specific debugging and isolation auditing)
  - `user_id` (when applicable)
  - `module` (e.g., `billing`, `crm`)
  - `message`

### Example
```json
{
  "timestamp": "2026-01-15T10:22:31Z",
  "level": "INFO",
  "request_id": "req_01HXYZ1234ABCD",
  "tenant_id": "t_9f2a...",
  "user_id": "u_11ab...",
  "module": "billing",
  "message": "Invoice created",
  "invoice_id": "inv_88cd..."
}
```

### Rules
- **Never log secrets, passwords, full tokens, or raw payment card data.**
- Sensitive PII (medical details, full addresses) logged only when strictly necessary for debugging, and minimized/redacted otherwise.
- `DEBUG` level is verbose and used only in local/staging; `production` defaults to `INFO`.

---

## 3. Request Correlation (`request_id`)

- Every incoming request is assigned a `request_id` (generated or propagated from an `X-Request-ID` header if provided by a client/load balancer) at the very start of the request lifecycle via middleware.
- Attached to: all log lines for that request, the error response (`ERROR_HANDLING.md`), and any downstream calls (Celery tasks triggered by the request should carry it forward).
- This is the primary tool for "a customer reported an error, find out what happened" debugging.

---

## 4. Metrics

### Application Metrics (Minimum Set)
- Request rate, error rate, and latency (p50/p95/p99) per endpoint.
- Background job (Celery) queue length, task success/failure rate, task duration.
- Database connection pool utilization, query latency.
- Redis hit/miss rate for cached aggregates.

### Business Metrics (Feed Into Dashboard Module — Phase 10)
- Active tenants, active members, sign-ups, churned tenants.
- These are product/business metrics surfaced to internal teams and eventually reflected in the customer-facing Dashboard module — kept conceptually distinct from operational/infra metrics above.

### Alerting Thresholds (Baseline — Tune Over Time)
- Error rate > X% over 5 minutes → page on-call.
- p95 latency > Y ms sustained → alert.
- Celery queue backlog growing unbounded → alert.
- Database connection pool near exhaustion → alert.

---

## 5. Error Tracking (Sentry)

- All unhandled exceptions (5xx errors, per `ERROR_HANDLING.md`) are automatically reported to Sentry with full stack trace, request context, `tenant_id`, and `user_id` (respecting PII rules above).
- Sentry issues are triaged with a clear severity (Sev-1 = active customer-impacting incident, Sev-2 = degraded, Sev-3 = minor/cosmetic).
- Frontend errors (React error boundaries, unhandled promise rejections) also reported to Sentry, separate project/environment tag from backend.

---

## 6. Audit Logging vs. Application Logging

These are distinct:
- **Application logs** — operational, for debugging, may be sampled/rotated, retained for a shorter window (e.g., 30–90 days).
- **Audit logs** — security-relevant events (login, permission changes, payment deletions/refunds, data exports, Super Admin cross-tenant access) per `SECURITY.md` — immutable, retained longer, queryable specifically for compliance/security review, not mixed in with general app logs.

---

## 7. Health Checks

- `GET /health` — liveness (is the process up)
- `GET /health/ready` — readiness (can it serve traffic: DB reachable, Redis reachable)

Used by the deployment orchestrator for rolling deploys (see `DEPLOYMENT.md`) and by uptime monitoring.

---

## 8. Dashboards (Internal, Ops)

Minimum Grafana (or equivalent) dashboards to stand up early:
1. **API Health** — request rate, error rate, latency by endpoint.
2. **Background Jobs** — Celery queue depth, task failures.
3. **Database** — connection pool, slow queries, replication lag (if applicable).
4. **Business Snapshot** — active tenants, sign-ups, MRR trend (feeds from the same data as the customer Dashboard module, viewed internally).

---

## 9. Rules for New Modules

Every new backend module must, at minimum:
- Log key state-changing actions (creates/updates/deletes) at `INFO` with `tenant_id`/`user_id` context.
- Emit error-level logs (and let them flow to Sentry) on unexpected failures.
- Avoid introducing unstructured `print()`/`console.log()` debugging left in committed code.
