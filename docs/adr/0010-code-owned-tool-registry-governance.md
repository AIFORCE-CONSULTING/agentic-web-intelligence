# ADR 0010: Govern tools through a code-owned registry

- Status: Accepted
- Date: 2026-09-04

## Context

The platform's web MCP host already restricts agents to two approved tools, but
future connectors could bypass that intent if their permission, secret, audit,
and contract requirements were scattered through endpoint code.

## Decision

Every tool callable through the MCP host is registered in code with its name,
owner, purpose, fixed workspace permission, input schema, output contract,
secret dependencies, enabled-by-default state, and audit requirement. The host
uses that registry for discovery, invocation, secret-configuration checks, and
permission selection. Unknown or disabled tools are denied.

The agent-visible tools endpoint remains deliberately small. A separate,
administrator-only registry endpoint exposes safe governance metadata without
credentials. A registry entry is necessary but not sufficient to implement a
future connector: its provider-specific behavior requires its own approved
capability contract.

## Consequences

New tools cannot become reachable merely by adding a route or calling a
provider library. They must state their authority and audit semantics at the
registry boundary. This creates a reusable approval point for future GitHub,
messaging, document, and model-provider connectors without granting agents
direct access to their credentials.
