# Agentic Web Intelligence

An open-source, production-quality platform for governed web discovery, extraction, and AI-agent research workflows.

The platform helps teams turn web-derived evidence into documented, governed, observable, and deployable AI solutions. It is inspired by the operating model of a Forward Deployed Engineer: discover, design, prototype, validate, and deliver without sacrificing enterprise standards.

## Phase 1 focus

Phase 1 establishes the engineering foundation and the first practical vertical slice: governed web intelligence through Model Context Protocol (MCP). The stack uses React for operator-facing experiences and FastAPI for APIs, agent services, and orchestration.

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

Foundation work is in progress. See [PROJECT.md](PROJECT.md), [ARCHITECTURE.md](ARCHITECTURE.md), and [ROADMAP.md](ROADMAP.md) for the project contract and delivery plan.

## Technology direction

- React + TypeScript
- FastAPI + Python
- MCP + LangGraph
- Docker Compose, PostgreSQL, Redis
- Observability and evaluation designed in from the outset

## License and community

This project is licensed under the [Apache License 2.0](LICENSE). Participation
is governed by the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).
