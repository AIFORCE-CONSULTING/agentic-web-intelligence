# Implementation Plan: Topic-Scoped Report Sections

**Branch**: `004-topic-report-sections` | **Date**: 2026-10-02 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/004-topic-report-sections/spec.md`

## Summary

Extend the existing grounded final-report path so platform code owns the report
sections and model calls are bounded to one planned topic at a time. The
platform will load planned topics and qualified summaries from the existing
report-input selector, assign simple report-local labels such as `S01`, ask the
local model for findings for that single topic only, validate any cited labels
against the supplied topic input, and render the final Markdown report from
trusted stored records.

This is a refinement of the existing validated report package, not a new report
workflow. It keeps `ResearchReportingService.final_report` and the unified
LangGraph `generate_final_report` node as the only report-generation path.

## Technical Context

**Language/Version**: Python 3.12 API; TypeScript/React web client
**Primary Dependencies**: FastAPI, asyncpg/PostgreSQL, Ollama Python client,
Pydantic, LangGraph, Temporal for existing durable preflight and summary work
**Storage**: PostgreSQL through `AgenticResearchStore`, `ResearchStore`,
`EvidenceSummaryStore`, and existing trust/review stores
**Testing**: Ruff and pytest for API; existing web build/type checks for UI changes
**Target Platform**: Local Docker Compose development stack
**Project Type**: Web application with API, worker, and browser UI
**Performance Goals**: At most two bounded local-model attempts per planned
topic; no raw webpage text in final-report prompts; report generation should
complete or produce fallback content without leaving the run in reporting
**Constraints**: Local/offline inference; temperature `0.0`; source summaries
are untrusted reference material; model may propose findings but cannot decide
topics, source eligibility, final links, or workflow state
**Scale/Scope**: One final report per canonical research run, up to three
planned topics, and the qualified source summaries already accepted into topic
coverage

## Constitution Check

**Pre-design result: PASS.** The feature extends the canonical reporting owner
and selected workflow. It does not add a new workflow, report endpoint,
authorization boundary, trust decision, source-eligibility rule, or status
machine.

### Architecture Reconciliation

| Responsibility | Existing owner and evidence | Plan |
| --- | --- | --- |
| Report workflow trigger | `generate_final_report` node from `apps/api/app/agentic_research/workflow_nodes.py` calls `ResearchReportingService.final_report`; ADR 0016 says this node remains the sole report caller | Reuse unchanged. The node still calls the same service and returns `report_stored`. |
| Report drafting and validation | `ResearchReportingService` in `apps/api/app/agentic_research/reporting.py`; ADR 0014 describes validated report packages | Extend. Replace one whole-report model draft with per-topic draft calls and deterministic platform rendering. |
| Report input selection | `AgenticResearchStore.report_inputs` joins topic coverage, summaries, trust evaluations, and review overrides | Reuse as the only selector. Do not re-evaluate trust, relevance, source adequacy, or review state. |
| Report persistence and provenance | `AgenticResearchStore.save_report_package` writes append-only report, input, contribution, exclusion, and attempt rows | Extend existing records. Do not create a second store. |
| Research progress | `ResearchStore.transition_status` through unified LangGraph wrapper owns `research_runs.status` | Reuse unchanged. A stored report package still lets the graph complete; reporting fails only if inputs cannot be read or the package cannot be stored. |
| Report read path | `GET /v1/research/runs/{run_id}/report` in `apps/api/app/main.py` and the existing Final report panel | Reuse and extend only if response fields must expose clearer reasons; no report-start endpoint. |
| Model authority | ADR 0014 and ADR 0016: local model receives bounded contracts and untrusted input; platform validates output | Narrow further. The model writes topic findings only; platform owns sections, labels, source lists, links, grade, and fallback. |

### State and Decision Ownership Matrix

| State or decision | Business question | Canonical record and field | Authorized writer | Readers | Derived copies | Allowed transitions | Conflict resolution |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Research workflow status | What stage or terminal outcome does the operator see? | `research_runs.status`, `status_version`, `failed_stage`, `failure_code`, `failure_explanation`, `retryable` | `ResearchStore.transition_status` through the unified LangGraph wrapper | UI, API, RuntimeService, worker | LangGraph checkpoint, Temporal history, transition audit | Existing transitions, including `reporting -> completed` after any report package is saved and `reporting -> failed` only when report inputs cannot be read or the package cannot be stored | Stored `research_runs` value wins over checkpoint/history; optimistic status version rejects conflicting updates |
| Report input eligibility | Which summaries may support the report? | Existing topic coverage, summary, trust, and review records loaded through `AgenticResearchStore.report_inputs` | Existing coverage, summary, trust, and review owners | Reporting service, report store, report UI | Frozen report-input rows in `agentic_research_report_inputs` | Existing qualification lifecycle only; this feature adds no eligibility transition | Existing canonical coverage/trust/review records win; a stored report snapshot is historical if current input fingerprint changes |
| Report topic structure | Which sections must appear in the final report? | `agentic_research_topics.topic_id`, `topic`, `position` as loaded into the report package | Topic-planning workflow through `AgenticResearchStore` | Reporting service, renderer, UI | Rendered Markdown headings; report-input child rows repeat topic identity | Created during topic planning; immutable for report rendering | Stored planned-topic order wins; legacy or unexpected model-authored topic fields are ignored/rejected |
| Citation label mapping | Which report-local label represents each stored source summary? | `agentic_research_report_inputs.source_ref` plus `source_url`, `source_title`, `summary_artifact_id`, `topic_record_id` | `ResearchReportingService` through `AgenticResearchStore.save_report_package` | Report renderer, UI, report endpoint, validators | Markdown citation links and supporting-source map | Created with each report package; immutable thereafter | Frozen report package wins for historical report; current report check detects mismatch with live inputs |
| Topic finding draft | Which model-proposed findings were safe enough to render for one topic? | `agentic_research_report_attempts.topic_id`, `attempt_number`, `raw_response`, `validation_errors`, `status`, `failure_code`, plus contribution rows when accepted | `ResearchReportingService` through `AgenticResearchStore` | Reporting service, UI quality explanation, audit support | Rendered Markdown findings; validation reasons | Attempt starts and ends as `pass`, `fail`, or `unusable`; maximum two attempts per planned topic with uniqueness on `report_id`, `topic_id`, and `attempt_number` | Deterministic validator wins; legacy/invalid model-authored topic identifiers, unsupported labels, and cross-topic labels are rejected |
| Report quality grade | Did the stored report meet coverage, traceability, and completeness requirements? | `agentic_research_reports.quality_grade`, `quality_reasons`, `report_origin` | `ResearchReportingService` through `AgenticResearchStore.save_report_package` | Report endpoint, UI, audit support | Quality badge and explanation | Created once as `PASS` or `FAIL`; immutable thereafter | Platform validator/fallback reason wins; grade does not change source trust or research status |
| Stored report package | Which operator-facing report may be shown? | `agentic_research_reports` and child input, contribution, exclusion, and attempt rows | `ResearchReportingService` through `AgenticResearchStore.save_report_package` | Report endpoint, UI, audit support | Rendered Markdown/API DTO | Created from validated topic sections or fallback evidence briefing; never edited | Immutable input snapshot wins; stale reports are shown only as historical/not-current if exposed |

For workflows:

- **UI display value:** The UI continues to display `research_runs.status` for
  workflow progress and the stored `ResearchReport.quality_grade` for report
  quality.
- **Authorization value:** RuntimeService evaluates existing research assignment,
  workspace, role, and capability records. It does not evaluate report quality.
- **Continuation:** LangGraph checkpoints resume execution, but each node reloads
  canonical stored records. A checkpoint is not proof that a report package is
  accepted.
- **Retries and concurrency:** Existing normalized research target and status
  versioning prevent competing research runs. Report packages remain append-only;
  the newest current package is read through the existing report endpoint.
- **Dependency failure:** Model timeout, unavailable model, malformed topic draft,
  or unusable topic output produces a `FAIL` report/fallback when inputs can be
  read and stored. Only unreadable report inputs or failed persistence make the
  research run fail during reporting.

### Operational Checkpoint

- **Trigger:** Existing unified research workflow reaches the `reporting` stage.
- **Authority owner:** RuntimeService remains the authority boundary for research
  capabilities; report quality and rendering are owned by `ResearchReportingService`.
- **Canonical state:** `research_runs` stores workflow status; `agentic_research_reports`
  and child rows store report package state.
- **Execution rule:** Reporting remains direct inside the existing LangGraph node
  because it is bounded local inference and adds no new external side effect.
  Temporal remains unchanged for durable preflight and summary work.
- **Human decisions:** Evidence review and overrides remain in existing trust/review
  records and are enforced before report input selection.
- **Excluded callers/capabilities:** No new UI button, report-start API, MCP tool,
  browser worker, Temporal workflow, trust-policy rule, or source-eligibility path.

### Post-Design Constitution Check

**Result: PASS.** Phase 0 and Phase 1 artifacts preserve the same owners. The
data model extends existing report-package records; the contract preserves the
existing report read endpoint; and the quickstart verifies the canonical
workflow without introducing a parallel report mechanism.

## Project Structure

### Documentation (this feature)

```text
specs/004-topic-report-sections/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── topic-report-contract.md
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
is implemented by extending the canonical reporting service, store, report
contracts, tests, and existing report panel.

## Complexity Tracking

No constitution violations or new architectural exceptions are required.
