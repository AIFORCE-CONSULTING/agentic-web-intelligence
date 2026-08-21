# Governed web research

Phase 2 provides two read-only web capabilities through the platform API:

- `POST /v1/research/search` discovers public source candidates.
- `POST /v1/research/extract` returns bounded text evidence from one public page.

The agent-facing contract stays small. SearXNG and Trafilatura are internal
implementations selected by the platform, not raw tools exposed to a workflow.

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

## Extraction policy

`/v1/research/extract` accepts one HTTP(S) URL and returns extracted evidence
only. It rejects local/private literal IP addresses, embedded credentials,
nonstandard ports, attachments, file downloads, unsupported content types,
oversized responses, and excessive redirects.

The Phase 2 default permits only `text/html` and `text/plain`. Authenticated
systems, PDFs, browser interaction, and crawling are separate future
capabilities that require additional policy and audit controls.
