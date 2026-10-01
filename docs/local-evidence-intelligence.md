# Local evidence intelligence

Phase 6 adds local-first generated summaries and page-level keywords for
evidence that the governed research workflow has already extracted. It is
governed by [ADR 0014](adr/0014-governed-local-model-provider.md).

The Phase 6 local model is not an agent. It receives bounded evidence text from
the platform, returns structured summary data, and has no tools, browser,
filesystem, database, runtime, credential, or network authority beyond the
configured local Ollama endpoint. [ADR 0016](adr/0016-governed-local-agent-capability-requests.md)
defines the bounded agent workflow that now coordinates this existing summary
and keyword service. The agent cannot bypass its eligibility or storage rules.

## Local web-trust eligibility

Before the platform sends captured evidence to the local model, it evaluates
that exact evidence version under the local default policy described in
[ADR 0015](adr/0015-local-policy-controlled-web-trust.md). This is a
browser-agnostic platform decision about evidence eligibility, not a claim that
a source is true or that a browser should block it.

The initial policy checks HTTPS, supported extracted content types, extraction
integrity, and extracted-size limits. Retrieval retains the requested candidate
URL, final evidence URL, and a bounded redirect result. The result explains how
the evidence was reached but does not independently change its trust
disposition. The extractor continues to validate every redirect destination
before requesting it.

Extracted text over 200,000 characters is retained as `review_required`, not
sent to the model, and available for an authorized human to inspect and accept.
The retrieval service still rejects a raw response over 2 MB and rejects
extracted text over 2,000,000 characters. Those hard acquisition limits are not
overrideable.

Each evaluation is persisted with its policy and component versions, rule
outcomes, and effective disposition. Operators can inspect the effective,
server-owned policy through the read-only `GET /v1/web-trust-policy` endpoint;
that endpoint neither changes policy nor re-evaluates evidence.

- `eligible` evidence may enter the local-model context.
- `review_required` evidence remains visible in the operator interface but is
  excluded from summaries and keywords until a human operator accepts that exact
  content hash with a recorded reason.
- `blocked` evidence remains retained for audit but cannot enter automated
  model context. A human acceptance cannot override a blocked result.

Operators can inspect a run's latest evaluations at
`GET /v1/research/runs/{run_id}/evidence-trust`. The operator UI provides an
inline review panel with the captured evidence, retrieval details, policy
version, and rule outcomes before acceptance. A human operator can accept a
`review_required` result through
`POST /v1/research/runs/{run_id}/evidence-trust/accept`; the acceptance records
the operator, reason, exact evidence version, and optional future expiry
separately from the summary execution mechanism. A blocked result cannot be
accepted.

## Boundary

Generated summaries are derived artifacts. The original extracted source
evidence remains the source of truth, and Postgres remains the canonical record
for each summary request, selected URL, route, status, chunk policy, generated
summary, keywords, prompt version, sufficiency flag, regeneration cycle, and
safe model-attempt outcome. New summaries use the fixed `evidence-summary-v3`
contract: chunks and consolidation groups return a summary and three to five
keywords; final source summaries return a summary, three to seven keywords, and
`evidence_sufficient`. The prompt asks the model to select keywords the summary
explains. The platform validates the response shape, keyword count, and keyword
uniqueness, but does not reject a useful summary because the keyword wording is
not repeated exactly in the prose. Existing `keyword_coverage` data remains
readable for historical artifacts, but new work neither requests nor writes it.

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

The unified LangGraph applies the routing threshold after summary work is
accepted. It
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

1. Enter a question, choose the source count, and select **Discover Sources**.
   The platform finds or creates the research record and enters the unified
   LangGraph workflow.
2. The platform discovers and automatically preflights each returned candidate
   through the bounded retrieval path. Small batches run directly; larger
   batches use Temporal automatically.
3. After the unified graph records topic relevance, the platform automatically
   summarizes and generates keywords for eligible, relevant retained evidence.
   `review_required`, `blocked`, and `unreachable`
   candidates remain visible with their reasons but do not enter model context.
4. An authorized operator may accept a specific `review_required` evidence
   version with a reason; the platform then automatically summarizes it.
5. Inspect generated summaries through the workspace keyword view. Each keyword
   groups every stored source summary that uses it, and a source link opens the
   newest stored summary for that URL without navigating to the external page.
   Repeating a completed normalized question reopens its existing target and
   does not create another discovery run or fetch its sources again.

The summary API is intentionally narrow:

- `POST /v1/evidence-summary-executions` creates a summary execution for a
  workspace-owned run and selected URLs.
- `GET /v1/evidence-summary-executions/{batch_id}` inspects a workspace-owned
  execution.
- `GET /v1/research/runs/{run_id}/evidence-summary-work-set` restores the
  combined summary-stage outcome for a run, including every internal
  five-source execution. It is the Research workspace's progress view.
- `GET /v1/evidence-summary-artifacts` returns one newest stored summary per
  URL for the current workspace, which powers the workspace keyword view.
- `GET /v1/research/runs/{run_id}/report` returns the newest stored final
  report without starting any model work.
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
dedicated Temporal evidence-summary workflow. The unified graph is the sole
starter of summary work, after relevance is recorded. It creates one summary
work set for the research task; a set may contain several internal jobs of at
most five sources. Each job persists its own result, and the graph resumes only
once the entire set is terminal. A failed job does not discard usable summaries
from its sibling jobs.
Durable execution makes an already authorized job restart-safe; it does not
grant the model or caller Temporal authority or own research status.

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

Both prompts require the model to write the summary before choosing keywords.
The server validates keyword count and uniqueness after Ollama returns JSON.
The prompts ask for keywords that the summary explains, without making exact
phrase repetition a rejection rule. If a completed response is malformed or fails those
checks, the platform records a safe validation category and gives that exact
summary unit one corrective attempt with the same bounded evidence. It never
passes the invalid response back to the model. A second invalid completed
response marks only that source `summary_contract_exhausted`; it does not erase
valid summaries from other sources.

Final summaries include an `evidence_sufficient` flag. When the extracted
evidence is insufficient, the summary must say so instead of filling gaps. That
source remains visible and reusable, but it does not count toward topic coverage
or final-report input. The final report uses only stored summaries that are
eligible under trust policy, relevant to a planned topic, and evidence
sufficient.

## Final report quality

The final report is built from a fixed snapshot of those qualified summaries.
The local model can propose a structured report, but the platform checks that
every claim cites a known source for the same topic before it renders the
report. The report panel shows a `PASS` or `FAIL` quality grade. `FAIL` does not
mean the evidence failed trust policy or that the research run failed; it means
the report was incomplete, too brief, or had to fall back to an evidence
briefing because no safe model draft was available.

The first draft may receive one bounded correction with a concise explanation
of what was missing. If both drafts fail the safe rendering checks, the platform
still displays an evidence briefing assembled from the stored summaries. The
report links only to the platform's stored source summaries. It never turns a
model-provided URL into a navigation target. A separate disclosure lists known
sources that were not used and why, such as blocked, awaiting review,
insufficient, failed to summarize, or not relevant to a planned topic.

## Failure behavior

Local evidence intelligence fails closed when:

- no local model provider is configured;
- Ollama is unreachable;
- the configured model is not installed;
- the provider is unavailable before it completes a response;
- the research run or selected evidence is unavailable;
- selected URLs are outside the current workspace-owned run; or
- Temporal is unhealthy or unavailable for a durably routed request.

Completed invalid model responses are a recoverable source-level problem, not a
provider outage. Each summary unit has at most two model-call slots in an
operator-authorized regeneration cycle. Attempt records retain model and prompt
versions, the unit identity, outcome, and safe validation category, never raw
model output. Failure records remain inspectable through the summary execution
status and source failure reasons. Extracted source evidence is retained
separately from generated summary artifacts.
