# Architecture

## System intent

The platform provides a controlled path from user request to enterprise systems. It starts with web intelligence because discovery and evidence gathering are foundational Forward Deployed Engineer activities.

```text
React Operator Console
        |
FastAPI Gateway and Platform API
        |
Agent Runtime / Orchestrator
        |
MCP Host and Policy Layer
        |
Search | Crawl | Extract | Browser MCP adapters
        |
Public web and approved enterprise systems
```

## Primary boundaries

### React web application

The React application is responsible for operator workflows, result review, source presentation, and future dashboards. It never holds provider credentials or calls external tool providers directly.

### FastAPI platform API

FastAPI owns request authentication, API contracts, session context, and the backend-for-frontend boundary. It is the entry point for React and other clients.

### Agent runtime

The runtime coordinates planned work, invokes approved skills and tools, and records execution state. LangGraph is the planned workflow layer; the runtime must not couple directly to a particular web provider.

### MCP host and policy layer

The MCP host selects and invokes approved MCP servers. It applies policy: identity, authorization, URL allow/deny rules, rate limits, quotas, logging, and output normalization.

### Web-intelligence adapters

Provider adapters expose a platform-level contract, not vendor-specific tool shapes:

- `web.search`
- `web.fetch`
- `web.extract`
- `web.crawl`

Every returned record must preserve URL, retrieval time, provider, extraction method, content type, and a content hash.

## Trust boundary

Website content is untrusted input. Retrieved instructions are data, never authorization to alter agent goals, invoke extra tools, disclose secrets, or bypass policy. The platform will enforce output limits, validate URLs, protect against SSRF, and retain evidence provenance.
