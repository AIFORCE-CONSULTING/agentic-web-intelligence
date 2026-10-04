# Implementation Plan: Correct Report Exclusion Labels

**Branch**: `008-fix-exclusion-labels` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/008-fix-exclusion-labels/spec.md`

## Summary

Correct the stored report exclusion disclosure so sources that were blocked or
unreachable during acquisition are not described as merely not relevant to the
planned topics. The change extends the existing report-package path:
`ResearchReportingService.final_report` still asks `AgenticResearchStore` for
report exclusions, and `AgenticResearchStore.report_exclusions` remains the one
place that derives operator-facing exclusion reason codes from already-stored
source, trust, summary, evidence-sufficiency, and relevance outcomes.

This is a reporting clarity fix. It does not change extraction, trust policy,
human review, topic relevance, summarization, LangGraph workflow state,
Temporal execution, or report findings.

## Technical Context

**Language/Version**: Python 3.12 API; TypeScript/React web client only if label display text needs a small UI adjustment  
**Primary Dependencies**: FastAPI, Pydantic, asyncpg/PostgreSQL, existing React report panel  
**Storage**: Existing PostgreSQL report-package tables through `AgenticResearchStore`; no new tables required  
**Testing**: pytest for API/store/reporting behavior; existing web build if UI copy changes  
**Target Platform**: Local Docker Compose development stack  
**Project Type**: Web application with API, worker, and browser UI  
**Performance Goals**: No additional model calls, no additional web retrieval, and no material report-generation latency change  
**Constraints**: Reasons must be derived deterministically from stored platform outcomes; the model must not infer or rewrite exclusion reasons  
**Scale/Scope**: One exclusion reason per excluded source in a stored report package; existing current and historical report behavior preserved

## Constitution Check

**Pre-design result: PASS.** The feature extends the existing report exclusion
derivation owned by `AgenticResearchStore`. It adds no competing workflow,
state machine, policy authority, store, model decision, human approval,
Temporal workflow, or LangGraph path.

### Architecture Reconciliation

| Responsibility | Existing owner and evidence | Plan |
| --- | --- | --- |
| Report workflow trigger | The unified LangGraph `generate_final_report` node calls `ResearchReportingService.final_report` (`apps/api/app/agentic_research/workflow_nodes.py`, `apps/api/app/agent_runtime/research_workflow.py`). ADR 0016 says the final-report node remains the sole report caller. | Reuse unchanged. The graph still invokes the same service and receives the same report-stored outcome. |
| Report package generation | `ResearchReportingService.final_report` (`apps/api/app/agentic_research/reporting.py`) loads report inputs and exclusions, renders/stores the report package, and does not let the model author exclusion disclosures. ADR 0014 describes validated final-report packages. | Reuse unchanged. No new report-generation route or service is added. |
| Exclusion disclosure | `AgenticResearchStore.report_exclusions` (`apps/api/app/agentic_research/store.py`) derives `ReportExclusion` rows from `research_sources`, preflight status, summary execution status, evidence sufficiency, and topic coverage. | Extend this method so reason codes distinguish trust blocks, publisher access denial, unreachable content, summary failure, insufficient evidence, and true topic irrelevance. |
| Exclusion persistence | `AgenticResearchStore.save_report_package` writes immutable `agentic_research_report_exclusions` rows attached to the stored report. | Reuse unchanged unless tests reveal a contract-only type/naming update is needed. Existing rows remain historical. |
| Report read path | `AgenticResearchStore.get_report` returns stored exclusions through `ResearchReport`; `GET /v1/research/runs/{run_id}/report` exposes the report; the React report panel renders `report.exclusions`. | Reuse. UI can display the server-generated reason as-is. Add UI label tests only if the UI maps reason codes. |
| Source acquisition and trust | Web trust/preflight and evidence acquisition own preflight status, redirect/access outcomes, and trust dispositions. ADR 0015 governs local web trust; ADR 0016 keeps trust/relevance/reporting separate. | Reuse as read-only inputs. Do not retry acquisition or reinterpret trust policy. |
| Topic relevance | Topic relevance service records `relevant`, `not_relevant`, or `model_failure` for captured eligible evidence. ADR 0016 reserves relevance for topic-specific evidence decisions. | Reuse as read-only input. "Not relevant to planned topics" is used only after usable evidence and summary exist and no topic coverage includes the source. |

### State and Decision Ownership Matrix

| State or decision | Business question | Canonical record and field | Authorized writer | Readers | Derived copies | Allowed transitions | Conflict resolution |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Report exclusion reason | Why did this discovered source not contribute to report findings for this stored report? | `agentic_research_report_exclusions.reason_code` and `reason` rows attached to a report package | `AgenticResearchStore.save_report_package`, using values produced by `AgenticResearchStore.report_exclusions` during `ResearchReportingService.final_report` | Report endpoint, UI Final report panel, tests, future audit views | Rendered "Sources not used for report findings" section | Created once with the report package; immutable thereafter | Stored report exclusion row wins for that historical report. If live source outcomes later change, a newer report package may have different rows; older rows are not reinterpreted. |
| Source preflight outcome | Could the platform capture usable evidence from the discovered source and did it pass local trust checks? | `research_sources.preflight_status`, `preflight_reason`, `preflight_trust_disposition`, `preflight_final_url` | Existing preflight/trust workflow through `ResearchStore` and trust services | Exclusion builder, UI candidate preflight, research workflow | Report exclusion reason, candidate preflight display | Existing preflight lifecycle only; this feature adds no transition | Preflight/trust block or acquisition failure wins over later generic relevance wording because it prevented usable evidence. |
| Summary outcome | Did captured evidence produce a usable stored source summary? | `evidence_summary_execution_sources.status`, `failure_category`, `evidence_sufficient`, and linked artifact | Evidence summary service/store | Exclusion builder, report input selector, UI summaries | Report exclusion reason and report inputs | Existing summary lifecycle only; this feature adds no transition | Summary failure or insufficient evidence wins over topic relevance wording because no qualified summary exists for report findings. |
| Topic relevance / coverage outcome | Did a completed summary count toward a planned topic? | Topic relevance and coverage records loaded through `AgenticResearchStore.report_inputs` and `list_topic_coverage` | Existing topic relevance and coverage services/stores | Report input selector, exclusion builder, report service | Report inputs and report exclusion reason | Existing relevance/coverage lifecycle only; this feature adds no transition | Only when preflight, summary, and evidence sufficiency are not excluding the source may the exclusion builder use `not_relevant_to_planned_topics`. |

For workflows:

- **UI display value:** The UI displays stored `ResearchReport.exclusions[*].reason`
  and may use `reason_code` for styling or future filtering. It does not infer
  the reason from candidate status.
- **Authorization value:** RuntimeService evaluates existing workflow authority
  and capabilities; it does not evaluate report exclusion reasons.
- **Continuation:** LangGraph checkpoints are not used to derive exclusion
  reasons. The final-report node reloads canonical stored source outcomes.
- **Retries and concurrency:** A retry that creates a new report package creates
  a new immutable exclusion snapshot. Existing report packages remain historical.
- **Dependency failure:** If source outcome records cannot be read or the report
  package cannot be saved, existing report failure behavior applies. This
  feature does not add a new dependency.

### Operational Checkpoint

- **Trigger:** Existing unified research workflow reaches `generate_final_report`
  and calls `ResearchReportingService.final_report`.
- **Authority owner:** RuntimeService remains the capability authority boundary;
  exclusion wording is not an authorization decision.
- **Canonical state:** Stored report package rows, especially
  `agentic_research_report_exclusions.reason_code` and `reason`.
- **Execution rule:** Direct execution inside the existing report path. No
  Temporal workflow is needed because the change only derives labels from stored
  records and performs no long-running or external work.
- **Human decisions:** No human decision is introduced or changed. Existing
  evidence review acceptance/rejection remains separate.
- **Excluded callers/capabilities:** No new UI button, MCP tool, report-start
  endpoint, browser worker, trust-policy rule, source retry, or model prompt.

### Post-Design Constitution Check

**Result: PASS.** Phase 0 and Phase 1 artifacts preserve the same owners. The
data model refines existing report-exclusion reason codes; the contract
describes the existing report response shape; and the quickstart verifies the
canonical report path without introducing parallel state or workflow.

## Project Structure

### Documentation (this feature)

```text
specs/008-fix-exclusion-labels/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── report-exclusion-contract.md
└── tasks.md
```

### Source Code (repository root)

```text
apps/api/app/agentic_research/
├── contracts.py          # ReportExclusion contract/type documentation if needed
├── reporting.py          # Existing report service caller, reused unchanged
└── store.py              # Exclusion reason derivation and persistence owner

apps/api/tests/
├── test_agentic_research.py
├── test_agentic_research_reporting.py
└── test_research_report.py

apps/web/src/
└── App.tsx               # Only if UI code maps reason codes instead of displaying reason text
```

**Structure Decision**: Use the existing API reporting and report-read
structure. Most work belongs in `apps/api/app/agentic_research/store.py` with
targeted tests. UI changes are optional and should be avoided unless the
current panel cannot display the clearer server-generated reasons.

## Complexity Tracking

No constitution violations are present. No new architectural complexity is
introduced.
