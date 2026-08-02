# Database Design & Conventions

## Fitness Business OS

---

## 1. Engine & Approach

- **Database:** PostgreSQL 16+
- **ORM:** SQLAlchemy 2.x (async), models defined declaratively
- **Migrations:** Alembic — every schema change goes through a migration, never manual DDL in prod
- **Multi-tenancy model:** Shared database, shared schema, `tenant_id` (organization_id) column on every tenant-scoped table, enforced via ORM base classes + PostgreSQL Row-Level Security (RLS)

---

## 2. Naming Conventions

| Object | Convention | Example |
|---|---|---|
| Tables | `snake_case`, plural | `members`, `lead_follow_ups` |
| Columns | `snake_case` | `first_name`, `created_at` |
| Primary keys | `id` (UUID) | `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` |
| Foreign keys | `<referenced_table_singular>_id` | `tenant_id`, `member_id`, `plan_id` |
| Booleans | `is_<state>` / `has_<state>` | `is_active`, `has_paid` |
| Timestamps | `<verb>_at` | `created_at`, `updated_at`, `deleted_at` |
| Enums | `snake_case` values, defined as Postgres enum or constrained varchar | `status: 'active' | 'frozen' | 'cancelled'` |
| Indexes | `ix_<table>_<column(s)>` | `ix_members_tenant_id` |
| Unique constraints | `uq_<table>_<column(s)>` | `uq_members_tenant_id_email` |
| Foreign key constraints | `fk_<table>_<referenced_table>` | `fk_members_tenant` |

---

## 3. Primary Keys & IDs

- All primary keys are **UUIDv4** (`gen_random_uuid()` / `uuid4()`), not auto-increment integers.
  - Rationale: safe to generate client-side/offline, no cross-tenant enumeration risk, merge-friendly across environments.
- Never expose internal sequential IDs in URLs or APIs.

---

## 4. Mandatory Columns (Every Tenant-Scoped Table)

```sql
id            UUID PRIMARY KEY DEFAULT gen_random_uuid()
tenant_id     UUID NOT NULL REFERENCES tenants(id)
created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
deleted_at    TIMESTAMPTZ NULL          -- soft delete
created_by    UUID NULL REFERENCES users(id)
updated_by    UUID NULL REFERENCES users(id)
```

- **Soft deletes by default** for business-critical data (members, payments, leads). Hard deletes only for non-critical, easily-recreated data (e.g., cached reports), and always behind an explicit service method — never a raw `DELETE`.
- `tenant_id` is **never nullable** on tenant-scoped tables, and is always indexed.
- Every tenant-scoped table has a composite index starting with `tenant_id` for any commonly filtered/sorted column, e.g. `ix_members_tenant_id_status`.

---

## 5. Tenant Isolation Enforcement (Defense in Depth)

1. **ORM layer:** A `TenantScopedBase` model mixin + a base repository/service that automatically injects `WHERE tenant_id = :current_tenant_id` into every query. Bypassing this requires an explicit, reviewed exception (e.g., Super Admin tooling).
2. **Database layer:** PostgreSQL Row-Level Security (RLS) policies on every tenant-scoped table, tied to a session-level `app.current_tenant_id` setting, so even a raw/ad-hoc query cannot leak cross-tenant data.
3. **Test layer:** Every module's test suite includes an explicit "tenant isolation" test that asserts Tenant A cannot read/write Tenant B's data via the API.

---

## 6. Core Entities (High-Level, Expands Per Module)

### Platform / Tenancy
- `tenants` — organization record, plan, branding, status
- `subscriptions` — tenant's billing plan, cycle, status
- `users` — platform users (staff + owner), tenant-scoped except Super Admin
- `roles`, `permissions`, `role_permissions` — RBAC
- `refresh_tokens` — hashed, rotated

### CRM
- `leads`, `lead_sources`, `lead_follow_ups`, `lead_status_history`

### Membership
- `members`, `membership_plans`, `member_subscriptions`, `member_documents`, `member_medical_info`, `member_freezes`, `member_transfers`

### Attendance
- `attendance_logs`, `qr_check_in_tokens`

### Billing
- `invoices`, `invoice_items`, `payments`, `discounts`, `coupons`, `refunds`

### Trainer
- `workout_templates`, `exercises`, `workout_assignments`, `trainer_notes`, `member_progress`

### Nutrition
- `meal_plans`, `meal_plan_items`, `body_measurements`, `progress_photos`

### Inventory
- `inventory_items`, `stock_movements`, `suppliers`, `purchase_orders`

### Expenses
- `expenses`, `expense_categories`

### Notifications
- `notification_templates`, `notification_logs`, `notification_preferences`

Each module's detailed schema (columns, constraints, relationships, ER diagram) should be added to this file incrementally as that module is implemented — do not pre-design tables far ahead of the current roadmap phase (see `ROADMAP.md`).

---

## 7. Migrations Workflow

```bash
# Create a new migration after changing models
alembic revision --autogenerate -m "add member_freezes table"

# Review the generated migration file manually before applying — autogenerate is not perfect

# Apply migrations
alembic upgrade head

# Roll back one revision
alembic downgrade -1
```

Rules:
- Every migration must be reversible (`upgrade` and `downgrade` both implemented).
- No migration should be edited after it has been merged/deployed — create a new migration to fix it instead.
- Data migrations (backfills) are separate from schema migrations where possible.
- Migrations are reviewed in PRs like any other code.

---

## 8. Data Types & Standards

- Money: stored as **integer minor units** (e.g., paise/cents) or `NUMERIC(12,2)` — decided per field, never `FLOAT`.
- Dates/times: always `TIMESTAMPTZ`, stored in UTC; converted to tenant/local timezone at the presentation layer.
- Enums: prefer Postgres native `ENUM` types for fixed, rarely-changing value sets; use constrained varchar + application-level validation for sets likely to grow.
- JSON/JSONB: allowed for genuinely unstructured/flexible data (e.g., custom form fields), not as a substitute for proper relational modeling.

---

## 9. Indexing Guidelines

- Every foreign key column is indexed.
- Every `tenant_id` column is indexed (and leads composite indexes for common filters).
- Add indexes based on actual query patterns identified in `API.md` endpoints, not speculatively.
- Review slow queries via `EXPLAIN ANALYZE` before adding indexes in response to performance issues (see `OBSERVABILITY.md`).

---

## 10. Backup & Retention

- Automated daily backups (managed Postgres) with point-in-time recovery where available.
- Backup/restore procedure documented in `DEPLOYMENT.md`.
- Soft-deleted records retained per a data retention policy to be defined in `SECURITY.md` (compliance requirement, e.g., GST/financial record retention rules).
