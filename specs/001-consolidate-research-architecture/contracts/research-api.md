# Contract: Existing Research API

## `POST /v1/research/runs`

The request remains the bounded `question` and supported `max_results`. The
authenticated workspace and human identity come from the identity boundary.

The route authenticates and validates, then delegates to the unified graph
entry adapter. That adapter finds or creates the canonical research task,
creates or reuses its server-owned runtime assignment, records the operator
start decision, starts or resumes the persisted graph, and returns
`research_runs.status`. The route cannot advance that status. It does not
search, save candidates, preflight, summarize, choose Temporal, or interpret
model output.

Return `201` for a new task and `200` for reused/resumed work. Preserve the
existing `ResearchRun` response and typed authentication, validation, and
availability errors.

The route returns service unavailable before starting or resuming research when
PostgreSQL, the LangGraph checkpointer, or mandatory Temporal readiness fails.
It does not create an in-memory run or silently choose direct execution. For a
stored dependency-failed run, the response exposes only the stable failure
code, safe explanation, failed stage, retryability, and failure time. Selecting
**Discover Sources** retries that same run only after required readiness passes.

## Reads and review

`GET /v1/research/runs/{run_id}` remains the polling contract and reads business
status from `research_runs.status`, not checkpoints, runtime-step state, or
Temporal history. The existing trust-acceptance route
remains the only human action for one exact evidence version. After the review
service stores it, trusted code may resume the waiting graph; the endpoint does
not grant model tools or alter runtime policy.
