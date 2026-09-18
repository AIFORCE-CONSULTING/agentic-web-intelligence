# Local evidence intelligence

Phase 6 adds local-first generated summaries and page-level keywords for
evidence that the governed research workflow has already extracted. It is
governed by [ADR 0014](adr/0014-governed-local-model-provider.md).

The local model is not an agent. It receives bounded evidence text from the
platform, returns structured summary data, and has no tools, browser,
filesystem, database, runtime, credential, or network authority beyond the
configured local Ollama endpoint.

## Local web-trust eligibility

Before the platform sends captured evidence to the local model, it evaluates
that exact evidence version under the local default policy described in
[ADR 0015](adr/0015-local-policy-controlled-web-trust.md). This is a
browser-agnostic platform decision about evidence eligibility, not a claim that
a source is true or that a browser should block it.

The initial policy checks HTTPS, supported extracted content types, extraction
integrity, and extracted-size limits. It records redirect history as unavailable
because the current evidence contract does not yet retain the redirect chain.
That limitation creates an `eligible_with_notice` result for otherwise valid
HTML or plain-text evidence; it does not prevent local summarization.

Extracted text over 200,000 characters is retained as `review_required`, not
sent to the model, and available for an authorized human to inspect and accept.
The retrieval service still rejects a raw response over 2 MB and rejects
extracted text over 2,000,000 characters. Those hard acquisition limits are not
overrideable.

Each evaluation is persisted with its policy and component versions, rule
outcomes, and effective disposition:

- `eligible` and `eligible_with_notice` evidence may enter the local-model
  context.
- `review_required` evidence remains visible in the operator interface but is
  excluded from summaries and keywords until a human operator accepts that exact
  content hash with a recorded reason.
- `blocked` evidence remains retained for audit but cannot enter automated
  model context. A human acceptance cannot override a blocked result.

Operators can inspect a run's latest evaluations at
`GET /v1/research/runs/{run_id}/evidence-trust`. A human operator can accept a
`review_required` result through
`POST /v1/research/runs/{run_id}/evidence-trust/accept`; the acceptance records
the operator, reason, exact evidence version, and optional expiry separately
from the summary execution mechanism.

## Boundary

Generated summaries are derived artifacts. The original extracted source
evidence remains the source of truth, and Postgres remains the canonical record
for each summary request, selected URL, route, status, chunk policy, generated
summary, keywords, sufficiency flag, and regeneration attempt.

Only authenticated administrators can configure the local provider. Authenticated
operators can request summaries for workspace-owned research runs and selected
sources. The model cannot choose sources, broaden evidence, select the execution
route, start durable work, approve human decisions, or invoke MCP tools.

The provider boundary supports local Ollama only. Endpoint configuration accepts
HTTP local addresses such as `http://localhost:11434`,
`http://127.0.0.1:11434`, and `http://host.docker.internal:11434`. It rejects
remote hosts, HTTPS URLs, embedded credentials, paths, query strings, and
fragments.

## Local setup

Install and run Ollama on the local host, then install an approved model such as
Qwen3 1.7B:

```powershell
ollama pull qwen3:1.7b
```

Start the local platform:

```powershell
docker compose --profile web-research up -d --build
```

This standard platform profile starts the API, web console, documentation site,
Postgres, SearXNG, Temporal, the Temporal UI, and the durable worker. Temporal
is required platform infrastructure: the operator starts the platform once and
never chooses an execution mechanism for an individual summary request.

The API applies the routing threshold after a summary request is accepted. It
executes a one-source, one-chunk request directly; it automatically schedules
the fixed Temporal workflow for multi-source or multi-chunk work.

The API checks Ollama readiness through `/api/tags`. Readiness does not perform
inference.

## Provider administration

Administrators manage the workspace's local provider configuration through the
Admin console or the local-model API:

- `GET /v1/local-model-provider` returns the current workspace configuration.
- `PUT /v1/local-model-provider` stores the local Ollama endpoint and model
  name.
- `GET /v1/local-model-provider/readiness` verifies that Ollama is reachable and
  that the configured model is installed.

The configuration is workspace-scoped and contains no secrets. Saving a
configuration records a `local_model.configured` security audit event with safe
metadata only.

## Operator workflow

Evidence summaries start from a persisted research run:

1. Create or reopen a governed research run.
2. The platform discovers and automatically preflights each returned candidate
   through the bounded retrieval path. Small batches run directly; larger
   batches use Temporal automatically.
3. The platform automatically summarizes and generates keywords for eligible
   retained evidence. `review_required`, `blocked`, and `unreachable`
   candidates remain visible with their reasons but do not enter model context.
4. An authorized operator may accept a specific `review_required` evidence
   version with a reason; the platform then automatically summarizes it.
5. Inspect generated summaries next to the original source evidence. To repeat
   a completed question, confirm rediscovery; the new run preserves a link to
   the earlier run rather than overwriting it.

The summary API is intentionally narrow:

- `POST /v1/evidence-summary-executions` creates a summary execution for a
  workspace-owned run and selected URLs.
- `GET /v1/evidence-summary-executions/{batch_id}` inspects a workspace-owned
  execution.
- `GET /v1/research/runs/{run_id}/evidence-summary-execution` restores the most
  recent summary execution for a run.
- `POST /v1/evidence-summary-executions/{batch_id}/regenerate` regenerates an
  already completed selection.

Regeneration must match the exact completed URL selection. It reuses stored
extracted evidence, resets only derived summary records, overwrites the matching
summary artifact in place, increments the regeneration attempt, and records a
`research.evidence_summary.regeneration_requested` audit event. It does not
retrieve webpages again.

## Routing

Routing is deterministic platform policy. Model output cannot influence it.

A request runs directly only when exactly one selected source produces exactly
one chunk. Any multi-source request or multi-chunk page automatically uses the
dedicated Temporal evidence-summary workflow. Durable execution is used only to
make an already authorized server job restart-safe; it does not grant the model
or caller Temporal authority.

If Temporal is unhealthy or unreachable when a durable route is selected, the
summary execution fails closed. That is a platform infrastructure failure, not
an operator routing choice.

## Chunking and consolidation

Each extracted page is prepared into bounded overlapping chunks. The platform
stores the content hash, character count, chunk count, and chunking policy
version for each selected source.

The local model first summarizes individual chunks with a fixed platform prompt.
Those chunk summaries are then consolidated into one page-level summary and
keyword set. When consolidation input would exceed the fixed budget, the
platform recursively records bounded consolidation groups before producing the
final source summary.

Final summaries include an `evidence_sufficient` flag. When the extracted
evidence is insufficient, the summary must say so instead of filling gaps.

## Failure behavior

Local evidence intelligence fails closed when:

- no local model provider is configured;
- Ollama is unreachable;
- the configured model is not installed;
- the provider returns invalid JSON or a schema-invalid result;
- the research run or selected evidence is unavailable;
- selected URLs are outside the current workspace-owned run; or
- Temporal is unhealthy or unavailable for a durably routed request.

Failure records remain inspectable through the summary execution status and
source failure reasons. Extracted source evidence is retained separately from
generated summary artifacts.
