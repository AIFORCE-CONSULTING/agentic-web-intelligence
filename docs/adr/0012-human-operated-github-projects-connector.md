# ADR 0012: Keep GitHub Project management human-operated and narrowly scoped

- Status: Accepted
- Date: 2026-09-04

## Context

The platform needs an efficient way to maintain a roadmap in GitHub Projects.
The existing secret registry, workspace roles, service identities, and tool
registry make it possible to integrate safely, but a broad GitHub client or
agent-visible GitHub MCP server would grant more authority than the roadmap
feature needs.

## Decision

The API owns a server-only connector pinned to one organization Project by
deployment configuration. Its first capabilities are limited to listing and
creating Project draft items and updating the existing `Priority` single-select
field. It cannot create repository Issues, Projects, views, fields, or other
GitHub resources.

The connector resolves its token only from the allowlisted deployment secret
provider. Only authenticated human administrators and operators receive the
fixed `github.projects.manage` permission. Service identities, MCP clients,
and agents receive no GitHub Project capability. Successful mutations record a
minimal, schema-gated security audit event without titles, bodies, upstream
responses, or credentials.

## Consequences

Operators gain a practical roadmap panel without turning GitHub into a general
agent tool. A future agent-facing integration requires a separate decision,
tool-registry entry, narrow contract, and approval policy; it must not reuse
this human-operated connector implicitly.
