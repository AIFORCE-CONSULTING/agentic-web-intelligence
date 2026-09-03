# ADR 0006: Use local-first identity with an enterprise OIDC boundary

- Status: Accepted
- Date: 2026-09-03

## Context

The platform must be safe to download and run locally without a commercial
identity provider, while remaining suitable for organizations that require SSO,
MFA, and integration with an existing identity stack.

## Decision

Phase 4 begins with local authentication backed by PostgreSQL. A deployment
operator supplies `AUTH_BOOTSTRAP_SECRET` to create the first administrator;
there are no default credentials or public registration. Local passwords use
Argon2 hashes. Browser authentication uses opaque, random session tokens held
in an HttpOnly cookie and stored only as hashes, enabling server-side expiry and
revocation.

Each local installation begins with one default workspace and its bootstrap user
as workspace administrator. The platform owns workspace roles and authorization.

Enterprise login will use a configuration-driven OpenID Connect adapter. An
external provider proves identity; the platform maps the immutable issuer and
subject to its own user, workspace membership, and role. The provider is not
required for local operation and is not implemented as a fallback password
flow.

## Consequences

The initial slice provides bootstrap, sign-in, sign-out, and current-user
endpoints only. It does not make existing Phase 2 or 3 endpoints private yet;
authorization is the next Phase 4 increment. Password recovery, invitations,
service identities, multi-workspace administration, and OIDC configuration UI
remain separate scoped work.
