# Contributing to Agentic Web Intelligence

Thank you for helping improve Agentic Web Intelligence. Useful contributions
include reproducible bug reports, documentation improvements, research findings,
security analysis, and well-scoped code changes.

By participating, you agree to follow the [Code of Conduct](https://github.com/AIFORCE-CONSULTING/agentic-web-intelligence/blob/main/CODE_OF_CONDUCT.md).
Contributions are made under the repository's [Apache License 2.0](https://github.com/AIFORCE-CONSULTING/agentic-web-intelligence/blob/main/LICENSE).

## Start With Discussion

Search existing issues before opening a new one. For a non-trivial feature,
workflow, security, architecture, or user-experience change, open a capability
proposal first and wait for a maintainer to agree on the direction before
investing in implementation. This prevents duplicate work and helps changes fit
the platform's existing research, trust, and execution boundaries.

Documentation corrections and narrowly reproducible bug fixes are generally
good candidates for a focused pull request. Maintainers may label a scoped issue
as `help wanted` when it is ready for community implementation.

Do not use public issues, discussions, or pull requests for security
vulnerabilities, credentials, personal data, customer data, or production URLs.
See the [security policy](https://github.com/AIFORCE-CONSULTING/agentic-web-intelligence/blob/main/SECURITY.md).

## Local Development

### Prerequisites

- Git
- Docker Desktop with Linux containers enabled
- Ollama, when exercising local-model research flows
- A local checkout of this repository

Copy the example environment file:

```powershell
Copy-Item .env.example .env
```

Replace every sample value in `.env`, particularly `POSTGRES_PASSWORD`,
`SEARXNG_SECRET`, and `AUTH_BOOTSTRAP_SECRET`. The bootstrap secret must be at
least 32 characters. Keep `.env` local and never commit it.

For the complete guided setup, including first administrator bootstrap and local
model configuration, follow the [Quickstart](https://aiforce-consulting.github.io/agentic-web-intelligence/quickstart/).

Start the local research platform:

```powershell
ollama pull qwen3:1.7b
docker compose --profile web-research up -d --build
```

The Research Workspace is available at `http://localhost:3000/`; the local
documentation site is available at `http://localhost:8001/`.

## Quality Checks

Run checks that cover the area you changed before opening a pull request.

API linting and tests:

```powershell
docker run --rm -v "${PWD}:/workspace" -w /workspace/apps/api python:3.12-slim sh -lc "pip install --require-hashes --only-binary=:all: -r requirements-dev.lock >/dev/null && ruff check . && PYTHONPATH=/workspace/apps/api pytest -q"
```

Web build:

```powershell
docker run --rm -v "${PWD}:/workspace" -w /workspace/apps/web node:22-alpine sh -lc "npm ci --ignore-scripts --audit=false && npm rebuild esbuild --ignore-scripts=false --foreground-scripts --audit=false && npm run build"
```

Documentation build:

```powershell
docker compose --profile documentation build docs
```

For dependency changes, follow [dependency security guidance](https://github.com/AIFORCE-CONSULTING/agentic-web-intelligence/blob/main/DEPENDENCY_SECURITY.md)
and [dependency management](https://aiforce-consulting.github.io/agentic-web-intelligence/dependency-management/). Python and
documentation lockfiles must be regenerated with the repository script; do not
edit lockfiles by hand.

## Design and Architecture Changes

The platform has deliberate boundaries for workflow state, authority, web-trust
evaluation, MCP tools, local models, and durable execution. Before changing a
user action, workflow, background worker, human approval, external effect, or
architecture boundary:

1. Read the [architecture constitution](https://aiforce-consulting.github.io/agentic-web-intelligence/architecture-constitution/)
   and relevant [ADRs](https://aiforce-consulting.github.io/agentic-web-intelligence/decisions/).
2. Reconcile the proposal with the existing owner of that responsibility.
3. Discuss the design with maintainers before implementation.
4. Add or update an ADR when the decision creates or changes a lasting
   architecture boundary.

The project uses Spec Kit for significant feature planning. The repository's
`AGENTS.md` and architecture constitution define the required planning and
approval expectations for these changes.

## Pull Requests

1. Create a focused branch from the current `main` branch.
2. Keep the pull request small enough to review and explain the user or platform
   outcome, not only implementation details.
3. Complete the pull request template, including verification evidence and any
   security, privacy, supply-chain, or architectural impact.
4. Update documentation whenever behavior, architecture, setup, or operations
   change.
5. Wait for the required CI checks and maintainer review before merge.

Maintainers may ask for tests, documentation, narrower scope, or a design
discussion before accepting a change. See [Governance](https://github.com/AIFORCE-CONSULTING/agentic-web-intelligence/blob/main/GOVERNANCE.md)
for how maintainers make decisions.
