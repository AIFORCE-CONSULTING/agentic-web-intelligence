# ADR 0008: Use revocable, least-privilege service identities

- Status: Accepted
- Date: 2026-09-04

## Context

The platform will eventually have independent workers, schedulers, and
integrations that need to call the API without impersonating a person. Browser
sessions and agent instructions cannot provide that authority safely.

## Decision

The platform issues opaque service tokens only when a workspace administrator
creates a named service identity with an explicit, server-defined subset of
research, runtime, and MCP permissions. The raw token is returned once and
stored only as a hash. It is sent through the standard Bearer header, is bound
to one workspace, and can be revoked immediately.

Service identities cannot receive administrator, security-audit, or
service-identity-management permission. They are distinct from human users and
from agent runtime roles. Creation, authorization denials, and revocation are
audited with a service-identity actor field where applicable.

## Consequences

Future independently deployed platform components can authenticate with narrow,
revocable credentials. The existing monolithic API does not create or use a
service token for its own internal calls. Token rotation, expiry, multiple
credential versions, and a management UI remain separate increments.
