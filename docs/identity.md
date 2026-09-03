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
- `GET /v1/auth/enterprise/status` — credential-free enterprise OIDC configuration status

## Authorization and workspace isolation

The platform owns a fixed role policy rather than accepting permissions from a
browser or agent instruction:

- **Administrator** — all current workspace capabilities, including MCP audit history.
- **Operator** — create, retrieve, and extend governed research; use approved MCP tools;
  inspect runtime runs.
- **Viewer** — retrieve workspace research and inspect runtime runs only.

Durable research runs, runtime runs, and MCP audit records are written with the
authenticated session's workspace ID. Reads filter by that same ID, so a valid
session from another workspace receives the same not-found result as an unknown
record. Browser sessions also store their selected workspace server-side; a
membership change cannot be supplied by a caller or agent as request text.

Pre-existing durable records without a workspace ID are deliberately excluded
from authenticated reads rather than guessed into a workspace. A future
administrator migration tool can assign them explicitly when that is safe.

Health checks, API documentation, and the prompt/tool catalogs remain public.
The actions that consume tools or access durable platform records require an
authenticated session and the appropriate workspace role.

## Security audit trail

`GET /v1/audit/security` gives a workspace administrator a bounded,
reverse-chronological record of security decisions in that workspace. The
platform records successful bootstrap, sign-in, and sign-out events, plus
denied authentication and authorization attempts. Events include the acting
user when known, workspace, event type, outcome, and timestamp. They do not
store passwords, bootstrap secrets, raw session tokens, or attempted email
addresses.

Audit persistence is intentionally non-blocking for an access decision: if the
audit database is unavailable, authentication and authorization still enforce
their rules rather than falling open. The service health endpoint continues to
expose persistence availability to operators.

## Administrator console

The local web console exposes this read-only first slice at `/admin`. It
supports first-time bootstrap and local sign-in, displays the active identity
and workspace role, permits sign-out, and shows the security audit only to an
administrator. User creation, invitations, role changes, session management,
and an enterprise-identity configuration UI remain later administration increments.

## Enterprise identity boundary

The platform has a provider-neutral, server-only OIDC configuration boundary.
It supports self-hosted providers such as Keycloak and enterprise providers
such as Entra, Okta, and Auth0 without making one of them a platform dependency.

An operator enables the boundary by providing all of these server environment
variables together:

- `OIDC_ISSUER_URL` — the provider's issuer URL; HTTPS is required outside localhost.
- `OIDC_CLIENT_ID` and `OIDC_CLIENT_SECRET` — confidential-client credentials.
- `OIDC_REDIRECT_URI` — the future API callback address; HTTPS is required outside localhost.
- `OIDC_PROVIDER_NAME` — optional operator-facing label.

The API validates the configuration shape and exposes only its safe state at
`GET /v1/auth/enterprise/status`. It never returns the client secret, and it
does not contact the configured issuer merely to report status. This means a
local installation stays fully functional with no enterprise identity provider.

This is deliberately not an SSO login implementation yet: there is no browser
redirect, authorization-code exchange, token validation, account provisioning,
or group-to-role mapping. The next adapter increment must validate discovery
and ID-token issuer/audience/signature/nonce server-side, map the immutable
issuer-plus-subject identity to a platform user, and then issue the same
platform-owned session used by local sign-in. Provider groups can inform a
mapping, but the platform remains the final authorization point.
