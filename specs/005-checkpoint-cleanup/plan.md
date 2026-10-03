# Implementation Plan: Completed Checkpoint Cleanup

**Branch**: `005-checkpoint-cleanup` | **Date**: 2026-10-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-checkpoint-cleanup/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Completed research runs currently leave LangGraph execution bookmarks behind
until startup or manual maintenance retries cleanup. The readiness check treats
that cleanup backlog as a hard blocker, so an operator can complete one
research run and then be prevented from starting an unrelated second run.

The implementation will extend the existing `ResearchCheckpointLifecycle` and
`ResearchStore` ownership that already manage checkpoint setup, cleanup audits,
and bounded retry. After a graph invocation returns, the unified workflow entry
will reload or confirm the research run is officially `completed` before it
triggers best-effort cleanup. Cleanup results will continue to be recorded in
`research_checkpoint_cleanups`, and readiness will report cleanup backlog as
degraded maintenance rather than blocking unrelated new research.

## Technical Context

**Language/Version**: Python 3.12 API service  
**Primary Dependencies**: FastAPI, LangGraph 1.2.10, langgraph-checkpoint-postgres 3.1.2, asyncpg, Temporal Python SDK  
**Storage**: PostgreSQL business tables through `ResearchStore`; LangGraph PostgreSQL checkpoint tables through `AsyncPostgresSaver`  
**Testing**: pytest for API and workflow tests  
**Target Platform**: Local Docker Compose platform and API/worker containers  
**Project Type**: Web API and background workflow service  
**Performance Goals**: Cleanup is bounded and best effort; starting a new unrelated research run must not wait on completed-run cleanup.  
**Constraints**: Do not delete framework checkpoint rows with direct SQL; do not remove evidence, summaries, keywords, trust decisions, reports, or audit records; do not introduce a second workflow state machine.  
**Scale/Scope**: One research-thread cleanup per completed run plus bounded retry batches for prior completed runs without successful cleanup audit records.

## Constitution Check

*GATE: Passed before Phase 0 research; re-checked after Phase 1 design below.*

- **Canonical owner:** Existing owners are reused. `ResearchCheckpointLifecycle`
  in `apps/api/app/agent_runtime/research_workflow.py` owns checkpoint
  lifecycle operations; `ResearchStore` in
  `apps/api/app/web_research/store.py` owns cleanup candidate lookup and cleanup
  audit records; the unified LangGraph wrapper owns research status
  transitions.
- **State and decision ownership:** Matrix below names the official record,
  writer, readers, derived copies, transitions, and conflict outcome for every
  touched state/decision.
- **No parallel authority:** The plan does not add a new cleanup service, new
  state machine, new store, new policy authority, or new execution path. It
  extends the current checkpoint lifecycle adapter and current research store.
- **Selected foundations:** LangGraph continues coordinating research;
  RuntimeService continues authorizing agent capabilities; Temporal remains
  durable execution for preflight and summaries; PostgreSQL stores official
  business/audit records; LangGraph checkpoints remain execution bookmarks.
- **Model boundary:** No model proposal or model validation is involved.
  Cleanup cannot be requested or decided by a model.
- **Migration and retirement:** No data migration is required. Existing
  completed research outputs remain readable. Pending cleanup rows are retried
  through the existing maintenance command. The hard-blocking readiness behavior
  is superseded when backlog is only completed-run cleanup maintenance.
- **Operational checkpoint:** Trigger is a run reaching `completed` or a bounded
  retry command. Authority owner is `ResearchCheckpointLifecycle`; cleanup audit
  state is stored by `ResearchStore`; work is direct local maintenance, not
  Temporal durable execution; no human decision is recorded; model, MCP, and
  operator research decisions are excluded.
- **Approval:** This plan is ready for user architecture approval before runtime
  or workflow code changes.

### State and Decision Ownership Matrix

| State or decision | Business question | Canonical record and field | Authorized writer | Readers | Derived copies | Allowed transitions | Conflict resolution |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Research workflow status | What stage or terminal outcome should the operator see for a research task? | `research_runs.status`, plus `status_version`, failure fields, and transition audit | Unified LangGraph wrapper through `ResearchStore.transition_status` | UI, API routes, RuntimeService, workflow nodes, worker continuations | LangGraph checkpoint state, Temporal histories, API read models | Existing transitions, including `reporting -> completed` after a report package is stored and `reporting -> failed` only when report creation/persistence cannot complete | Stored `research_runs` row wins. Checkpoints and Temporal histories never advance or roll back official status. Stale writers reload official state or fail safely. |
| Cleanup audit outcome | Was execution-bookmark cleanup attempted for this completed run, and what happened? | `research_checkpoint_cleanups.outcome` and `explanation` for the `research_run_id` | `ResearchCheckpointLifecycle` via `ResearchStore.record_checkpoint_cleanup` | Checkpoint lifecycle, health/readiness, maintenance command, operational diagnostics | LangGraph checkpoint row presence/absence; operator health view | No record -> pending; pending attempt -> succeeded or failed; failed -> succeeded on later retry; succeeded remains terminal for backlog purposes | Cleanup audit does not change research status. If audit and checkpoint rows disagree, completed research data remains authoritative and bounded cleanup retry repairs bookmark state. |
| Cleanup backlog health | Is there completed-run execution-bookmark maintenance still pending? | Derived count from completed `research_runs` lacking successful cleanup audit | `ResearchStore.checkpoint_cleanup_backlog` computes it from canonical records | Health/services endpoint, checkpoint lifecycle, maintenance command | API readiness response | Backlog may be zero, degraded maintenance, or dependency-unavailable; it is not a research workflow state | Backlog no longer blocks unrelated research starts. If dependency is unavailable, health reports degraded/unavailable while research status records remain authoritative. |
| Execution bookmark retention | Should a LangGraph checkpoint thread still be retained? | LangGraph checkpoint tables for the research `thread_id` and graph namespace | LangGraph checkpointer through official saver APIs, called only by `ResearchCheckpointLifecycle` | LangGraph runtime, checkpoint lifecycle | Cleanup audit, health/readiness | Active/waiting/failed/review-required runs retain bookmarks; completed runs become cleanup-eligible after status commit and terminal graph return | Research status wins over checkpoint state. Direct SQL deletes are forbidden; retry uses the official checkpointer deletion API. |

For workflows, also state:

- The UI displays `research_runs.status`; cleanup backlog may appear only as
  maintenance health and should not be presented as research status.
- RuntimeService evaluates the stored research assignment, authority records,
  and official research status; cleanup audit does not grant capabilities.
- Interrupted research resumes from LangGraph checkpoints only while the
  official research status is resumable. Completed research does not resume
  from a checkpoint.
- Cleanup retry is idempotent: repeated attempts append audit outcomes and a
  successful cleanup removes the run from backlog calculations.
- Checkpoint cleanup dependency failures record a failed cleanup audit and
  degrade maintenance health without changing completed research status.
- Readiness must expose two separate facts: whether checkpoint infrastructure is
  available for active workflow execution, and whether completed-run cleanup
  maintenance is pending. Only checkpoint infrastructure unavailability can make
  a new research start unavailable; completed-run cleanup backlog can only add
  degraded maintenance detail.

## Project Structure

### Documentation (this feature)

```text
specs/005-checkpoint-cleanup/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
apps/api/app/agent_runtime/research_workflow.py
apps/api/app/web_research/store.py
apps/api/app/main.py
apps/api/tests/test_unified_research_workflow.py
apps/api/tests/test_web_research.py
docs/agent-runtime.md
docs/current-platform-architecture.md
```

**Structure Decision**: Extend the current API workflow and store modules.
Tests stay in the existing workflow and API test files. Documentation updates
stay with the current agent-runtime and architecture records.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitution violations are required for this plan.

## Phase 0 Research Summary

See [research.md](./research.md). Key decisions:

- Use the existing checkpoint lifecycle owner and official LangGraph
  checkpointer deletion API.
- Treat pending completed-run cleanup as degraded maintenance, not a hard
  blocker for unrelated research.
- Keep startup/manual bounded retry as a recovery path.

## Phase 1 Design Summary

See [data-model.md](./data-model.md), [quickstart.md](./quickstart.md), and
[contracts/checkpoint-cleanup-contract.md](./contracts/checkpoint-cleanup-contract.md).

## Post-Design Constitution Re-Check

*GATE: Passed after Phase 1 design.*

The design extends existing owners, keeps official business state in
PostgreSQL service stores, keeps LangGraph checkpoints as derived execution
bookmarks, uses the existing bounded maintenance command, and adds no model,
MCP, Temporal, workflow, policy, or store authority. Cleanup failures are
audited and do not change completed research status.
