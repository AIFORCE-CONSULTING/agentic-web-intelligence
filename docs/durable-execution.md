# Durable Execution

Temporal is mandatory local infrastructure for approved work that must survive
an API timeout, worker restart, or bounded retry. It is an execution mechanism,
not an authorization service, trust policy, or source of operator-facing state.

## Local services

Start the standard platform stack:

```powershell
docker compose --profile web-research up -d --build
```

The Temporal API listens on port `7233`, its UI on
<http://localhost:8233>, the platform API on port `8000`, and the web console on
port `3000`. The `durable-worker` receives only the database, Temporal, and
governed research configuration it needs.

## Routing

Platform code selects direct or durable execution from deterministic workload
thresholds. The operator and model never choose the route.

- Small candidate preflight and summary work runs directly inside the graph.
- Work meeting the durable threshold uses `CandidatePreflightWorkflow` or
  `EvidenceSummaryWorkflow`.
- No public endpoint, MCP tool, model capability, or generic Temporal client can
  start an arbitrary workflow.

## Continuation

For durable work, the LangGraph node records a wait and returns. The Temporal
workflow calls the established service, which persists the official business
result through its owning store. The `continue_unified_research` activity then
reloads the research record, authority facts, and graph thread and resumes the
same unified graph at its next valid stage.

Temporal history and LangGraph checkpoints never become business truth.
`research_runs.status` remains the status shown by the UI. Preflight and summary
stores remain the official records for their work. A stale checkpoint,
conflicting or terminal research status, missing authority, or already-applied
result stops continuation safely.

## Failure and visibility

If Temporal is unavailable when a durable route is required, the platform
fails closed and records the typed failure. Retries use stable identifiers so
they do not duplicate evidence, summary artifacts, authority decisions, or
workflow transitions.

The Admin **Durable Work** section is read-only. It combines the current
workspace's preflight and summary durable-work records; it does not infer
business status from Temporal and does not expose workflow controls,
credentials, or cross-workspace data.

The worker no longer registers `GovernedRuntimeWorkflow` or its old researcher
and reviewer activities. Those duplicate execution paths and their test-era
history were removed during Phase 7.5.

See [ADR 0013](adr/0013-governed-durable-execution-contract.md) and the
[current architecture](current-platform-architecture.md).
