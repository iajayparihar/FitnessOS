# Multi-Tenancy

**One Organization = one tenant.** Every tenant-owned row carries
`organization_id`, and that value is always assigned server-side.

## Resolution chain

```
Clerk session token
      |  app/integrations/clerk/  — see AUTHENTICATION.md
      v
User                       get_current_user()
      |  users.organization_id — the ACTIVE tenant pointer, not an entitlement
      v
OrganizationMembership     get_current_membership()   <- the access authority
      |  must exist, be undeleted, and have status = active
      v
Organization               get_current_organization()
      |  status must be active or pending
      v
TenantContext              get_tenant_context()
      |  binds app.current_organization_id to the transaction
      v
RBAC permission check      require_org_permission("tenants:manage")
```

`users.organization_id` records which of the caller's organizations they are
currently working in. It is re-validated against a live membership on every
request, so a forged or stale pointer grants nothing and revoking a membership
takes effect on the next request.

## Clerk Organizations are not used

The Clerk integration verifies identity only; `org_id` claims are ignored. The
FitnessOS `organizations` table is the sole tenant boundary, so there is no
second source of truth to reconcile.

## Membership vs RBAC

Two questions, two systems:

| Question | Answered by |
|---|---|
| Which tenant is this request in? | `organization_memberships` |
| What may this user do in it? | RBAC `roles` / `permissions` |

They stay separate, bridged at exactly one point: **each membership seat is
granted the same-named system role** when the seat is created or changed. A new
member is therefore usable immediately, without a second manual step.

`sync_seat_rbac_role()` touches system-role assignments only. Any custom role an
organization has additionally granted a user survives a seat change.

### The system role catalogue

Six platform-wide roles, seeded once with `organization_id IS NULL`. There is one
row per role for the whole platform, not a copy per tenant, so adding a
permission to Manager reaches every organization without a data migration. The
tenant lives on the assignment (`user_roles.organization_id`), which is why
holding Admin in Organization A confers nothing in Organization B.

| Seat | Scope |
|---|---|
| `owner` | Everything, including roles, organization lifecycle and subscription |
| `admin` | Runs the business; opens branches. No role management or org lifecycle |
| `manager` | Floor operations; financials read-only; cannot open branches |
| `staff` | Front desk: members, leads, check-ins. Billing read-only |
| `trainer` | Coaching: attendance, training and nutrition plans. No money, no staff admin |
| `member` | A gym-goer. `tenants:read` only |

Two escalation guards shape these sets:

- **Only `owner` holds `rbac:manage`.** Anyone who can edit roles can grant
  themselves any permission, so holding it below owner is equivalent to
  ownership and would make the catalogue decorative.
- **Only `owner` holds `tenants:manage` and `subscriptions:manage`** — archiving
  the organization and changing what it pays for.

`branches:manage` is deliberately *not* part of `tenants:manage`. Opening a
location is routine for a multi-branch operator; archiving the tenant is not.

**`member` is intentionally near-empty.** Permissions are organization-wide, so
granting a gym-goer `membership:read` would expose the entire member list.
Self-service needs object-level scoping, which this system does not yet have.

### Changing the catalogue

`SYSTEM_ROLE_DEFINITIONS` in `app/modules/rbac/service.py` is the source of
truth. `seed_system_roles()` is idempotent and reconciles in both directions: it
grants permissions that are missing and revokes ones no longer in a definition.
Custom roles an organization creates through `/api/v1/rbac/roles` are untouched.

### Role assignment is a service-layer decision, not a route-level check

`assign_role_to_user()` re-validates everything, so a route handler never has to
know the rules itself:

- the target `role_id` must resolve under the caller's organization (a custom
  role from another tenant, or a role that does not exist, both raise
  `RoleNotFound` — the same way a missing one would);
- the target `user_id` must have a live `OrganizationMembership` in that
  organization (`UserNotInOrganization` otherwise) — membership, not
  `users.organization_id`, decides who belongs;
- an optional `branch_id` must belong to the same organization
  (`BranchNotInOrganization` otherwise).

Reaching this function at all already requires `rbac:manage`, which only the
`owner` seat holds — so self-assignment of the owner *RBAC role* is not a
distinct escalation path; it is already gated by the permission catalogue.

### Self-promotion and the owner seat

The one seat-level (not RBAC-level) escalation path is the membership PATCH/POST
endpoints, because `users:manage` — needed to add or edit a member — is held by
`admin`, not just `owner`. Two rules close it, enforced in
`update_membership()`/`add_membership()`, not in the router:

- **No actor may change their own membership role**, unconditionally. An admin
  editing their own row to `{"role": "owner"}` is refused with 403 before any
  other check runs, regardless of whether they are the last owner or not.
- **Only an existing owner may grant, revoke, or otherwise touch a membership
  that holds the owner seat** — a role change, a status change (suspending an
  owner's account), or adding a new member as owner all require the actor's own
  membership to already be `owner`. This is what stops `users:manage` (Admin)
  from minting or deposing owners.

Both checks run before the last-owner-removal check, so demoting the sole owner
answers 403 (self-role-change) rather than 409 — self-promotion protection is
strictly stronger than merely preserving owner *count*.

## Never trust a client-supplied organization_id

No request schema exposes `organization_id`; a test asserts this against the
OpenAPI document. A path `{organization_id}` is a routing convenience checked
against the resolved tenant, and the check runs **before** the permission check
so a cross-tenant probe always answers 404 regardless of what the caller may do
in their own tenant.

Service reads take `organization_id` as a required argument and put it in the
`WHERE` clause rather than comparing after the fetch:

```python
select(OrganizationBranch).where(
    OrganizationBranch.organization_id == organization_id,   # not a post-hoc check
    OrganizationBranch.id == branch_id,
)
```

## Error shape

Cross-tenant access, a missing record and a non-member all answer
`404 {"detail": "Organization not found."}` — identical bodies, so status codes
cannot be used to discover which ids exist. `403` means the caller is in the
right tenant but lacks the permission, or the organization is not operational.

## Row-level security

Policies are not enabled yet, but the groundwork is in place. Every request
binds its tenant with:

```sql
select set_config('app.current_organization_id', :org, true)
```

The `true` makes it **transaction-local**. Connections are pooled, so a
session-level `SET` would survive checkin and hand one tenant's identity to the
next request that borrows the connection. Two tests assert the setting is
discarded on COMMIT and on ROLLBACK, and never reaches a second session.

To enable RLS later, add policies matching the `# RLS POLICY` comments in the
model modules:

```sql
ALTER TABLE organization_branches ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON organization_branches
  USING (organization_id = current_setting('app.current_organization_id')::uuid);
```

## Organization lifecycle

`active` and `pending` are operational. `suspended`, `cancelled` and `archived`
are refused by `get_tenant_context`, so no tenant-scoped route keeps serving a
frozen organization.

Deleting an organization soft-deletes it and sets `archived`. Gym records are
retained for billing, attendance and compliance history.

## Invariants enforced by the database

| Invariant | Mechanism |
|---|---|
| Unique slug among live organizations | partial unique index on `lower(slug)` where `deleted_at IS NULL` |
| One live membership per (user, org) | partial unique index where `deleted_at IS NULL` |
| At most one main branch per org | partial unique index where `is_main AND deleted_at IS NULL` |
| Unique branch name per org | partial unique index on `(organization_id, lower(name))` |
| One settings row per (org, branch, key) | unique constraint |

Application checks narrow the candidate; the indexes are what hold under
concurrency.

## Provisioning is atomic

`provision_organization()` writes the organization, owner membership, owner RBAC
role, main branch and default settings in one transaction. Any failure rolls all
of it back — a half-initialised organization with no owner or no main branch can
never exist. `POST /api/v1/organizations`, `POST /api/v1/auth/onboarding` and the
legacy password registration all go through it, so there is one creation path.
