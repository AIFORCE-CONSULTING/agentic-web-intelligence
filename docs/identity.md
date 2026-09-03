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

## Enterprise compatibility

The platform will add a configuration-driven OIDC adapter rather than choosing
a single vendor. This supports self-hosted providers such as Keycloak and
enterprise providers such as Entra, Okta, and Auth0. Provider groups may later
map to platform roles, but the platform remains the final authorization point.
