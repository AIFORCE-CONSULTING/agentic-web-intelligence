# Implementation Plan: Chunk-Aware Summary Batching

**Branch**: `007-chunk-aware-summary-batching` | **Date**: 2026-10-03 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `specs/007-chunk-aware-summary-batching/spec.md`

## Summary

The platform currently packages summary work for Temporal by source count alone:
`EvidenceSummaryAutomation._MAX_SOURCES_PER_EXECUTION = 5` slices relevant
source URLs into fixed groups before each execution is prepared. That ignores
how much text each source contains. Recent local data showed source chunk counts
from 1 to 23 chunks, with about 22 seconds per chunk on average. A five-source
group can therefore exceed the 20-minute Temporal activity timeout even when the
local model is operating normally.

This plan extends the existing evidence-summary owner instead of adding another
workflow. LangGraph continues to decide that the research run needs
summarization. The evidence-summary service plans safe summary work groups using
known chunk counts, prepares those executions, and sends only appropriately
sized durable jobs to Temporal. The Temporal workflow uses the aggregate
summary-work-set status to resume the unified research graph, so one failed
internal execution does not automatically fail the research run when completed
summaries exist.

## Technical Context

**Language/Version**: Python 3.12 for API/background workers; TypeScript/React
for existing operator UI if copy needs to change.  
**Primary Dependencies**: FastAPI, LangGraph, Temporal Python SDK, asyncpg,
Pydantic, pytest; no new dependency is planned.  
**Storage**: PostgreSQL through existing `EvidenceSummaryStore`,
`ResearchStore`, and `AgenticResearchStore` records.  
**Testing**: pytest for API/service/workflow tests; existing web build if UI
text changes.  
**Target Platform**: Local Docker Compose platform with API, durable worker,
PostgreSQL, Temporal, Ollama, and web UI.  
**Project Type**: Local web application with API service, durable worker, and
operator UI.  
**Performance Goals**: Reduce avoidable 20-minute summary activity timeouts by
preventing oversized multi-source durable executions; keep small-source batches
efficient.  
**Constraints**: Do not change chunk size, model prompts, source discovery,
trust evaluation, relevance evaluation, report grading, or operator workflow.
Do not introduce a second orchestrator or durable-execution path. Initial
batching policy: 1 to 5 chunks is small, 6 to 15 chunks is above-normal, 16 or
more chunks is oversized, and no multi-source work group may exceed 15 total
chunks.  
**Scale/Scope**: Research runs with operator-selected source limits up to the
current UI-supported range, including mixed small and large web sources.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Canonical owner:** Existing owners are preserved. LangGraph remains the
  research workflow owner in `apps/api/app/agent_runtime/research_workflow.py`.
  Evidence summary batching and execution packaging remain owned by
  `EvidenceSummaryAutomation` and `EvidenceSummaryService` in
  `apps/api/app/evidence_summaries/service.py`. Durable execution remains owned
  by `EvidenceSummaryWorkflow` in
  `apps/api/app/evidence_summaries/workflow.py`. Stored summary records remain
  owned by `EvidenceSummaryStore` in
  `apps/api/app/evidence_summaries/store.py`. ADR 0016 states that summary
  processing belongs to the existing summary workflow and that partial success
  continues from usable summaries. ADR 0014/0016 preserve Temporal as the
  durable-execution boundary when thresholds require it.
- **State and decision ownership:** Completed below. The plan identifies the
  official record and writer for each touched state/decision.
- **No parallel authority:** This extends the evidence-summary owner. It does
  not add another workflow, state machine, service, policy authority, store, or
  execution path.
- **Selected foundations:** LangGraph coordinates the application sequence and
  enters the summary stage. RuntimeService authorization is unchanged.
  Temporal continues to run durable summary work when routing says durable.
  PostgreSQL remains the business/audit record through existing stores.
- **Model boundary:** The model does not choose batch size, source grouping,
  execution route, failed-source usability, or workflow continuation. Platform
  code validates and records every state transition.
- **Migration and retirement:** Existing callers stay on
  `EvidenceSummaryAutomation.start_for_relevant_urls`. The fixed slicing policy
  is replaced in place and retired once tests prove the chunk-aware planner.
  Existing stored work sets and executions remain readable; no data migration is
  required.
- **Operational checkpoint:** Trigger is the existing LangGraph summary node
  after relevance decisions are recorded. Authority owner is the
  evidence-summary service for batching and execution packaging. Canonical state
  is stored in existing summary work-set, execution, source, attempt, and
  artifact tables. Direct/durable routing remains automatic. No human decision
  is added. Exclusions: source discovery, trust policy, review accept/reject,
  relevance, prompts, report grading, and UI source-count selection.
- **Approval:** Runtime/workflow code changes require the normal design
  checkpoint approval before implementation.

The Constitution Check passes for planning because the work extends the
existing canonical owners and all touched state decisions are assigned below.

### State and Decision Ownership Matrix

| State or decision | Business question | Canonical record and field | Authorized writer | Readers | Derived copies | Allowed transitions | Conflict resolution |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Summary work group membership | Which source URLs are assigned to one summary execution? | `evidence_summary_execution_sources.execution_id` + `url`, with work-set grouping via `evidence_summary_work_set_members.work_set_id`/`execution_id` | `EvidenceSummaryAutomation` through `EvidenceSummaryStore.create_execution()` and `attach_execution_to_work_set()` | `EvidenceSummaryService`, `EvidenceSummaryWorkflow`, Admin durable-work view, tests | Temporal workflow input contains only the execution id; LangGraph checkpoint stores wait context | planned by automation -> execution created -> optionally attached to work set -> prepared/scheduled/executed | PostgreSQL membership wins. Temporal input cannot add or remove sources. Duplicate graph resumes reuse the existing work set instead of creating new groups. |
| Batch-sizing decision | How much source content may be sent to one summary execution? | Deterministic planner output persisted indirectly as execution source membership and recorded source `chunk_count` values | `EvidenceSummaryAutomation` using chunk counts prepared by `EvidenceSummaryService`/chunking policy | `EvidenceSummaryService`, tests, operator/admin status | Logs/test fixtures may repeat planner output but are not authoritative | not planned -> planned before execution creation -> immutable for that execution; 1-5 chunks is small, 6-15 chunks is above-normal, 16+ chunks is oversized and isolated | Stored execution membership wins. If source evidence changes before execution, the existing content hash/chunk count recorded for that execution defines what was processed. |
| Execution route | Should one summary execution run directly or through Temporal? | `evidence_summary_executions.route` | `EvidenceSummaryService.prepare()` through `EvidenceSummaryStore.set_execution_route()` | `EvidenceSummaryAutomation`, durable worker, Admin durable-work view | Temporal history records durable runs; LangGraph wait state records pending durable work | `undetermined` -> `direct` or `durable` | Stored route wins. Model/operator cannot choose route. Invalid route/status combinations fail safely. |
| Source summary status | Did one source produce usable summary output? | `evidence_summary_execution_sources.status`, `failure_reason`, `failure_category`, `evidence_sufficient`, `artifact_id` | `EvidenceSummaryService` through `EvidenceSummaryStore` | `EvidenceSummaryStore`, `AgenticResearchStore`, UI/API status, reporting | Attempt rows, chunk rows, group rows, summary artifacts | `pending` -> `extracting` -> `extracted` -> `summarizing` -> `completed` or `failed`; regeneration may reset derived rows to `extracted` | Source status wins for source usability. Failed sources remain excluded. Completed artifacts remain usable unless their trust/relevance/source facts no longer qualify. |
| Summary execution status | Did one internal summary execution finish with usable output? | `evidence_summary_executions.status` | `EvidenceSummaryService` and worker failure activities through `EvidenceSummaryStore` | `EvidenceSummaryWorkflow`, work-set refresh, Admin durable-work view | Temporal activity result/history | `extracting`/`awaiting_execution` -> `summarizing` -> `completed` or `failed`; scheduling failure -> `failed` | Execution status determines its own terminal state, but not the whole research run when the aggregate work set contains completed usable summaries. |
| Summary work-set status | Did the whole summary stage have any usable completed summaries? | `evidence_summary_work_sets.status` | `EvidenceSummaryStore.refresh_work_set()` / `complete_evidence_summary_work_set` activity | `EvidenceSummaryWorkflow`, LangGraph continuation, UI/API status | LangGraph wait result; Temporal workflow result | `created` -> `waiting` -> `completed` if at least one execution completed with usable output; `failed` if every execution fails/cancels; remains `waiting` until all executions terminal | Work-set status is the summary-stage aggregate. It overrides an individual execution failure for continuation decisions. |
| Research run status | What operator-facing stage is the research run in? | `research_runs.status`, `status_version`, `failed_stage`, `failure_code`, `failure_explanation` | Unified LangGraph via `ResearchStore` | UI, API routes, RuntimeService, Admin status, tests | LangGraph checkpoint is an execution bookmark only; Temporal history is execution tracking only | Existing transitions remain: `summarizing` -> `assessing_coverage` when usable summaries exist; `summarizing` -> `failed` when no usable summaries exist or stored state conflicts | Research status wins for the UI. Summary work-set results inform the graph, but do not write status directly except through the existing continuation path. |
| Report input eligibility | Which summaries may enter coverage/reporting? | `agentic_topic_coverage_evidence.summary_artifact_id` joined to completed summary artifacts and accepted relevance/trust records | `AgenticResearchStore` coverage assessment | Reporting service, UI/API | Final report package repeats cited source labels | no coverage -> coverage row created only when all canonical evidence/trust/relevance/summary facts qualify | Coverage rules win. Failed summary sources never create qualifying report inputs. |

For workflows:

- The UI displays `research_runs.status` plus summary source counts read from
  the summary stores.
- RuntimeService evaluates stored assignment/capability/workflow facts; this
  feature does not change RuntimeService decisions.
- Interrupted work resumes from stored summary work sets/executions and
  LangGraph checkpoints. Checkpoints are bookmarks only.
- Retries and concurrent requests reuse an existing active/completed work set
  for the run and do not create duplicate summary groups.
- Dependency failures update the affected summary execution/source records. The
  graph continues only from the aggregate work-set outcome.

## Project Structure

### Documentation (this feature)

```text
specs/007-chunk-aware-summary-batching/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── summary-batching.md
└── tasks.md
```

### Source Code (repository root)

```text
apps/api/
├── app/
│   ├── evidence_summaries/
│   │   ├── service.py
│   │   ├── store.py
│   │   └── workflow.py
│   ├── agentic_research/
│   │   ├── store.py
│   │   └── workflow_nodes.py
│   └── agent_runtime/
│       └── research_workflow.py
└── tests/
    ├── test_evidence_summary_*.py
    ├── test_unified_research_workflow.py
    └── test_web_research.py

apps/web/
└── src/
    └── App.tsx
```

**Structure Decision**: Extend the existing API service, evidence-summary
module, unified graph, and tests. No new application, worker, service, or store
is introduced.

## Phase 0 Research Summary

See [research.md](./research.md). Key decisions:

- use a deterministic chunk-aware planner in the evidence-summary service;
- retain direct-vs-durable routing inside the summary preparation boundary;
- let aggregate work-set status control graph continuation;
- avoid changing chunk size or model prompts in this feature.

## Phase 1 Design Summary

See [data-model.md](./data-model.md), [contracts/summary-batching.md](./contracts/summary-batching.md), and [quickstart.md](./quickstart.md).

The design intentionally persists batching through existing execution/source
membership and source chunk-count records rather than creating a separate
planner table.

## Post-Design Constitution Check

- **Canonical owners remain unchanged:** `EvidenceSummaryAutomation` owns work
  grouping, `EvidenceSummaryService` owns preparation/execution,
  `EvidenceSummaryWorkflow` owns durable activity continuation, `ResearchStore`
  owns operator-facing research status, and `AgenticResearchStore` owns
  coverage/report inputs.
- **No parallel authority introduced:** The design removes the fixed slicing
  policy in place and does not add another workflow path.
- **Selected foundations preserved:** LangGraph starts/continues the summary
  stage, Temporal runs durable work, PostgreSQL stores business state, and the
  model remains outside routing/batching/state decisions.
- **Model boundary preserved:** Batch size and continuation decisions are
  deterministic platform decisions.
- **Migration/retirement clear:** Fixed five-source slicing is superseded by the
  chunk-aware planner. Existing records remain readable because schema does not
  change.

## Complexity Tracking

No constitution violations are planned.
