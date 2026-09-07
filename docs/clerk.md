# FitnessOS — Clerk Authentication Migration

## Master Implementation Prompt

You are working on the existing `FitnessOS` repository:

https://github.com/iajayparihar/FitnessOS

Your task is to migrate the authentication layer from the current custom authentication implementation to Clerk while preserving the existing FitnessOS architecture, business logic, multi-tenancy, RBAC, database models, and API contracts wherever practical.

Do NOT perform a blind rewrite.

The target architecture is:

```
Clerk
   |
   | Authentication / Identity
   v
FastAPI
   |
   +--> Authenticate Clerk session token
   |
   +--> Resolve Clerk user ID
   |
   +--> Resolve FitnessOS local user
   |
   +--> Resolve organization/tenant
   |
   +--> Apply FitnessOS RBAC/permissions
   |
   v
PostgreSQL
```

The core principle is:

```
Clerk = Identity Provider / Authentication Authority

FitnessOS = Application User + Tenant + Authorization Authority
```

Do not move FitnessOS business authorization into Clerk unless explicitly required.

---

# 1. FIRST: UNDERSTAND THE EXISTING CODEBASE

Before changing any code, inspect the complete repository.

You must inspect at minimum:

```
backend/app/core/
backend/app/modules/auth/
backend/app/modules/rbac/
backend/app/modules/tenants/
backend/app/db/
backend/alembic/
frontend/
backend/app/config.py
backend/app/main.py
backend/README.md
repository README.md
tests/
```

Specifically identify:

```
- User model
- Organization model
- Membership model
- Role model
- Permission model
- Session model
- Refresh token model
- Auth schemas
- Auth services
- Auth dependencies
- JWT implementation
- Password hashing
- Refresh token rotation
- Logout/revocation
- Tenant resolution
- RBAC enforcement
- Frontend login/register implementation
- API client authentication
- Existing tests
- Environment variables
- Docker configuration
- Alembic migrations
```

Do not modify anything during this inspection phase.

Produce an internal implementation plan based on the actual repository.

Do not assume filenames or models that do not exist.

---

# 2. ESTABLISH THE CURRENT AUTHENTICATION FLOW

Document the existing flow.

The current system contains custom authentication functionality including:

```
- HS256 JWT access tokens
- PBKDF2-SHA256 password hashing
- refresh tokens
- server-side sessions
- access token expiration
- refresh token rotation
- bearer authentication
- current-user dependency
- organization information
- RBAC / tenant architecture
```

Trace the exact flow:

```
Registration
    ↓
User creation
    ↓
Organization creation
    ↓
Password storage
    ↓
Login
    ↓
Access token
    ↓
Refresh token
    ↓
API authentication
    ↓
Current user
    ↓
Tenant
    ↓
Permissions
```

Identify every place that depends on the custom auth implementation.

Create a dependency map before modifying code.

---

# 3. DEFINE THE TARGET ARCHITECTURE

Implement the following conceptual architecture:

```
                ┌──────────────────────┐
                │       Clerk          │
                │                      │
                │ Sign up              │
                │ Sign in              │
                │ OAuth                │
                │ Password reset       │
                │ Email verification   │
                │ MFA                  │
                │ Sessions             │
                │ Identity             │
                └──────────┬───────────┘
                           │
                     Clerk session
                           │
                           v
                ┌──────────────────────┐
                │      FastAPI         │
                │                      │
                │ Clerk verification   │
                │ Authentication       │
                │ User resolution      │
                │ Tenant resolution    │
                │ RBAC                 │
                │ Permissions          │
                └──────────┬───────────┘
                           │
                           v
                ┌──────────────────────┐
                │     PostgreSQL       │
                │                      │
                │ FitnessOS User       │
                │ Organizations        │
                │ Memberships          │
                │ Roles                │
                │ Permissions          │
                │ Gym domain data      │
                └──────────────────────┘
```

---

# 4. IMPORTANT OWNERSHIP RULES

Clerk should own:

```
- Authentication
- Passwords
- Password reset
- Email verification
- OAuth
- MFA
- Passkeys where enabled
- Authentication sessions
- Identity credentials
- Identity lifecycle
```

FitnessOS should own:

```
- Local User record
- Organization
- Gym
- Tenant
- Membership
- Trainer
- Roles
- Permissions
- RBAC
- Attendance
- Billing
- CRM
- Nutrition
- Analytics
- Subscriptions
- Inventory
- Expenses
- Notifications
- Business-specific authorization
```

Do not duplicate password management inside FitnessOS after migration.

---

# 5. USER IDENTITY MODEL

Add a stable Clerk identity reference to the local FitnessOS user model.

Preferred conceptual structure:

```
User
├── id                    UUID
├── clerk_user_id         string
├── email
├── ...
└── organization_id
```

`clerk_user_id` must be:

```
- non-null for users migrated/created through Clerk
- unique
- indexed
```

Do not use email as the permanent identity mapping.

Use:

```
clerk_user_id
```

as the external identity key.

The FitnessOS internal UUID remains the internal application user ID.

Never replace all internal UUID relationships with Clerk IDs.

---

# 6. DATABASE MIGRATION

Create an Alembic migration.

Before changing the schema:

```
1. inspect the current User table
2. inspect foreign keys
3. inspect indexes
4. inspect existing auth/session tables
5. inspect seed data
6. inspect test fixtures
```

Add:

```
clerk_user_id
```

with an appropriate unique constraint/index.

Migration strategy must support existing users.

Do NOT immediately delete:

```
password_hash
sessions
refresh-token tables
```

unless you have confirmed that no existing production/data migration path requires them.

Instead use a staged migration.

Phase 1:

```
Add clerk_user_id
Make it nullable
Deploy
```

Phase 2:

```
Backfill/migrate users
Establish Clerk identity mapping
```

Phase 3:

```
Make clerk_user_id non-null if appropriate
```

Phase 4:

```
Remove obsolete authentication tables/columns
```

This should be safe for production deployment.

---

# 7. CLERK CONFIGURATION

Use the current official Clerk Python/backend integration.

Do not blindly depend on outdated examples.

Verify the current official Clerk Python documentation and package/API recommendations before implementation.

Add environment configuration for values actually required by the current Clerk integration.

Potential configuration may include:

```
CLERK_SECRET_KEY
CLERK_PUBLISHABLE_KEY
CLERK_JWT_KEY / public key configuration
CLERK_AUTHORIZED_PARTIES
```

Use the exact configuration required by the current official SDK/integration.

Never hard-code secrets.

Never commit:

```
.env
Clerk secret keys
private keys
API secrets
```

Update:

```
backend/.env.example
```

with safe placeholders.

---

# 8. BACKEND CLERK AUTHENTICATION

Create a clean authentication abstraction.

Do not scatter Clerk SDK calls throughout business modules.

Create a dedicated authentication integration layer.

For example, conceptually:

```
backend/app/integrations/clerk/
    __init__.py
    client.py
    authentication.py
    exceptions.py
```

or adapt the existing project architecture if another structure is more appropriate.

The rest of the application should not need to know Clerk SDK implementation details.

The application should interact with an abstraction such as:

```
authenticate_request()

get_authenticated_identity()

get_current_user()
```

---

# 9. AUTHENTICATION DEPENDENCY

Replace the current custom JWT parsing dependency with Clerk-backed authentication.

Current conceptual flow:

```
Authorization: Bearer <custom JWT>
            ↓
decode_jwt()
            ↓
validate session
            ↓
load user
```

Target:

```
Authorization: Bearer <Clerk session token>
            ↓
Clerk token verification
            ↓
validate issuer / authorized party / expiration
            ↓
extract Clerk user ID
            ↓
load FitnessOS user
            ↓
resolve tenant
            ↓
apply authorization
```

The authentication dependency must:

```
- reject missing credentials
- reject malformed credentials
- verify token signature
- verify token expiration
- verify expected issuer/claims as required
- validate authorized party where applicable
- extract Clerk user ID
- resolve local FitnessOS user
- reject inactive users
- return a strongly typed authenticated user/context
```

Do not trust an unverified JWT payload.

Do not simply decode JWT base64 content without signature verification.

---

# 10. AUTHENTICATED REQUEST CONTEXT

Introduce a clear authenticated request context.

Conceptually:

```
AuthenticatedContext
```

containing:

```
clerk_user_id
fitnessos_user_id
organization_id
role
permissions
```

Do not necessarily put all values into the Clerk token.

Resolve application-specific information from FitnessOS.

Example:

```
Clerk:
    clerk_user_id = user_123

FitnessOS:
    user.id = UUID(...)
    organization_id = UUID(...)
    role = OWNER
    permissions = [...]
```

This keeps identity and authorization properly separated.

---

# 11. CURRENT USER

Preserve the existing:

```
get_current_user()
```

interface wherever possible.

The goal is that existing business endpoints continue to work without massive rewrites.

For example:

```
@router.get("/me")
async def me(
    current_user: User = Depends(get_current_user)
):
    ...
```

should continue to work.

Internally, `get_current_user()` should now resolve the user from Clerk identity.

This minimizes migration risk.

---

# 12. REGISTRATION

Do not maintain duplicate password registration logic.

Old:

```
POST /auth/register
    ↓
validate password
    ↓
hash password
    ↓
create user
    ↓
generate JWT
    ↓
generate refresh token
```

Target:

```
Clerk sign-up
    ↓
Clerk creates identity
    ↓
frontend obtains authenticated session
    ↓
backend receives authenticated request
    ↓
FitnessOS creates local User
    ↓
FitnessOS creates Organization where applicable
    ↓
return application profile/context
```

Determine whether registration should remain as a backend endpoint for onboarding/business provisioning.

If retained, it should NOT accept/store passwords.

---

# 13. USER PROVISIONING

Implement an idempotent user provisioning mechanism.

When a valid Clerk user authenticates for the first time:

```
1. extract clerk_user_id
2. find local user by clerk_user_id
3. if found:
       return existing user
4. otherwise:
       create local user
       attach appropriate organization/tenant
       assign default role
       return user
```

This operation must be safe if executed more than once.

Use database constraints to prevent duplicate users.

Do not use:

```
email-only matching
```

as the sole identity strategy.

If legacy users must be matched by email during migration, treat this as a controlled migration process and document the assumptions.

---

# 14. ORGANIZATION / TENANT HANDLING

FitnessOS already has organization and tenant concepts.

Do not accidentally break them.

The architecture must support:

```
Clerk identity
    ↓
FitnessOS User
    ↓
FitnessOS Organization
    ↓
Membership
    ↓
Role
    ↓
Permissions
```

If one Clerk identity can belong to multiple FitnessOS organizations, design for organization selection.

If the current application only supports one active organization per user, preserve that behavior initially.

Do not introduce multi-organization complexity unless the existing business requirements require it.

---

# 15. RBAC

Keep RBAC in FitnessOS.

Do not replace the existing:

```
roles
permissions
organization membership
tenant checks
```

with Clerk authentication.

Authentication answers:

```
"Who are you?"
```

Authorization answers:

```
"What can you do?"
```

FitnessOS must remain responsible for the second question.

Example:

```
Clerk:
    user = user_123

FitnessOS:
    user_123 -> organization ABC
    user_123 -> role TRAINER
    TRAINER -> attendance.read
    TRAINER -> members.read
    TRAINER -> billing.read = false
```

The API must enforce FitnessOS permissions.

---

# 16. API AUTHORIZATION

Audit every protected endpoint.

For each endpoint identify:

```
- authentication requirement
- organization requirement
- role requirement
- permission requirement
- object-level authorization
- tenant isolation requirement
```

Make sure authenticated users cannot access another organization's data simply by changing an ID in the request.

Test:

```
User A -> Organization A
User B -> Organization B
```

User A must NOT be able to access:

```
Organization B members
Organization B attendance
Organization B billing
Organization B trainers
Organization B analytics
```

even if User A knows the database UUID.

---

# 17. FRONTEND AUTHENTICATION

Inspect the current frontend authentication implementation before modifying it.

Replace custom login/register/session handling with the appropriate Clerk frontend integration.

Use Clerk's official frontend SDK for the actual frontend framework used by FitnessOS.

The frontend should be responsible for:

```
- sign in
- sign up
- sign out
- authentication UI
- session state
```

The backend should remain responsible for:

```
- token verification
- application user resolution
- tenant resolution
- RBAC
- business authorization
```

Do not store long-lived authentication secrets in browser localStorage unless explicitly required by the framework/integration.

Prefer the official Clerk session mechanism.

---

# 18. API CLIENT

Update the frontend API client.

Every authenticated API request must include the current Clerk session token using the officially recommended integration pattern.

Avoid manually implementing:

```
refresh token rotation
JWT refresh
password storage
session persistence
```

if Clerk already handles those responsibilities.

Do not create duplicate auth state machines.

---

# 19. LOGOUT

Remove application-owned refresh-token logout logic once Clerk owns sessions.

Frontend:

```
Clerk signOut()
```

Backend:

```
verify Clerk session
```

Do not pretend that deleting a local application refresh token is equivalent to revoking the Clerk session.

If FitnessOS needs an application-level forced logout mechanism, implement it separately, e.g.:

```
user.is_active = false
```

or:

```
user.auth_version
```

or:

```
session_invalidated_at
```

depending on the requirements.

---

# 20. SESSION MANAGEMENT

Determine which existing session functionality becomes obsolete.

Current custom system contains server-side session validation.

Do not immediately remove it.

First identify all consumers.

If no application functionality requires the custom session table after migration:

```
mark it deprecated
migrate production
remove it in a later migration
```

Do not create two competing session authorities.

The desired final state is:

```
Clerk = authentication session authority

FitnessOS = application authorization/user state
```

---

# 21. PASSWORDS

After Clerk migration:

FitnessOS must NOT:

```
- store plaintext passwords
- hash passwords
- verify passwords
- implement password reset
- implement password recovery
```

Remove PBKDF2/password code only after migration is proven safe.

The old password code should not remain as an alternative authentication mechanism accidentally.

If legacy password authentication must temporarily remain:

```
explicitly feature-flag it
document it
add a migration path
plan its removal
```

---

# 22. BACKWARD COMPATIBILITY

Avoid unnecessary API breaking changes.

Where possible preserve:

```
/api/v1/auth/me
```

and existing response structures.

If endpoints become obsolete, document:

```
old endpoint
replacement
migration reason
frontend impact
```

Do not break every API consumer merely because the authentication provider changed.

---

# 23. WEBHOOKS / IDENTITY SYNCHRONIZATION

Evaluate whether FitnessOS should consume Clerk webhooks.

Potential events include:

```
user.created
user.updated
user.deleted
```

Only implement webhook synchronization where it provides actual value.

If webhooks are used:

```
- verify webhook signatures
- make processing idempotent
- handle retries
- never trust arbitrary webhook payloads
- log event IDs
- prevent duplicate processing
```

A webhook should update local application metadata.

It should not blindly overwrite FitnessOS business data.

---

# 24. USER DELETION

Define the lifecycle explicitly.

When a Clerk user is deleted:

```
What happens to FitnessOS User?
```

Possible approaches:

```
soft-delete
deactivate
anonymize
cascade
```

Do not implement destructive cascading without understanding the business requirements.

Gym records may need to remain for:

```
billing
attendance
compliance
reporting
audit
```

Prefer soft deletion where appropriate.

---

# 25. SECURITY REQUIREMENTS

Treat authentication as security-critical code.

Never:

```
- trust decoded JWT payloads without verification
- trust client-provided user IDs
- trust client-provided organization IDs
- trust client-provided roles
- accept arbitrary permissions
- store secrets in source control
- log authentication tokens
- log passwords
- expose Clerk secret keys
- bypass signature validation
- disable SSL verification
- weaken token validation for tests in production code
```

Validate:

```
issuer
expiration
signature
authorized party where required
token type / expected claims where applicable
```

Use secure HTTP error handling.

Avoid leaking whether an email/account exists during authentication flows where that would create account-enumeration risk.

---

# 26. ERROR HANDLING

Create consistent authentication errors.

Examples:

```
401 Unauthorized
    Missing authentication
    Invalid token
    Expired token
    Unknown Clerk identity

403 Forbidden
    Authenticated but insufficient permissions
    Tenant access denied
```

Do not return:

```
"user exists"
"email registered"
"wrong password"
```

in ways that unnecessarily expose account information.

Keep API error responses consistent with the existing FitnessOS conventions.

---

# 27. OBSERVABILITY

Add safe authentication logging.

Log:

```
request ID
endpoint
authentication result
local user ID where appropriate
organization ID where appropriate
failure category
```

Do NOT log:

```
access tokens
refresh tokens
passwords
Clerk secret keys
Authorization headers
```

Use structured logging if the project already supports it.

---

# 28. TEST STRATEGY

Before modifying authentication, capture the existing behavior with tests.

Then add tests for:

### Authentication

```
valid Clerk token
expired token
invalid signature
missing token
malformed token
wrong issuer
invalid authorized party
unknown Clerk user
```

### User mapping

```
existing local user
first-time Clerk user
duplicate Clerk user
inactive local user
```

### Tenant isolation

```
organization A -> organization A
organization A -> organization B = denied
```

### RBAC

```
owner
admin
trainer
staff
member
```

Test both:

```
authenticated + authorized
```

and:

```
authenticated + unauthorized
```

### Logout/session

Test Clerk session behavior according to the integration.

### Webhooks

If implemented:

```
valid webhook
invalid signature
duplicate event
retry
unknown event
```

---

# 29. INTEGRATION TESTS

Create end-to-end authentication tests.

Test:

```
Clerk identity
   ↓
API request
   ↓
authentication dependency
   ↓
local user
   ↓
organization
   ↓
RBAC
   ↓
business endpoint
```

At least test:

```
GET /api/v1/auth/me
```

and representative protected endpoints from:

```
membership
attendance
billing
trainer
nutrition
analytics
```

---

# 30. MIGRATION PLAN FOR EXISTING USERS

Do not assume all existing users are disposable.

Create a migration strategy.

Possible approach:

```
Existing user
    ↓
Create/link Clerk identity
    ↓
Store clerk_user_id
    ↓
Existing FitnessOS UUID remains unchanged
    ↓
Existing organization remains unchanged
    ↓
Existing memberships remain unchanged
    ↓
User signs in through Clerk
```

The migration must not break historical records.

Do not change:

```
attendance.user_id
billing.user_id
trainer.user_id
membership.user_id
```

just because authentication changes.

---

# 31. DATA INTEGRITY

Before database migrations, inspect all foreign keys.

Ensure:

```
User UUID remains stable
```

The following should continue referencing the FitnessOS User:

```
attendance
billing
membership
CRM
trainer
nutrition
notifications
analytics
```

Clerk ID is an external identity mapping.

It should NOT become the primary key of the FitnessOS domain model.

---

# 32. ENVIRONMENT CONFIGURATION

Update:

```
backend/.env.example
deployment configuration
Docker configuration
CI/CD secrets documentation
```

Never commit actual credentials.

Document:

```
Clerk application setup
development environment
staging environment
production environment
```

Make sure development and production Clerk instances/configurations are separated appropriately.

---

# 33. LOCAL DEVELOPMENT

The authentication system must remain developer-friendly.

Document:

```
1. Create Clerk development application
2. Configure environment variables
3. Start backend
4. Start frontend
5. Sign up test user
6. Verify local FitnessOS user provisioning
7. Verify organization creation
8. Verify protected API request
9. Verify RBAC
```

Do not require developers to manually generate JWTs.

---

# 34. PRODUCTION DEPLOYMENT

Create a production-safe rollout plan.

Recommended rollout:

```
Phase 1
    Add Clerk dependencies/configuration

Phase 2
    Add clerk_user_id

Phase 3
    Implement Clerk authentication abstraction

Phase 4
    Add tests

Phase 5
    Integrate frontend

Phase 6
    Enable Clerk authentication

Phase 7
    Migrate existing users

Phase 8
    Monitor errors

Phase 9
    Remove custom password authentication

Phase 10
    Remove obsolete session/refresh-token infrastructure
```

Do not perform destructive cleanup in the first deployment.

---

# 35. PERFORMANCE

Do not introduce unnecessary network calls on every API request.

Prefer the official Clerk verification mechanism appropriate for the architecture.

If networkless JWT verification is supported and appropriate:

```
verify locally using Clerk's signing/public key
```

instead of:

```
API request to Clerk for every backend request
```

However, follow the current official Clerk guidance and security requirements.

Authentication must remain fast enough for high-volume gym APIs.

---

# 36. CACHING

Do not cache authorization decisions incorrectly.

If caching user/organization/permission information:

```
include user identity
include organization identity
define TTL
invalidate when role changes
invalidate when user is disabled
```

Never allow cached authorization information to cause cross-tenant access.

---

# 37. RATE LIMITING

Authentication migration must not remove API protections.

Maintain or introduce rate limiting for sensitive endpoints such as:

```
registration/onboarding
authentication callbacks
webhook endpoints
password-related operations if any remain
high-risk account operations
```

Do not rate-limit normal authenticated API traffic in a way that breaks gym operations.

---

# 38. SECURITY REVIEW

After implementation, perform a security review specifically for:

```
authentication bypass
tenant bypass
privilege escalation
JWT validation
organization spoofing
user ID spoofing
role spoofing
webhook spoofing
account enumeration
token leakage
secret leakage
session confusion
CORS
CSRF where relevant
cookie configuration where relevant
```

Pay particular attention to:

```
"authenticated user A requests organization B"
```

and:

```
"authenticated user A changes user_id in request body"
```

Both must be rejected unless explicitly authorized.

---

# 39. DO NOT OVER-ENGINEER

Do not introduce:

```
microservices
event buses
Redis
Kafka
service mesh
custom identity gateway
```

just because Clerk is being added.

Use the existing FitnessOS architecture.

Keep the authentication boundary clean and simple.

---

# 40. CODE QUALITY

Follow existing repository conventions.

Before adding code:

```
inspect existing patterns.
```

Do not create duplicate utilities.

Do not create:

```
three different current-user dependencies
multiple Clerk clients
multiple auth abstractions
duplicate permission systems
```

Prefer one clear authentication entry point.

Use:

```
type hints
async patterns already used by project
existing dependency injection
existing exception handling
existing database session patterns
```

---

# 41. DOCUMENTATION

Update project documentation.

Include:

```
Architecture
Clerk setup
Environment variables
Local development
Production setup
User provisioning
User migration
RBAC behavior
Tenant behavior
Troubleshooting
Security considerations
```

Explain clearly:

```
Clerk authenticates users.

FitnessOS authorizes users.
```

---

# 42. FINAL TARGET STRUCTURE

The final architecture should conceptually resemble:

```
frontend/
    Clerk authentication
    API client
    application UI

backend/
    app/
        integrations/
            clerk/
                client.py
                authentication.py
                exceptions.py

        modules/
            auth/
                dependencies.py
                service.py
                schemas.py

            users/

            tenants/

            rbac/

            membership/

            attendance/

            billing/

            trainer/

            nutrition/

            analytics/

        core/
            permissions.py
            tenancy.py

        db/

    alembic/
```

The exact file structure must follow the repository's existing conventions.

---

# 43. IMPORTANT: DO NOT DELETE CURRENT AUTH IMMEDIATELY

The current custom authentication system must be treated as legacy during migration.

First:

```
understand
```

then:

```
integrate Clerk
```

then:

```
migrate
```

then:

```
test
```

then:

```
remove obsolete functionality
```

Do not delete:

```
security.py
auth service
session models
refresh token logic
password logic
```

until you have established exactly which pieces are obsolete.

---

# 44. IMPLEMENTATION ORDER

Execute in this order:

## STEP 1 — Repository audit

Inspect the complete auth/tenant/RBAC architecture.

Deliver:

```
- current auth flow
- affected files
- database dependencies
- frontend dependencies
- migration risks
```

Do not modify code yet.

## STEP 2 — Clerk integration design

Define:

```
- Clerk identity mapping
- local User mapping
- authentication dependency
- organization handling
- RBAC handling
```

Do not modify business logic unnecessarily.

## STEP 3 — Database migration

Add:

```
clerk_user_id
```

Create Alembic migration.

Test migration up/down.

## STEP 4 — Backend Clerk integration

Implement the Clerk authentication abstraction.

Replace custom JWT verification only at the authentication boundary.

## STEP 5 — User provisioning

Implement idempotent local-user provisioning.

## STEP 6 — Current-user dependency

Make:

```
get_current_user()
```

Clerk-backed.

Preserve downstream API compatibility.

## STEP 7 — Frontend

Integrate Clerk authentication.

Replace custom frontend auth state.

## STEP 8 — API client

Send Clerk session token to FastAPI.

## STEP 9 — Authorization audit

Review every protected endpoint for:

```
authentication
authorization
tenant isolation
```

## STEP 10 — Tests

Run:

```
unit tests
integration tests
migration tests
authorization tests
```

## STEP 11 — Legacy cleanup

Only after successful migration:

```
remove password authentication
remove custom JWT creation
remove refresh-token implementation
remove obsolete session handling
remove unused schemas/endpoints
```

## STEP 12 — Documentation

Update README and deployment documentation.

---

# 45. DEFINITION OF DONE

The implementation is complete only when:

```
[ ] Clerk authentication works locally

[ ] Clerk authentication works in staging

[ ] Backend verifies Clerk tokens correctly

[ ] Invalid tokens are rejected

[ ] Expired tokens are rejected

[ ] Clerk user maps to FitnessOS User

[ ] Duplicate users cannot be created

[ ] Existing FitnessOS UUID relationships remain intact

[ ] Organizations remain intact

[ ] Tenant isolation works

[ ] RBAC works

[ ] Existing protected APIs work

[ ] Frontend authentication works

[ ] Logout works

[ ] User provisioning is idempotent

[ ] Existing users have a migration path

[ ] No passwords are stored by FitnessOS after migration

[ ] No authentication secrets are committed

[ ] Tokens are never logged

[ ] Webhooks are verified if implemented

[ ] Authentication tests pass

[ ] Authorization tests pass

[ ] Migration tests pass

[ ] Existing business tests pass

[ ] Documentation is updated

[ ] Obsolete custom authentication code is removed only after migration
```

---

# 46. FINAL VALIDATION COMMANDS

Before declaring completion, run the repository's actual test/lint/type-check commands.

At minimum verify:

```
tests
lint
formatting
type checking
Alembic migration
backend startup
frontend build
```

Do not claim success unless the commands actually pass.

If a command fails:

```
identify the failure
fix it
rerun it
```

Do not hide failing tests.

---

# 47. OUTPUT REQUIRED FROM THE CODING AGENT

At the end provide a concise implementation report containing:

## Changed

List files changed.

## Database

List migrations and schema changes.

## Authentication

Explain the new Clerk flow.

## Authorization

Explain how FitnessOS RBAC remains responsible for authorization.

## Frontend

Explain authentication changes.

## Legacy Auth

List what was removed and what remains temporarily.

## Tests

List commands executed and their results.

## Security

List security checks performed.

## Migration

Explain how existing users are migrated.

## Remaining Work

List anything intentionally not completed.

---

# MOST IMPORTANT ARCHITECTURAL RULE

Do not think of this migration as:

```
"Replace FitnessOS users with Clerk users."
```

Think of it as:

```
"Replace FitnessOS authentication with Clerk authentication while preserving FitnessOS users and authorization."
```

The final relationship should be:

```
Clerk User
     |
     | clerk_user_id
     v
FitnessOS User
     |
     v
Organization / Tenant
     |
     v
Membership
     |
     v
Role
     |
     v
Permissions
     |
     v
FitnessOS Business Data
```

This separation must remain intact.

Do not compromise tenant isolation or authorization correctness for implementation convenience.
