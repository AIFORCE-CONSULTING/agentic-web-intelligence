# Governed web research

Phase 2 provides two read-only web capabilities through the platform API:

- `POST /v1/research/search` discovers public source candidates.
- `POST /v1/research/extract` returns bounded text evidence from one public page.

The agent execution boundary is the MCP host at `POST /mcp`. It implements the
MCP JSON-RPC methods `initialize`, `tools/list`, and `tools/call` and exposes
only `web.search` and `web.extract`. `GET /v1/mcp/tools` is a convenient
operator-readable view of that same allow-listed registry. Provider-specific
tools are never advertised to agents.

## Tool-registry governance

Every agent-visible tool is a code-owned registry entry, not just a dispatch
case. An entry must declare its owner, purpose, required workspace permission,
input schema, output contract, server-side secret dependencies, enabled-by-
default state, and whether execution audit is mandatory. The API enforces the
declared permission before dispatch and refuses an enabled tool whose required
secret is not configured.

Administrators can inspect the full safe policy inventory at
GET /v1/tools/registry. It contains no secret values. The existing web tools
have no credential dependency, are enabled by default, are read-only, and
require an execution audit. A future connector must be registered with the
same metadata before it can become callable.

Every agent-requested `tools/call` must cite a correlated, stored RuntimeService
allow decision. The host reloads that decision before dispatch; a tool schema
or model proposal is never treated as permission. Every call outcome is stored in Postgres without retaining the
retrieved page text. Operators can inspect the 25 most recent outcomes through
`GET /v1/mcp/audit`; it records the tool, success/failure/denial outcome, and
safe provenance such as a retrieved URL and content hash.

The agent-facing contract stays small. SearXNG and Trafilatura are internal
implementations selected by the platform, not raw tools exposed to a workflow.

The operator-facing run endpoint enters the one LangGraph research workflow. A
run keeps the question, workflow status, source candidates, evidence, derived
artifacts, and audit trail in Postgres. Temporal is selected automatically for
qualifying preflight and summary work and resumes that same graph after its
result is stored.

When a public source rejects automated retrieval—for example, with HTTP 403—the
platform returns a clear extraction failure instead of saving misleading source
data. The run receives a `research.extract.failed` audit event with the requested
URL, safe failure reason, and upstream status when available.

## Run locally

Set a long random `SEARXNG_SECRET` in your local `.env` file. The committed
`.env.example` shows the required setting without containing a real secret.

Start the application stack and the internal search service:

~~~powershell
docker compose --profile web-research up --build
~~~

SearXNG is available only on the Compose network. The browser and workflows
call the platform API, not SearXNG directly.

Open `http://localhost:3000/developer` for the operator-facing developer hub.
It shows the API, durable-research persistence, and governed-discovery health,
and links to the API reference, OpenAPI schema, MCP tool catalog, and the
documentation site. The `web-research` profile includes that site on port 8001.

## Search example

~~~powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/v1/research/search `
  -ContentType application/json `
  -Body '{"query":"agentic web intelligence","max_results":2}'
~~~

The platform caps discovery at 50 results, pages through the internal provider
as needed, normalizes source fields, removes duplicate URLs from one discovery
request, and filters results that point to non-public network destinations.

## Persistent research run

Start the complete governed workflow instead of using the transient developer
search endpoint:

~~~powershell
$run = Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/v1/research/runs `
  -ContentType application/json `
  -Body '{"question":"agentic web intelligence","max_results":5}'
$run.id
~~~

The route authenticates and validates the request, finds or creates its research
record, and starts or resumes the unified LangGraph. Search, acquisition, trust,
relevance, summaries, coverage, and reporting then proceed through their owning
services. Retrieve stored progress with `GET /v1/research/runs/{run_id}`. The default local
`web-research` Compose profile starts Postgres, SearXNG, Temporal, the Temporal
UI, and the durable worker with the API.

`GET /v1/research/runs` returns the 25 most recently updated runs by default,
including source and evidence counts but not full evidence text. The operator
console uses this bounded library to reopen a run without re-running discovery.
When the normalized research target already exists, the platform returns that
record and reuses its known sources and evidence instead of creating a duplicate
run or rediscovering stored URLs.

## Extraction policy

`/v1/research/extract` accepts one HTTP(S) URL and returns extracted source data
only. It rejects local/private literal IP addresses, hostnames that resolve to
non-public addresses, embedded credentials, nonstandard ports, attachments,
file downloads, unsupported content types, oversized responses or extracted
text, and excessive redirects. Every redirect target is revalidated before a
request is made.

The Phase 2 default permits only `text/html` and `text/plain`. Authenticated
systems, PDFs, browser interaction, and crawling are separate future
capabilities that require additional policy and audit controls.
