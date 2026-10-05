# Implementation Plan: Bounded Final Report Batching

**Branch**: `009-bounded-report-batching` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/009-bounded-report-batching/spec.md`

## Summary

Extend the existing topic-scoped final-report path so a planned topic with many
qualified summaries is split into smaller bounded report groups before calling
the local model. The platform will continue to own topics, source membership,
source labels, report quality, citation links, and final Markdown rendering.
The model will draft findings only for one bounded group of already-qualified
summaries at a time. Validated findings from successful groups are merged into
one topic section; failed groups are recorded as report-stage quality reasons
without discarding successful findings from other groups.

This is a refinement of `ResearchReportingService.final_report`, not a new
report workflow. The existing unified LangGraph `generate_final_report` node
remains the only report caller, and `GET /v1/research/runs/{run_id}/report`
remains the only report read path.

## Technical Context

**Language/Version**: Python 3.12 API; TypeScript/React web client  
**Primary Dependencies**: FastAPI, asyncpg/PostgreSQL, Ollama Python client,
Pydantic, LangGraph, Temporal for existing durable preflight and summary work  
**Storage**: PostgreSQL through `AgenticResearchStore` report package tables;
`ResearchStore` remains the workflow-status owner  
**Testing**: Ruff and pytest for API; existing web build/type checks if report
display labels change  
**Target Platform**: Local Docker Compose development stack  
**Project Type**: Web application with API, worker, and browser UI  
**Performance Goals**: Report-drafting model calls should use bounded groups of
no more than seven summaries and no more than roughly 10,000 prompt input
characters per group, unless a single source summary exceeds that character
budget by itself and must be isolated. A topic with 15 qualified summaries
should produce a useful report section instead of two empty `{}` responses.  
**Constraints**: Local/offline inference; temperature `0.0`; source summaries
are untrusted reference material; model may propose findings but cannot decide
topics, source eligibility, source grouping authority, report quality, final
links, or workflow state  
**Scale/Scope**: One final report per canonical research run, up to three
planned topics, and all qualified source summaries already accepted into topic
coverage

## Constitution Check

**Pre-design result: PASS.** The feature extends the canonical report owner and
selected workflow. It does not add a new workflow, report endpoint, trust
decision, RuntimeService authority, source-eligibility path, Temporal workflow,
or research-status transition.

### Architecture Reconciliation

| Responsibility | Existing owner and evidence | Plan |
| --- | --- | --- |
| Report workflow trigger | `generate_final_report` node in `apps/api/app/agentic_research/workflow_nodes.py` calls `ResearchReportingService.final_report`; ADR 0016 says the graph final-report node remains the sole report caller | Reuse unchanged. The node still calls the same service and returns `report_stored`. |
| Report drafting and validation | `ResearchReportingService` in `apps/api/app/agentic_research/reporting.py`; ADR 0014 "Validated final-report packages" requires platform-owned report sections and bounded model findings | Extend. Add deterministic grouping inside the reporting service before model calls. |
| Report input selection | `AgenticResearchStore.report_inputs` selects qualified summaries from topic coverage, summaries, trust evaluations, and review outcomes | Reuse unchanged. Do not re-evaluate trust, relevance, source adequacy, or review state. |
| Report grouping | Currently implicit: every qualified source for a topic is sent in one topic payload | New responsibility inside `ResearchReportingService`. It is an execution packaging decision, not source eligibility or workflow status. |
| Report persistence and provenance | `AgenticResearchStore.save_report_package` writes append-only report, input, contribution, exclusion, and attempt rows | Extend existing report attempt records with bounded-group identity. Do not create a second store. |
| Research progress | `ResearchStore.transition_status` through the unified LangGraph wrapper owns `research_runs.status` | Reuse unchanged. A stored report package still lets the graph complete; reporting fails only if report inputs cannot be read or the package cannot be stored. |
| Report read path | `GET /v1/research/runs/{run_id}/report` in `apps/api/app/main.py` and the existing Final report panel | Reuse. Add clearer quality details only if existing response fields are insufficient. No report-start endpoint. |
| Model authority | ADR 0014 and ADR 0016: the local model receives bounded contracts and untrusted input; platform validates output | Narrow further. The model writes findings for one bounded group only; platform owns grouping, merging, sections, labels, source lists, links, grade, and fallback. |
| Ollama runtime tuning | Current calls set `temperature: 0.0`; stored research suggests `keep_alive`, `num_ctx`, loaded-model count, and parallelism should be measured | Treat as measurement/tuning guidance in this feature. Do not make runtime tuning a prerequisite for correctness; bounded grouping is the correctness fix. |

### State and Decision Ownership Matrix

| State or decision | Business question | Canonical record and field | Authorized writer | Readers | Derived copies | Allowed transitions | Conflict resolution |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Research workflow status | What stage or terminal outcome does the operator see? | `research_runs.status`, `status_version`, `failed_stage`, `failure_code`, `failure_explanation`, `retryable` | `ResearchStore.transition_status` through the unified LangGraph wrapper | UI, API, RuntimeService, worker | LangGraph checkpoint, Temporal history, transition audit | Existing transitions, including `reporting -> completed` after any report package is saved and `reporting -> failed` only when report inputs cannot be read or the package cannot be stored | Stored `research_runs` value wins over checkpoint/history; optimistic status version rejects conflicting updates |
| Report input eligibility | Which summaries may support the report? | Existing topic coverage, summary, trust, and review records loaded through `AgenticResearchStore.report_inputs` | Existing coverage, summary, trust, and review owners | Reporting service, report store, report UI | Frozen report-input rows in `agentic_research_report_inputs` | Existing qualification lifecycle only; this feature adds no eligibility transition | Existing canonical coverage/trust/review records win; a stored report snapshot is historical if current input fingerprint changes |
| Report topic structure | Which sections must appear in the final report? | `agentic_research_topics.topic_id`, `topic`, `position` as loaded into the report package | Topic-planning workflow through `AgenticResearchStore` | Reporting service, renderer, UI | Rendered Markdown headings; report-input child rows repeat topic identity | Created during topic planning; immutable for report rendering | Stored planned-topic order wins; model-authored topic fields are ignored or rejected |
| Report bounded group | Which subset of one topic's qualified summaries was sent to one report-drafting call? | `agentic_research_report_attempts.topic_id`, new `group_index`, `input_characters`, `response_characters`, and associated frozen report-input rows | `ResearchReportingService` through `AgenticResearchStore.save_report_package` | Reporting service, report diagnostics, tests, audit support | Model prompt payload; validation feedback | Created during report generation for each topic; group identity is immutable within the stored report package | Frozen report package wins for historical diagnostics; grouping is recomputed only when a new report package is created |
| Citation label mapping | Which report-local label represents each stored source summary? | `agentic_research_report_inputs.source_ref` plus `source_url`, `source_title`, `summary_artifact_id`, `topic_record_id` | `ResearchReportingService` through `AgenticResearchStore.save_report_package` | Report renderer, UI, report endpoint, validators | Markdown citation links and supporting-source map | Created with each report package; immutable thereafter | Frozen report package wins for historical report; current report check detects mismatch with live inputs |
| Bounded finding draft | Which model-proposed findings were safe enough to render for one bounded group? | `agentic_research_report_attempts.topic_id`, `group_index`, `attempt_number`, `raw_response`, `response_characters`, `validation_errors`, `status`, `failure_code`, plus contribution rows when accepted | `ResearchReportingService` through `AgenticResearchStore` | Reporting service, UI quality explanation, audit support | Rendered Markdown findings; validation reasons | Attempt is persisted only after an attempt outcome is known as `pass`, `fail`, or `unusable`; maximum two attempts per bounded group | Deterministic validator wins; empty `{}`, unsupported labels, and labels outside the bounded group are rejected |
| Topic report section | What operator-facing findings are shown for one planned topic? | Stored report Markdown plus `agentic_research_report_contributions` for accepted findings and source-list entries | `ResearchReportingService` through trusted renderer | Report endpoint, UI, audit support | Markdown section and in-page anchors | Created from zero or more validated bounded groups plus deterministic source list | Validated group findings are included; failed groups add quality reasons but do not erase successful findings |
| Report quality grade | Did the stored report meet coverage, traceability, and completeness requirements? | `agentic_research_reports.quality_grade`, `quality_reasons`, `report_origin` | `ResearchReportingService` through `AgenticResearchStore.save_report_package` | Report endpoint, UI, audit support | Quality badge and explanation | Created once as `PASS` or `FAIL`; immutable thereafter | Platform validator/fallback reason wins; grade does not change source trust or research status |
| Stored report package | Which operator-facing report may be shown? | `agentic_research_reports` and child input, contribution, exclusion, and attempt rows | `ResearchReportingService` through `AgenticResearchStore.save_report_package` | Report endpoint, UI, audit support | Rendered Markdown/API DTO | Created from validated bounded findings and/or fallback evidence; never edited | Immutable input snapshot wins; newest report package is current by created time |

For workflows:

- **UI display value:** The UI continues to display `research_runs.status` for
  workflow progress and `ResearchReport.quality_grade` plus `quality_reasons`
  for report quality.
- **Authorization value:** RuntimeService evaluates existing research assignment,
  workspace, role, and capability records. It does not evaluate report quality
  or report group size.
- **Continuation:** LangGraph checkpoints resume execution, but the final-report
  node reloads canonical stored inputs before creating a report package. A
  checkpoint is not proof that a report package or bounded group passed.
- **Retries and concurrency:** Existing normalized research target and status
  versioning prevent competing research runs. Within a report package,
  `topic_id + group_index + attempt_number` uniquely identifies bounded report
  attempts so retry records do not collide.
- **Dependency failure:** Model timeout, model unavailable, empty `{}`,
  malformed group output, unsupported labels, or unusable findings create a
  report quality reason when inputs can be read and stored. Only unreadable
  report inputs or failed persistence make the research run fail during
  reporting.

### Bounded Group Planning Rule

The first implementation uses deterministic report-group planning inside
`ResearchReportingService`:

- maximum summaries per bounded group: **7**;
- target maximum prompt input characters per bounded group: **10,000**;
- summaries are grouped in stored topic/source order;
- if adding the next summary would exceed either limit, a new group starts;
- if one summary exceeds 10,000 prompt input characters by itself, it is placed
  alone in an oversized single-source group and still validated normally;
- no qualified source summary may be dropped because of grouping.

The character budget applies to the prompt payload sent for that bounded group,
including topic context and supplied source summaries. It is a reliability
guardrail for the local model, not a trust or relevance decision.

### Operational Checkpoint

- **Trigger:** Existing unified research workflow reaches the `reporting` stage.
- **Authority owner:** RuntimeService remains the authority boundary for research
  capabilities. `ResearchReportingService` owns report grouping, validation,
  rendering, and quality grading.
- **Canonical state:** `research_runs` stores workflow status. `agentic_research_reports`
  and child rows store report package state, report inputs, report attempts,
  contributions, exclusions, and quality reasons.
- **Execution rule:** Reporting remains direct inside the existing LangGraph node
  because it uses bounded local inference over stored summaries and adds no new
  external side effect. Temporal remains unchanged for durable preflight and
  summary work.
- **Human decisions:** Evidence review and overrides remain in existing trust and
  review records and are enforced before report input selection.
- **Excluded callers/capabilities:** No new UI button, report-start API, MCP
  tool, browser worker, Temporal workflow, trust-policy rule, source-eligibility
  path, or model-selection decision.

### Post-Design Constitution Check

**Result: PASS.** Phase 0 and Phase 1 artifacts preserve the same owners. The
data model extends existing report-package records with bounded-group identity;
the contract preserves the existing report read endpoint; and the quickstart
verifies the canonical workflow without introducing a parallel report mechanism.

## Project Structure

### Documentation (this feature)

```text
specs/009-bounded-report-batching/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── bounded-report-batching-contract.md
└── tasks.md
```

### Source Code (repository root)

```text
apps/api/app/agentic_research/
├── contracts.py
├── reporting.py
└── store.py

apps/api/app/agentic_research/workflow_nodes.py
apps/api/app/main.py
apps/api/tests/
├── test_agentic_research_reporting.py
├── test_research_report.py
└── test_research_workflow.py

apps/web/src/App.tsx
docs/adr/
├── 0014-governed-local-model-provider.md
└── 0016-governed-local-agent-capability-requests.md
```

**Structure Decision**: Keep the existing API/reporting/web layout. The feature
is implemented by extending the canonical reporting service, report attempt
schema, store, tests, and existing report panel only if additional diagnostics
need display.

## Complexity Tracking

No constitution violations or new architectural exceptions are required.
