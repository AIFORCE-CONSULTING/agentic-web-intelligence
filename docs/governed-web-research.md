# Governed web research

Phase 2 provides two read-only web capabilities through the platform API:

- `POST /v1/research/search` discovers public source candidates.
- `POST /v1/research/extract` returns bounded text evidence from one public page.

The agent-facing contract stays small. SearXNG and Trafilatura are internal
implementations selected by the platform, not raw tools exposed to a workflow.

Research is durable when it uses the run endpoints. A run keeps the question,
ranked source candidates, extracted source data, and an append-only audit trail in
Postgres. This makes results inspectable and reusable without giving agents
direct database or browser access.

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

## Search example

~~~powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/v1/research/search `
  -ContentType application/json `
  -Body '{"query":"agentic web intelligence","max_results":2}'
~~~

The platform caps the number of returned results, normalizes source fields, and
filters results that point to non-public network destinations.

## Persistent research run

Create a research run instead of using the transient search endpoint:

~~~powershell
$run = Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/v1/research/runs `
  -ContentType application/json `
  -Body '{"question":"agentic web intelligence","max_results":2}'
$run.id
~~~

The response contains its sources and audit events. Attach approved extracted
source data to that same run with:

~~~powershell
Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/v1/research/runs/$($run.id)/extract" `
  -ContentType application/json `
  -Body '{"url":"https://example.com"}'
~~~

Retrieve it later with `GET /v1/research/runs/{run_id}`. The default local
`web-research` Compose profile starts Postgres with the API and SearXNG.

`GET /v1/research/runs` returns the 25 most recently updated runs by default,
including source and evidence counts but not full evidence text. The operator
console uses this bounded library to reopen a run without re-running discovery.

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
