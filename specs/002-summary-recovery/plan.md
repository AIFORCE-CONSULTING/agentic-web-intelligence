# Implementation Plan: Reliable Summary Recovery

**Branch**: `002-summary-recovery` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

## Summary

Extend the existing evidence-summary service so one malformed completed local-model response receives one safe corrective attempt, without weakening validation or creating another workflow. Remove the model-generated keyword-coverage map, verify keyword presence deterministically, record safe attempt diagnostics, preserve successful sources when another source fails, and show the stored report and summary failures in the existing Research workspace.

## Technical Context

**Language/Version**: Python 3.12; TypeScript 5  
**Primary Dependencies**: FastAPI, Pydantic, asyncpg, Temporal, LangGraph, Ollama, React, Vite  
**Storage**: PostgreSQL 16  
**Testing**: pytest, Ruff, Vite production build, strict MkDocs build, Docker Compose integration verification  
**Target Platform**: Local Docker Compose platform with operator-managed Ollama  
**Project Type**: Web application with API, durable worker, and browser UI  
**Constraints**: At most two completed responses per summary unit; no extra webpage retrieval; no raw malformed-model-output storage; no model authority or tool access  
**Scope**: Existing bounded summary executions of up to five sources, using existing direct or Temporal routing

## Architecture Reconciliation

| Responsibility | Current owner | Owner after change | Treatment |
| --- | --- | --- | --- |
| Prompt and output validation | `EvidenceSummaryService`; ADR 0014 | Same service | Extend with v2 keyword-presence validation and one corrective response. |
| Summary/source persistence | `EvidenceSummaryStore` | Same store | Add append-only attempt diagnostics and source failure metadata. |
| Direct/durable routing | `EvidenceSummaryAutomation` and Temporal boundary | Same owners | Reuse unchanged; recovery stays inside one execution. |
| Research status and continuation | Unified LangGraph and `ResearchStore` | Same owners | Reuse unchanged; consume completed or failed summary result. |
| Agent authority | `RuntimeService`; ADR 0016 | Same owner | Reuse unchanged; no new capability or authority. |
| Trust and review | Web-trust and evidence-review services | Same owners | Reuse unchanged before summarization. |
| Report storage | `AgenticResearchStore` | Same store | Add trusted omission disclosure and a read-only report view. |
| Operator experience | Existing Research workspace | Same UI surface | Extend; do not add a second agent screen. |

This plan introduces no parallel service, policy, state machine, execution path, or source of truth. LangGraph checkpoints remain execution bookmarks and Temporal history remains durable-execution tracking.

## Constitution Check

### Before Design: Pass

- `EvidenceSummaryService` remains the only owner of model summary interaction and validation.
- `EvidenceSummaryStore` remains the only owner of summary execution, source, artifact, and new attempt records.
- RuntimeService remains the authority boundary; the local model proposes only derived summary text and keywords.
- LangGraph remains the application workflow; existing platform routing still chooses direct versus Temporal-backed execution.
- Existing evidence eligibility and human-review decisions are unchanged.
- Historical nullable `keyword_coverage` data remains readable. New v2 work stops creating or depending on it; no data deletion or compatibility workflow is needed.

### State and Decision Ownership Matrix

| State or decision | Business question | Canonical record and field | Authorized writer | Readers | Derived copies | Allowed transitions | Conflict resolution |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Response validation | Does this completed response satisfy the summary contract? | `evidence_summary_attempts.state`, `outcome`, `validation_category`, `validation_explanation` | Summary service through summary store | Summary service, UI read model, tests | None | `reserved` attempt 1 -> `accepted` or `rejected`; only rejected attempt 1 -> `reserved` attempt 2 -> `accepted` or `rejected` | The unique cycle/unit/attempt reservation is claimed before a model call; duplicate delivery reads it and never calls the model. |
| Source outcome | Did this source version produce a valid final summary? | `evidence_summary_execution_sources.status`, `summary`, `keywords`, `evidence_sufficient`, `failure_category`, `failure_reason` | Summary store, called only by summary service | Graph, report qualification, UI, artifact reuse | Accepted summary artifact | `extracted` -> `summarizing` -> `completed` after an accepted final unit, or `failed` after a rejected final attempt 2 or dependency failure | A `completed` source with `evidence_sufficient: false` is visible but excluded from coverage and reporting. A dependency failure records `model_dependency_unavailable`; an existing accepted artifact wins over conflicting later writes. |
| Execution outcome | Did this selected group produce usable summaries? | `evidence_summary_executions.status` | Summary store | Temporal worker, LangGraph continuation, UI | Temporal result and durable-work view | `awaiting_execution` -> `summarizing` -> `completed` if at least one source completes with `evidence_sufficient: true`; otherwise `failed` | A stale reservation or provider failure marks its source failed and becomes an execution dependency failure; the store transaction determines outcome and Temporal cannot override it. |
| Research status | What is the task state shown to the operator? | `research_runs.status`, `status_version` | Unified LangGraph through research store | UI, RuntimeService, continuation | Checkpoint and Temporal history | Existing approved research transitions | Status version rejects stale continuation; research row wins. |
| Final report | What grounded report is available? | `agentic_research_reports.markdown` and provenance | Reporting service through agentic research store | Read-only UI route, operator | UI state | Absent -> stored when qualified summaries exist | UI reads only; failed sources never become report input. |

### Operational Checkpoint

- **Trigger**: Existing Discover Sources flow reaches eligible, relevant evidence selected for summarization.
- **Authority owner**: RuntimeService authorizes the research task; the summary service validates only derived content.
- **Canonical state**: `research_runs.status` remains operator-facing; summary records answer narrower summary questions.
- **Execution**: Existing routing selects direct or Temporal processing. Neither the model nor operator chooses.
- **Human decision**: Existing exact-version evidence acceptance remains unchanged. No human approval is needed for one bounded corrective response.
- **Exclusions**: No discovery, extraction, trust-rule, model-provider, capability, or historical-data change.

### Attempt Reservation And Conflict Handling

The store, not the model, reserves the next model-call slot before the summary
service asks Ollama for a response. One cycle is identified by the execution ID
and its existing `regeneration_attempt`; ordinary direct retries, Temporal
retries, and process restarts stay within that cycle. Only an explicitly
authorized regeneration begins the next cycle.

For one exact source version and summary unit, the only legal sequence is:

```text
no attempt -> reserved attempt 1 -> accepted
                                -> rejected -> reserved attempt 2 -> accepted
                                                                  -> rejected (source failed)
```

A reservation cannot be reclaimed by another worker. If it outlives the
configured model-request deadline plus 30 seconds, it is recorded as a
dependency failure and the existing dependency-failure path owns the execution
result. A duplicate caller returns the stored reservation or
result without another model call. A final accepted response writes its artifact
and source completion in one transaction; a later conflict preserves that
artifact and is surfaced safely. `retrying` is a UI view derived from a rejected
first attempt, not a second source-status value.

### After Design: Pass

Every durable decision and operator-visible state has one record, one writer, named readers, transitions, and conflict handling. No new architectural authority is required, so no new ADR is needed; ADR 0014 will be amended to describe the v2 output contract.

## Design Decisions

1. V2 model output contains only `summary`, `keywords`, and final-only `evidence_sufficient`.
2. The platform validates unique, non-empty keywords by normalized case-and-whitespace presence in the completed summary. Chunks use 3–5 keywords; final source summaries use 3–7.
3. A new append-only attempt record reserves each model-call slot before it is sent, then captures each accepted or rejected completed response without retaining raw output.
4. A rejected first response gets one complete corrective replacement request using the same bounded evidence input plus a safe validation category. Provider unavailability or a stale reservation is a dependency failure, not a corrective response.
5. An exhausted unit fails only its source; independent sources continue. A stale reservation or provider failure marks its affected source `model_dependency_unavailable` and fails the execution through the existing dependency path. No accepted artifact is created for a failed source.
6. A final response with `evidence_sufficient: false` is a valid completed source outcome, but it is excluded from coverage and reporting. An execution completes when at least one source completes with `evidence_sufficient: true`; it fails if none does or an execution-level dependency fails. The unified graph uses this stored result unchanged.
7. Qualified report input remains existing accepted artifacts only. Trusted platform code, not the report model, appends the omitted-source notice.
8. Add a read-only report endpoint and show it after Keywords in the existing Research workspace. The existing status panel shows failed source reasons and attempt counts.
9. Amend ADR 0014 and local evidence documentation for the new keyword rule and bounded recovery.

### Fixed Validation And Operator-Outcome Rules

Keyword presence is a deterministic phrase check: trim outer whitespace,
collapse internal whitespace, compare case-insensitively, preserve punctuation,
and require the complete normalized keyword phrase in the normalized summary.
The model never decides whether this rule passed.

Source and execution outcomes use the shared safe categories in the feature
data model. Each existing owning service writes only its own category and fixed
operator message. The evidence-summary service owns
`summary_contract_exhausted` and `model_dependency_unavailable`; web trust,
evidence review, acquisition, durable execution, and the owning store retain
their existing authority for all other categories. The Research workspace reads
the stored message; it does not infer a category from worker logs or Temporal.

## Project Structure

```text
apps/api/app/evidence_summaries/    # prompts, validation, attempt/store behavior
apps/api/app/agentic_research/      # grounded report composition and read model
apps/api/app/durable_execution/     # existing summary activity/workflow boundary
apps/api/app/main.py                # authenticated read-only report route
apps/api/tests/                     # unit, store, API, durable and integration tests
apps/web/src/App.tsx                # existing Research workspace status and report view
docs/adr/0014-governed-local-model-provider.md
docs/local-evidence-intelligence.md
specs/002-summary-recovery/         # design artifacts and generated tasks
```

**Structure Decision**: Extend the existing API, worker, store, reporting service, and Research workspace. Do not introduce a new service, package, database, or UI route family.

## Implementation Sequence

1. Update summary contracts, prompts, deterministic keyword validation, and prompt versioning. Preserve historical coverage fields as nullable/read-only data.
2. Add canonical attempt diagnostics and source-level failure metadata with uniqueness constraints and idempotent store methods.
3. Update direct and durable execution: one corrective response, source-level exhaustion, partial execution completion, and no-success failure.
4. Add trusted report omission disclosure and a workspace-scoped read-only report endpoint.
5. Extend the existing Research workspace with summary recovery outcomes and the stored final report.
6. Test invalid JSON, keyword failures, correction success, source exhaustion, all-source exhaustion, provider unavailability, duplicate delivery, restart, historical artifacts, trust exclusion, and report grounding.
7. Update ADR 0014 and local evidence documentation; run full API, web, docs, and Compose verification.

## Complexity Tracking

No constitutional violation or exception is proposed.
