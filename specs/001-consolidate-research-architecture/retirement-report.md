# Research Architecture Retirement Report

## Scope

This report records the repository-wide caller audit performed after the
unified LangGraph research workflow replaced the earlier overlapping workflow
paths. The audit covers API routes and startup state, application services,
Temporal worker registration, tests, and the web UI.

## Retired Components

The following components and entry points no longer exist in production code:

- `AgenticResearchControlService` and its duplicate control persistence;
- `ResearchOrchestrationService`, the plain-Python stage router;
- the deterministic planner, first-result executor, and reviewer workflow;
- `GovernedRuntimeWorkflow` and `TemporalRuntimeBoundary`;
- the old `/v1/runtime/runs` list, detail, approval, attention, and cancellation
  routes; and
- the old Admin approval and durable-cancellation controls.

The source-level retirement test in
`apps/api/tests/test_unified_research_integration.py` scans API production code
and `apps/web/src/App.tsx` for these retired entry points. It fails if one is
reintroduced.

## Retained Components

- `POST /v1/research/runs` remains the single operator action that starts or
  resumes research.
- `UnifiedResearchWorkflowEntry` and the compiled LangGraph own application
  orchestration.
- `research_runs.status` remains the operator-facing workflow status and is
  written through `ResearchStore` by the unified workflow.
- `RuntimeService` remains the authorization boundary. Its linked runtime run,
  researcher step, reservations, limits, and authorization decisions are
  retained because the unified graph uses them.
- `GovernedWebMcpHost` remains the only governed web-tool execution boundary.
- Web trust evaluations and human evidence acceptance remain independent of
  LangGraph and Temporal.
- Temporal continues candidate preflight and evidence-summary work. Its
  histories are execution tracking, not business status.
- PostgreSQL LangGraph checkpoints remain resumable execution bookmarks, not
  the operator-facing source of truth.
- Evidence, summaries, keywords, topics, relevance decisions, coverage, and
  reports remain product data.

## Clean-Start Boundary

The bounded clean-start command removes only standalone runtime rows with no
`research_run_id` and the four superseded agentic control tables. It preserves
all runtime assignments linked to canonical research records and does not
target evidence-domain tables. LangGraph bookmarks are deleted through the
official checkpointer API. Histories for `GovernedRuntimeWorkflow` are deleted
through Temporal's administration API using an exact workflow-type query.

## Caller Audit

The audit searches production API and web sources for imports, construction,
registration, routes, or controls associated with the retired components. It
also verifies the retained path remains connected from the research route to
the unified graph, RuntimeService, governed MCP host, trust services, summary
services, and Temporal continuation worker.

Audit result on 2026-09-28: no production caller, route, startup hook, worker
registration, or UI action can start the retired workflow. The consolidated
path remains the only active research orchestration path. The applied clean
start reported zero standalone runtime rows, zero obsolete graph threads, zero
`GovernedRuntimeWorkflow` Temporal histories, and no remaining superseded
agentic control tables.
