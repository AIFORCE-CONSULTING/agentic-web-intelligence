# ADR 0001: Begin with a monorepo

- Status: Accepted
- Date: 2026-08-09

## Context

The initial platform needs coordinated development across React, FastAPI, MCP adapters, documentation, and local infrastructure.

## Decision

Begin with a monorepo organized by deployable application and shared package boundaries.

## Consequences

Contributors can run the integrated stack locally with one checkout. Independent release or access-control needs can justify later extraction, but directory boundaries must remain clear from the start.
