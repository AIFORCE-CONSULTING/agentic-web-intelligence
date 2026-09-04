# ADR 0011: Fail safely and expose an administrator-only security posture

- Status: Accepted
- Date: 2026-09-04

## Context

Phase 4 introduced identity, service identities, secret handling, and tool
governance. A deployment should not start with known unsafe configuration, and
operators need one safe view of the resulting posture without receiving
credentials or raw identity data.

## Decision

The API validates critical deployment configuration during application creation:
the environment is allowlisted, a supplied bootstrap secret has a minimum
length, production browser origins use HTTPS, and OIDC values are complete as a
set. It adds baseline browser security headers to every response and no-store
to security-sensitive responses.

An administrator-only operations endpoint reports identity/audit persistence
readiness, safe secret status, enterprise identity status, and tool registry
metadata. It never returns secret values. The Phase 4 runbook defines the
local end-to-end validation sequence.

## Consequences

Known insecure configurations fail before serving traffic, while optional local
components can remain unconfigured for development. Operators gain a bounded
posture view without turning a health endpoint into a source of credentials.
Production-specific network and infrastructure controls remain a Phase 7
deployment concern.
