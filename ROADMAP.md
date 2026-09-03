# Roadmap

## Phase 1 - Foundation

- Repository scaffold and contribution standards
- React + FastAPI application boundaries
- Docker Compose local environment
- MkDocs Material documentation site
- Architecture Decision Records
- CI validation and repository templates

## Phase 2 - Governed Web Intelligence

Deliver an evidence-producing web-research workflow through a governed MCP boundary.

- LangGraph workflow with approved web-search and extraction tools
- MCP host, source provenance, basic tool policy, and execution audit history
- Developer and operator portal for the console, API reference, documentation, and service health
- Publish the MkDocs documentation site with GitHub Pages

## Phase 3 - Agent Runtime (complete)

- Server-only LangGraph planning, execution, and review workflows
- Fixed roles and capabilities, typed state, policy-validated handoffs, and audit events
- Run-scoped, expiring provenance memory
- Bounded reviewer-to-researcher revision pattern with safe escalation

## Phase 4 - Enterprise Services

Add authentication, authorization, tool registry, secrets, and governance.

## Post-Phase-4 Parking Lot

These items are intentionally captured for the next planning pass. They do not
expand the active Phase 4 scope or replace the existing Durable Execution
roadmap phase.

1. **GitHub Projects integration** — connect the platform's planning workflow
   to GitHub Projects so an operator can build a roadmap, create tasks, and
   update their priority quickly.
2. **Source-candidate review usability** — make each source candidate URL a
   clickable external link that opens in a new browser tab, and request/display
   longer article descriptions so an operator has more context before choosing
   a source for extraction.

## Phase 5 - Durable Execution

Add Temporal, long-running workflows, and human-in-the-loop operations.

## Phase 6 - Observability

Add LangFuse, OpenTelemetry, metrics, and evaluation.

## Phase 7 - Production Deployment

Add Kubernetes, Azure deployment patterns, scaling, security hardening, and release automation.
