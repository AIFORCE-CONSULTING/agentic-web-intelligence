# Identity foundation

Phase 4 begins with a local-first authentication boundary that can later use an
enterprise OpenID Connect provider.

## Local deployment

Set `AUTH_BOOTSTRAP_SECRET` to a unique value of at least 32 characters before
starting the API. Use it once with `POST /v1/auth/bootstrap` to create the
first administrator and default workspace. There are no default credentials and
public registration is disabled.

Local passwords are stored as Argon2 hashes. The API issues an opaque, random
session in an HttpOnly cookie; only its hash is stored in PostgreSQL. Sessions
expire after eight hours and are revoked on sign-out.

## API

- `POST /v1/auth/bootstrap` — one-time local administrator bootstrap
- `POST /v1/auth/sign-in` — local credential sign-in
- `POST /v1/auth/sign-out` — revoke the current session
- `GET /v1/auth/me` — current user and default workspace role

This is an authentication foundation, not authorization. Existing Phase 2 and
Phase 3 endpoints retain their current access behavior until the next Phase 4
authorization increment deliberately scopes them to an authenticated workspace.

## Enterprise compatibility

The platform will add a configuration-driven OIDC adapter rather than choosing
a single vendor. This supports self-hosted providers such as Keycloak and
enterprise providers such as Entra, Okta, and Auth0. Provider groups may later
map to platform roles, but the platform remains the final authorization point.
