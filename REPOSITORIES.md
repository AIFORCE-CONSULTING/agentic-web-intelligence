# Repository Organization

Phase 1 begins as a monorepo so contributors can run the React application, FastAPI API, shared contracts, documentation, and local infrastructure together.

| Area | Responsibility |
|---|---|
| `apps/web` | React + TypeScript operator console |
| `apps/api` | FastAPI gateway and backend-for-frontend |
| `platform-common` | Shared Python models, configuration, and utilities |
| `platform-core` | Agent orchestration and platform services |
| `sample-mcp-servers` | Reference servers and provider adapters |
| `sample-agents` | Reusable agent workflows |
| `examples` | Complete vertical-slice examples |
| `docker` | Docker Compose and local service configuration |
| `diagrams` | Source-controlled architecture diagrams |
| `docs` | MkDocs Material site source |

The repository can be split later only when a component has independent release, access-control, or contributor needs. A premature multi-repository split would make the first integrated capability harder to develop and operate.
