# Architecture Decision Records (ADR)

## Fitness Business OS

This file logs significant architectural, technical, and business decisions, why they were made, and what alternatives were considered. Every non-trivial decision referenced in other docs (`ARCHITECTURE.md`, `TECH_STACK.md`, `SECURITY.md`, etc.) should have a corresponding entry here.

**Format:** Each ADR is numbered sequentially and never renumbered or deleted, even if later superseded — supersession is recorded explicitly.

---

## ADR Template

```markdown
## ADR-000X: <Short Title>

**Status:** Proposed | Accepted | Superseded by ADR-000Y | Deprecated
**Date:** YYYY-MM-DD
**Deciders:** <who>

### Context
What problem are we solving? What forces/constraints apply?

### Decision
What did we decide to do?

### Alternatives Considered
- Option A — why rejected
- Option B — why rejected

### Consequences
What becomes easier or harder as a result? What follow-up work does this create?
```

---

## ADR-0001: Modular Monolith Over Microservices (Initial Architecture)

**Status:** Accepted
**Date:** TBD (log actual date at project kickoff)
**Deciders:** Founding team

### Context
Fitness Business OS has a large eventual feature surface (CRM, Membership, Billing, Trainer, Nutrition, Inventory, Expenses, Notifications, AI, Marketplace, Enterprise). A small team needs to move fast without taking on premature distributed-systems complexity.

### Decision
Build as a **modular monolith**: single deployable FastAPI backend, internally organized into strictly separated modules (bounded contexts) that communicate through service-layer interfaces, not direct cross-module DB access.

### Alternatives Considered
- **Microservices from day one** — rejected: too much operational overhead (service discovery, distributed transactions, network reliability, deployment complexity) for a small team and unvalidated product.
- **Unstructured monolith (no module boundaries)** — rejected: leads to a "big ball of mud" that's expensive to untangle later if/when specific modules need to scale independently.

### Consequences
- Faster initial development, simpler deployment/ops.
- Requires discipline to maintain module boundaries (enforced via `FOLDER_STRUCTURE.md` and `CODING_STANDARDS.md`) so a future extraction to services is possible without a full rewrite.
- Revisit this decision if a specific module (e.g., Notifications, AI) develops distinct scaling or team-ownership needs.

---

## ADR-0002: Shared Database, Shared Schema Multi-Tenancy

**Status:** Accepted
**Date:** TBD
**Deciders:** Founding team

### Context
The platform must guarantee strict tenant data isolation while remaining operationally simple and cost-effective at MVP scale (many small gym tenants, not a handful of huge enterprise customers).

### Decision
Use a **shared database, shared schema** model: every tenant-scoped table has a `tenant_id` column, enforced via ORM-layer automatic filtering plus PostgreSQL Row-Level Security as defense in depth.

### Alternatives Considered
- **Database per tenant** — rejected for MVP: high operational overhead (migrations across N databases, connection pooling complexity) not justified at current scale.
- **Schema per tenant** — rejected for MVP: still meaningfully more complex to migrate/manage than shared schema; reconsidered for large Enterprise customers requiring stronger isolation guarantees.

### Consequences
- Simple, single migration path; lower infra cost.
- Requires rigorous enforcement (RLS + ORM base classes + mandatory isolation tests, per `DATABASE.md`/`SECURITY.md`) since a bug here is a critical security incident.
- Migration path exists to move a specific large tenant to a dedicated schema/database later if required contractually.

---

## ADR-0003: Cloud Hosting Provider (AWS vs. DigitalOcean)

**Status:** Proposed — pending decision
**Date:** TBD
**Deciders:** TBD

### Context
Need a hosting provider for staging/production. AWS offers more services/scale headroom; DigitalOcean offers simpler pricing and operations for a small team.

### Decision
*(To be filled in once decided — record the choice, pricing rationale, and target managed services used: e.g., RDS vs. Managed PostgreSQL, ElastiCache vs. Managed Redis.)*

### Alternatives Considered
- AWS — more services, steeper learning curve, more granular IAM/security controls.
- DigitalOcean — simpler, cheaper at small scale, less flexibility at large scale.

### Consequences
*(Fill in after decision.)*

---

## ADR-0004: Payment Gateway Selection

**Status:** Proposed — pending decision
**Date:** TBD

### Context
Need a payment gateway supporting the Indian market (primary launch market) with a path to international expansion. Candidates: Razorpay, Cashfree, Stripe.

### Decision
*(To be filled in — record chosen provider(s), fee structure, and PCI-scope implications.)*

---

## ADR-0005: Client-State Management Library (Frontend)

**Status:** Proposed — pending decision
**Date:** TBD

### Context
Need a lightweight client-state solution alongside React Query (which handles server state). Candidates: Zustand, Redux Toolkit, React Context.

### Decision
*(To be filled in.)*

---

## ADR-0006: Clerk as Identity Provider (Replaces Custom JWT/Password Auth)

**Status:** Accepted
**Date:** 2026-09-17
**Deciders:** Founding team

### Context
The backend had a custom auth stack (self-signed JWTs, PBKDF2 passwords, DB-backed refresh sessions). Maintaining credential storage, password reset, email verification, MFA, and login lockout in-house is significant, security-sensitive surface for a small team. RBAC and multi-tenancy are our differentiators; identity is not.

### Decision
Delegate identity to **Clerk**. The backend verifies Clerk session JWTs (RS256) at a single chokepoint (`get_current_user`), provisions local users just-in-time (linked via a `CLERK` `UserAuthMethod`), and keeps organization/RBAC state authoritative in our database. Password hashing, self-issued JWTs, and the `sessions` table were removed.

### Alternatives Considered
- **Keep custom auth** — rejected: ongoing maintenance and security burden (reset/verify/MFA/lockout) for undifferentiated work.
- **Add Clerk alongside custom auth** — rejected: two identity systems to maintain; contradicts a lean surface.
- **Other IdPs (Auth0/Cognito/Firebase)** — viable; Clerk chosen for developer experience and first-class organization primitives. Revisit if pricing or org-sync needs change.

### Consequences
- Less security-critical code; MFA/reset/verification configured in Clerk, not code.
- New dependency on Clerk availability; requires a Clerk JWT template exposing `email`/name claims for offline provisioning.
- Org lifecycle sync currently via JIT provisioning + onboarding/invite endpoints; Clerk webhooks can be added later if server-side lifecycle sync is needed.
- Rate limiting on our own API is now in-app (`slowapi`), since Clerk only covers login-side throttling.

---

*Add new ADRs below as decisions are made. Do not skip logging a decision just because it feels "obvious" at the time — future context is exactly what this file protects.*
