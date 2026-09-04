# ADR 0009: Centralize deployment secrets behind an allowlisted provider

- Status: Accepted
- Date: 2026-09-04

## Context

Bootstrap, enterprise identity, and future connector credentials must be
available to trusted server code without being copied into browser responses,
agent state, prompts, logs, or durable records. Local open-source deployments
also need to work without a cloud secret manager.

## Decision

The API owns a fixed secret registry and initially resolves it only from
deployment environment variables. The registry exposes values only to
server-side code, emits credential-free configured/missing status, and
recursively redacts all configured values before audit and runtime persistence.
Security audit events also use a code-owned allowlist of scalar detail fields;
unknown events, nested data, and sensitive field names are rejected before
persistence.
Requests cannot dynamically select an environment-variable name.

The first entries are the bootstrap secret, OIDC client secret, and reserved
GitHub connector token. A future vault adapter must implement the same narrow
provider interface; it must not expose arbitrary secret lookup to tools,
agents, or clients.

## Consequences

Local .env deployment remains supported while the platform has a clear path to
managed-vault integration. Secret values do not appear in the status endpoint
or security audit trail. Connector implementation remains separate: registering
a credential does not make a connector or tool available.
