# Authentication & Authorization

**Clerk authenticates users. FitnessOS authorizes them.**

Clerk is the identity provider and session authority. It owns sign-up, sign-in,
passwords, password reset, email verification, OAuth and MFA. FitnessOS owns the
local user record, the organization tenant, memberships, roles, permissions and
every business rule that follows from them.

Clerk never decides what a user may do. FitnessOS never stores a password.

## Request flow

```
Authorization: Bearer <Clerk session token>
        |
        v
ClerkClient.verify_session_token()      app/integrations/clerk/client.py
        |  RS256 signature (JWKS or configured PEM, cached per process)
        |  iss == CLERK_ISSUER
        |  exp / iat / nbf, with CLERK_JWT_LEEWAY_SECONDS of skew
        |  azp is in CLERK_AUTHORIZED_PARTIES
        v
identity_from_claims() -> ClerkIdentity  app/integrations/clerk/authentication.py
        |
        v
provision_user_from_identity()           idempotent; keyed on clerk_user_id
        |
        v
get_current_user() -> User               app/modules/auth/dependencies.py
        |
        v
get_auth_context() -> AuthenticatedContext
        |  organization_id, role_slugs, permissions — all read from PostgreSQL
        v
require_permission("billing:manage")     app/modules/rbac/dependencies.py
```

`azp`, not `aud`. Clerk session tokens carry no `aud` claim, so the authorized
party is validated explicitly rather than through JWT audience validation.
Verification is networkless after the first JWKS fetch.

## Identity mapping

```
Clerk user (user_2abc…)
   |  users.clerk_user_id   TEXT, indexed, uniquely partial-indexed
   v
FitnessOS User (UUID)  <-- the primary key every domain table references
   |
   v
Organization -> Membership -> Role -> Permission -> business data
```

`clerk_user_id` is an external mapping only. The FitnessOS UUID is unchanged by
this migration, so `attendance.user_id`, `billing.user_id`, `membership.user_id`
and `trainer.user_id` keep pointing at the same rows they always did.

Email is never the identity key. It is stored for display and may be absent from
a Clerk token, in which case a stable `clerk-<id>@local.invalid` placeholder is
recorded until a webhook or profile update supplies the real address.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/auth/me` | The authenticated user. Unchanged response shape, plus `clerk_user_id`. |
| `GET /api/v1/auth/context` | Identity with resolved organization, roles and permissions. |
| `POST /api/v1/auth/onboarding` | Creates the tenant for a Clerk user and makes them owner. Replaces password registration. |
| `POST /api/v1/auth/register` | Legacy. 404 unless `LEGACY_PASSWORD_AUTH_ENABLED`. |
| `POST /api/v1/auth/login` | Legacy. 404 unless `LEGACY_PASSWORD_AUTH_ENABLED`. |
| `POST /api/v1/auth/refresh` | Legacy. 404 unless `LEGACY_PASSWORD_AUTH_ENABLED`. |
| `POST /api/v1/auth/logout` | Legacy. 404 unless `LEGACY_PASSWORD_AUTH_ENABLED`. |

### Logout

There is no backend logout. The frontend calls Clerk's `signOut()`, which is
what actually ends the session. Deleting a FitnessOS refresh token never revoked
a Clerk session and must not be presented as if it did.

For an application-level forced logout, set `users.is_active = false`. The
authentication dependency rejects inactive users on the next request.

## Provisioning

The first time a valid Clerk identity reaches the API, a local user is created
with no organization. Onboarding then creates the tenant and assigns the owner
role. Provisioning is idempotent: concurrent first requests both converge on one
row because the partial unique index on `clerk_user_id` rejects the loser, which
re-reads the winner.

If another local user already holds the incoming email and is not eligible for
migration linking, provisioning refuses with 409 rather than creating a shadow
account or taking over the existing one.

## Migrating pre-Clerk users

Existing users keep their UUID, organization, memberships and history. Only the
identity mapping is added.

1. Create each existing user in Clerk (dashboard or Backend API), using their
   existing email address.
2. Set `CLERK_LINK_EXISTING_USERS_BY_EMAIL=true`.
3. Users sign in through Clerk. On first authenticated request, the local user
   with the matching **verified** email is linked: `clerk_user_id` is written
   and a `clerk` auth method is bound. The UUID does not change.
4. When the backlog is linked, set the flag back to `false`.

The flag is off by default because email is not a trustworthy permanent identity
key. While off, an email collision is refused rather than linked. Even while on,
linking never touches a user that already has a `clerk_user_id`, and never acts
on an unverified email.

## Configuration

See `backend/.env.example`. `CLERK_ISSUER` and `CLERK_AUTHORIZED_PARTIES` are
both required; the integration refuses to authenticate without them rather than
falling back to weaker validation. Use separate Clerk instances for development,
staging and production — their issuers differ, so a token from one is rejected
by the others.

`CLERK_AUTHORIZED_PARTIES` doubles as the CORS allowlist, keeping the accepted
`azp` values and the accepted browser origins in agreement.

## Local development

1. Create a Clerk **development** application.
2. Copy `backend/.env.example` to `backend/.env` and fill in
   `CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `CLERK_ISSUER`,
   `CLERK_JWKS_URL` and `CLERK_AUTHORIZED_PARTIES`.
3. `cd backend && uv run alembic upgrade head`
4. `uv run uvicorn app.main:app --reload`
5. Sign up through your Clerk frontend and call
   `GET /api/v1/auth/me` with the session token from `getToken()`.
6. `POST /api/v1/auth/onboarding` to create the tenant.
7. `GET /api/v1/auth/context` to confirm the owner role and permissions.

You never need to hand-craft a JWT. The test suite mints Clerk-shaped tokens
from a throwaway RSA key (`tests/conftest.py`), so tests need no Clerk account.

## Security notes

- Token payloads are never trusted before signature verification. The unverified
  header is read only to route a token to the legacy or Clerk verifier; both
  verify in full.
- `organization_id`, roles and permissions come from PostgreSQL, never from a
  token claim, so they cannot be spoofed by a client.
- Tokens, refresh tokens, passwords and `Authorization` headers are never
  logged. Authentication logs carry a failure category, endpoint, request id and
  the resolved user and organization ids only.
- Rate limiting on onboarding is per worker process. Put an edge rate limiter in
  front of a multi-worker deployment.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Every token 401s | `CLERK_ISSUER` does not exactly match the token's `iss`, or `CLERK_AUTHORIZED_PARTIES` omits the frontend origin. |
| 401 right after switching environments | Token minted by a different Clerk instance. |
| 409 on first sign-in | An existing local user holds that email and linking is off. Link deliberately, or resolve the duplicate. |
| 403 on every business endpoint | The user has no organization. Call `POST /api/v1/auth/onboarding`. |
| `invalid input value for enum authprovider: "clerk"` | Migrations are behind. Run `alembic upgrade head`. |
