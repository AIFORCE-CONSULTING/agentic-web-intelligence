# ADR 0002: Use React and FastAPI at the application boundary

- Status: Accepted
- Date: 2026-08-09

## Context

The platform needs an operator-grade interface and a backend aligned with the Python AI ecosystem.

## Decision

Use React with TypeScript for user-facing applications and FastAPI with Python for the platform API, agent runtime integration, and backend services.

## Consequences

The frontend remains independent of agent and provider implementation details. FastAPI exposes stable API contracts and centralizes authentication, authorization, and orchestration boundaries.
