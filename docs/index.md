# Agentic Web Intelligence

An open-source, production-quality platform for governed web discovery, extraction, and AI-agent research workflows.

The platform is designed to help teams move from an ambiguous business problem to a documented, governed, observable, and deployable AI solution. Its working model is the Forward Deployed Engineer: discover, design, prototype, validate, and deliver while preserving enterprise standards.

## Phase 1: Foundation

Phase 1 makes the project safe and easy to adopt. It establishes the repository, development environment, documentation, contribution standards, and the first thin vertical slice:

```text
React operator console -> FastAPI gateway -> MCP policy boundary -> web intelligence tools
```

The initial local stack runs only the React console and FastAPI service. PostgreSQL and Redis are intentionally opt-in until a platform capability needs them.

## Start here

- Read the [project vision](foundation/project.md) and [engineering principles](foundation/principles.md).
- Review the [platform architecture](architecture.md) and the [MCP web-intelligence decision](adr/0003-web-intelligence-mcp.md).
- Follow the [contribution guide](contributing.md) to run the project locally.
