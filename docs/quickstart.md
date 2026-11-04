# Quickstart

This guide starts a private local instance of Agentic Web Intelligence. It is
for development and evaluation on your own machine; do not expose it directly
to the public internet.

## Prerequisites

- Docker Desktop with Linux containers enabled
- [Ollama](https://ollama.com/) running on the host machine
- Git, if you are starting from a source checkout

## Local-use limits

This is a local development and evaluation deployment, not an internet-facing
service. Keep the default `localhost` addresses in place and do not expose the
API, web console, database, Temporal UI, or documentation ports through a
public tunnel, router, or cloud host.

Docker Desktop must be running with enough memory, CPU, and disk space for the
platform services (PostgreSQL, SearXNG, Temporal, API, worker, web console, and
documentation site) as well as your normal desktop work. Research speed also
depends on the local Ollama model and the resources available to it; the
default `qwen3:1.7b` model must be installed and running before semantic
research, summaries, keywords, or reports can complete.

Web discovery and evidence extraction are optional configured services, not a
guarantee that every public webpage can be read. Publishers can deny automated
access, require a login or consent choice, use unsupported content types, or
return insufficient content. The platform records those outcomes rather than
bypassing them.

## Configure Local Secrets

From the repository root, create a local environment file:

```powershell
Copy-Item .env.example .env
```

Open `.env` and replace these sample values with unique local secrets:

- `POSTGRES_PASSWORD`
- `SEARXNG_SECRET`
- `AUTH_BOOTSTRAP_SECRET` (at least 32 characters)

Set `WEB_ORIGIN` to `http://localhost:3000`. Keep `.env` outside version
control and do not reuse these development secrets anywhere else.

## Install the Local Model

The default local research configuration uses Qwen3 1.7B through Ollama:

```powershell
ollama pull qwen3:1.7b
```

## Start the Platform

Start every service required for governed web research, including PostgreSQL,
SearXNG, Temporal, the durable worker, the API, the web console, and the
documentation site:

```powershell
docker compose --profile web-research up -d --build
```

Docker runs database bootstrap before the API and worker accept research work.
Wait for the platform status indicator in the web console to report ready.

Open:

- Research Workspace: `http://localhost:3000/`
- Administrator console: `http://localhost:3000/admin`
- Documentation: `http://localhost:8001/`
- Temporal UI: `http://localhost:8233/`

## First Use

1. Open the administrator console and create the first local administrator
   using `AUTH_BOOTSTRAP_SECRET`.
2. Configure the local Ollama provider and confirm the selected model is ready.
3. Create a Research Topic, ask a research question, and select
   **Discover Sources**.
4. Review any evidence marked **Needs your decision** before starting another
   question in the same topic.

The platform automatically decides whether work runs directly or through
Temporal. The operator does not need to select an execution mode.

## Verify a Source Checkout

Before contributing, run the checks in [Contributing](contributing.md). For an
end-to-end local smoke check, confirm the Research Workspace, documentation
site, and API readiness endpoint are available after Compose reports healthy
services.
