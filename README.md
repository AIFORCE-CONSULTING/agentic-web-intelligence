# Agentic Web Intelligence

An open-source, production-quality platform for governed web discovery, extraction, and AI-agent research workflows.

The platform helps teams turn web-derived evidence into documented, governed, observable, and deployable AI solutions. It is inspired by the operating model of a Forward Deployed Engineer: discover, design, prototype, validate, and deliver without sacrificing enterprise standards.

## Phase 1: Foundation

Phase 1 establishes the engineering foundation: repository standards, React and FastAPI application boundaries, a Docker-first local environment, versioned documentation, and continuous integration.

## Phase 2: Governed web intelligence

Phase 2 delivers the first practical vertical slice: an evidence-producing web-research workflow that reaches approved search and extraction tools through Model Context Protocol (MCP). React remains the operator experience and FastAPI the platform boundary.

## Planned components

```text
apps/
  web/                 React operator console
  api/                 FastAPI gateway and platform API
platform-common/       Shared Python contracts and utilities
platform-core/         Agent-runtime and orchestration components
sample-mcp-servers/    Reference MCP servers and adapters
sample-agents/         Production-oriented agent examples
examples/              End-to-end use cases
docker/                Local Compose environment
diagrams/              Versioned architecture diagrams
docs/                  Documentation-site source
```

## Status

Phases 1 and 2 are complete. Phase 3 is the current focus. See [PROJECT.md](PROJECT.md), [ARCHITECTURE.md](ARCHITECTURE.md), and [ROADMAP.md](ROADMAP.md) for the project contract and delivery plan.

## Technology direction

- React + TypeScript
- FastAPI + Python
- MCP + LangGraph
- Docker Compose, PostgreSQL, Redis
- Observability and evaluation designed in from the outset

## License and community

This project is licensed under the [Apache License 2.0](LICENSE). Participation
is governed by the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).
