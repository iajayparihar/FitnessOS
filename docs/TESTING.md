# Testing Strategy

## Fitness Business OS

---

## 1. Philosophy

Testing is not optional polish — it's how we protect a multi-tenant system handling money, PII, and medical data from regressions. Every module ships with tests as part of "done," not as a follow-up task.

---

## 2. Testing Pyramid

```
        ┌───────────────┐
        │   E2E (few)      │   Critical user journeys only
        ├───────────────┤
        │ Integration (some) │   API endpoints, DB interactions
        ├───────────────┤
        │  Unit (many)          │   Service logic, utilities, validators
        └───────────────┘
```

---

## 3. Backend Testing (pytest)

### Unit Tests
- Target: service-layer business logic, utility functions, validators.
- Mock/stub external dependencies (payment gateway, SMS/WhatsApp providers, email).
- Fast (milliseconds), run on every save/CI run.

### Integration Tests
- Target: API endpoints end-to-end against a real (test) PostgreSQL database.
- Use a dedicated test database, reset/rolled back between tests (transaction rollback or fresh schema per test run).
- Cover: happy path, validation errors, permission denials, not-found cases.

### Tenant Isolation Tests (Mandatory Per Module)
Every module with tenant-scoped data must include an explicit test proving isolation, e.g.:

```python
async def test_tenant_cannot_access_other_tenants_member(client, tenant_a, tenant_b):
    member = await create_member(tenant_id=tenant_b.id)
    response = await client.get(
        f"/api/v1/members/{member.id}",
        headers=auth_headers(tenant_a.owner_user),
    )
    assert response.status_code == 404
```

This is treated as a **security control**, not just a functional test — see `SECURITY.md`.

### RBAC Tests
Every permission-gated endpoint must have at least one test confirming an under-permissioned role is rejected (`403`), e.g., Receptionist attempting `payments:delete`.

### Fixtures & Factories
- Shared `conftest.py` fixtures: test DB session, test client, tenant factory, user factory (per role), auth header helper.
- Use factory functions/libraries (e.g., `factory_boy` or simple factory functions) to generate realistic test data — avoid copy-pasted fixture blobs.

### Coverage Target
- Minimum 80% coverage on service-layer code as a guideline, not a vanity metric — critical paths (billing, auth, tenancy) should approach 100%.
- Coverage reports generated in CI; regressions below threshold block merge (threshold to be tuned as the codebase matures).

---

## 4. Frontend Testing

| Type | Tool | Scope |
|---|---|---|
| Unit | Vitest / Jest | Utility functions, hooks, pure logic |
| Component | React Testing Library | Individual components, form validation, permission-gated rendering |
| E2E | Playwright (or Cypress) | Critical user journeys across real browser |

### Critical E2E Journeys (Minimum Set)
- Owner signs up → creates tenant → logs in
- Receptionist adds a lead → converts to member → registers membership
- Member payment/invoice flow (using payment gateway test mode)
- QR check-in flow
- Trainer assigns workout to a member
- RBAC: a Trainer cannot access billing screens

---

## 5. Test Data & Environments

- Tests never run against staging/production databases.
- A seed script (`scripts/seed_demo_data.py`) provides realistic demo data for manual QA/staging, separate from automated test fixtures.
- Payment gateway, SMS, WhatsApp, email providers are used in **sandbox/test mode** in CI and staging — never live in non-production environments.

---

## 6. CI Enforcement

Per `DEPLOYMENT.md`, every PR runs:
1. Backend unit + integration tests (`pytest`)
2. Frontend unit + component tests (`vitest`/`jest`)
3. Linting/type-checking (treated as part of "tests must pass")
4. (On merge to `develop`) E2E suite against the staging deploy

No PR merges with failing or newly-skipped tests without an explicit, reviewed justification in the PR description.

---

## 7. Performance & Load Testing

- Introduced once core modules (CRM → Billing, Phases 4–7) are stable.
- Target: k6 or Locust scripts simulating realistic multi-tenant load (many tenants, concurrent check-ins during peak gym hours).
- Used to validate the `tenant_id`-indexed query strategy actually scales before onboarding larger customers.

---

## 8. Manual QA Checklist (Pre-Release, Until Automation Matures)

For each release, manually verify (in addition to automated tests):
- New feature works for each relevant role (Owner/Manager/Receptionist/Trainer/etc.)
- No regression in tenant isolation (spot-check with two demo tenants)
- Mobile-responsive check on the frontend (until dedicated mobile apps exist)
- Payment flows in gateway sandbox mode

This checklist should shrink over time as E2E coverage grows — track in `CHANGELOG.md` / release notes.
