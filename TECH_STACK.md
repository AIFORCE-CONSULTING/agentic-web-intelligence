# Technology Stack

| Concern | Initial choice | Rationale |
|---|---|---|
| Frontend | React + TypeScript | Strong ecosystem for operator consoles and data-rich user interfaces. |
| Backend | FastAPI + Python | Native fit for AI tooling, typed API contracts, and asynchronous services. |
| Agent workflows | LangGraph | Explicit, testable stateful workflow orchestration. |
| Tool protocol | Model Context Protocol | Portable integration boundary for agent tools and services. |
| Local environment | Docker Compose | Reproducible, Docker-first contributor setup. |
| Data services | PostgreSQL and Redis | Durable relational data plus low-latency caching and coordination. |
| Documentation | MkDocs Material | Versioned, navigable engineering documentation. |
| CI/CD | GitHub Actions | Repository-native validation and automation. |

Cloud, model, search, and scraping providers remain replaceable behind adapters.
