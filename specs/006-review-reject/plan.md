# Implementation Plan: Human Evidence Review Rejection

**Branch**: `006-review-reject` | **Date**: 2026-10-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-review-reject/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Review-required evidence can currently be inspected and accepted by a human
operator, but it cannot be rejected. That leaves the operator with an awkward
choice: accept the evidence or leave the research run waiting indefinitely.
The current workflow also tries to enter `awaiting_review` from relevance
evaluation, but the official research-status transition table does not permit
that move.

The implementation will extend the existing web-trust review path instead of
adding a second review system. `EvidenceTrustService` and `WebTrustStore` will
continue to own human evidence-review decisions; `ResearchStore` will continue
to own operator-facing research status; the unified LangGraph workflow will
resume the same paused research thread after either an accepted or rejected
human decision. Rejected evidence remains stored and visible for audit, but it
never becomes eligible for automated model context, summaries, keyword cards,
topic coverage, or final reports.

## Technical Context

**Language/Version**: Python 3.12 API service; TypeScript/React web UI  
**Primary Dependencies**: FastAPI, Pydantic, asyncpg, React, LangGraph, Temporal Python SDK  
**Storage**: PostgreSQL business tables through `WebTrustStore`, `ResearchStore`, and existing research/evidence stores  
**Testing**: pytest for API, store, and unified workflow tests; existing frontend build/tests as available  
**Target Platform**: Local Docker Compose platform with API, web, worker, PostgreSQL, SearXNG, Ollama, and Temporal  
**Project Type**: Web API, React operator UI, and background workflow service  
**Performance Goals**: Review actions are single-source operator actions and should complete with the same responsiveness as the existing accept action; rejecting one source must not restart discovery or extraction.  
**Constraints**: Do not delete evidence or trust records; do not add automatic model/agent review decisions; do not create another workflow, policy authority, store, or research start path; do not let LangGraph or Temporal become the source of business truth.  
**Scale/Scope**: One exact evidence version per operator review action; one waiting research run resumes after the stored decision is recorded.

## Constitution Check

*GATE: Passed before Phase 0 research; re-checked after Phase 1 design below.*

- **Canonical owner:** Existing owners are reused. `EvidenceTrustService` in
  `apps/api/app/web_trust/service.py` owns the rules for human evidence-review
  decisions; `WebTrustStore` in `apps/api/app/web_trust/store.py` owns the
  persisted review decision. `ResearchStore` in
  `apps/api/app/web_research/store.py` owns `research_runs.status` and the
  legal transition table. The unified LangGraph entry in
  `apps/api/app/agent_runtime/research_workflow.py` resumes the existing
  paused thread. ADR 0015 establishes local web-trust dispositions, and ADR
  0016 keeps human evidence acceptance separate from agent reasoning and
  execution.
- **State and decision ownership:** Matrix below names the official record,
  writer, readers, derived copies, transitions, and conflict outcome for every
  touched state/decision.
- **No parallel authority:** The plan does not add a second review service,
  another policy implementation, a new state machine, another store, or a new
  operator workflow. It extends the current acceptance path to record
  `accepted` or `rejected` outcomes for the same exact review-required
  evidence version.
- **Selected foundations:** LangGraph continues coordinating the research
  workflow and resumes from its checkpoint only after stored human review.
  RuntimeService remains the authority boundary for agent/tool capabilities,
  but it does not make the human review decision. Temporal remains unchanged
  for durable preflight and summary work. PostgreSQL remains the official
  business and audit record.
- **Model boundary:** Models, agents, MCP tools, workers, and background
  processes may observe that evidence is waiting for review, but only an
  authenticated human operator may accept or reject it. Model output is never
  treated as a review decision.
- **Migration and retirement:** Existing acceptance records remain readable and
  will be treated as `accepted`. Existing accept callers keep their endpoint
  and behavior. A new reject endpoint and UI action share the same trust-review
  owner. No old workflow path is retired because the current path is extended,
  not replaced.
- **Operational checkpoint:** Trigger is the operator pressing Accept or Reject
  in the human review panel for a specific review-required evidence version.
  Human-decision authority is `EvidenceTrustService`; canonical review state is
  stored by `WebTrustStore`; operator-facing workflow status is stored by
  `ResearchStore`; work runs directly through the API and unified graph resume,
  not a new Temporal workflow. Excluded callers are models, agents, MCP tools,
  unauthenticated clients, and background workers acting without a stored human
  decision.
- **Approval:** This plan is ready for user architecture approval before
  runtime or workflow code changes.

### State and Decision Ownership Matrix

| State or decision | Business question | Canonical record and field | Authorized writer | Readers | Derived copies | Allowed transitions | Conflict resolution |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Evidence trust base disposition | What did the deterministic local trust policy decide about this captured evidence version before human review? | `web_evidence_trust_evaluations.disposition` for `source_url` + `content_hash` | `EvidenceTrustService.evaluate` through `WebTrustStore.record_evaluation` | Web-trust API, UI, unified graph relevance node, summary service, report services | API read models and UI state | Immutable after insert; a newer evaluation for a different policy/content version may supersede it for lookups | Base disposition is immutable. If a later human decision exists, base disposition remains visible as `base_disposition` while effective disposition is computed separately. |
| Human evidence review decision | Did a human operator allow or deny this exact review-required evidence version for automated model use? | `web_evidence_trust_overrides.outcome` (`accepted` or `rejected`), optional reviewer note, `actor_user_id`, `evaluation_id`, `created_at`, optional expiry/workflow resume fields | `EvidenceTrustService.accept` and new `EvidenceTrustService.reject` through `WebTrustStore` | Web-trust API, UI, unified graph resume, relevance/summary/report filtering, audit views | LangGraph resume payload, API response, UI panel | No decision -> accepted or rejected; accepted/rejected is terminal for the exact active evidence version unless the record expires or a future explicit replacement feature is approved | Stored human decision wins over checkpoint or UI state. Conflicting second decisions return conflict and do not silently replace the first effective decision. Existing rows without `outcome` are treated as `accepted`. |
| Effective evidence eligibility | May this evidence version enter automated model context now? | Computed by `WebTrustStore.latest_evaluation`: base disposition plus active human decision outcome | `WebTrustStore` computes from canonical trust evaluation and human decision rows | Unified graph relevance node, summary service, report service, UI/API | `EvidenceTrustEvaluation.disposition` response, candidate preflight display | `review_required` + accepted -> effective `eligible`; `review_required` + rejected -> remains excluded/reviewed rejected; eligible/blocked base dispositions cannot become accepted/rejected through review | Base policy and human decision records win. Rejected evidence is never converted to eligible by workflow resume data. |
| Research workflow status | What stage or terminal outcome should the operator see for this research task? | `research_runs.status`, plus `status_version`, failure fields, and transition audit | Unified LangGraph wrapper through `ResearchStore.transition_status` | UI, API routes, RuntimeService, workflow nodes, worker continuations | LangGraph checkpoint state, Temporal histories, API read models | Add `evaluating_relevance -> awaiting_review`; existing review path remains `awaiting_review -> evaluating_relevance`, `awaiting_review -> assessing_coverage`, or `awaiting_review -> failed` | Stored `research_runs` row wins. Checkpoints and Temporal histories never advance or roll back official status. Stale writers reload official state or fail safely. |
| Workflow continuation after review | Has the stored human decision been linked to the graph resume request for this paused run? | `web_evidence_trust_overrides.workflow_thread_id`, `workflow_status_version`, `workflow_resume_requested_at` for the active decision | `EvidenceTrustService.record_workflow_resume` through `WebTrustStore.record_workflow_resume` | Unified graph entry, audit/debug views, retry path | LangGraph `Command(resume=...)` payload | No resume recorded -> resume recorded once; retry may reuse the same stored decision and status version or fail safely on stale status | Stored review decision must exist before resume is requested. If resume fails after recording, retry reloads the stored decision and continues; it must not create a duplicate business outcome. |

For workflows, also state:

- The UI displays `research_runs.status` for the run and the web-trust
  evaluation plus human decision outcome for each evidence version.
- RuntimeService evaluates existing research assignment, role, capability, and
  official run status. It does not accept or reject evidence.
- Interrupted work resumes from the LangGraph checkpoint only after the stored
  human decision exists. The checkpoint resume payload carries the outcome for
  execution, but it is not the business record.
- Retries are idempotent because the exact evidence version can have one active
  effective human decision. Repeated reject/accept attempts after a decision
  return the existing decision or a conflict instead of creating a new outcome.
- Concurrent requests are resolved by the persisted decision row and current
  run status version. The first durable effective decision wins for the exact
  active evidence version.
- If dependencies are unavailable, the API returns a retryable error after the
  business record is either not written or written and auditable. Workflow
  recovery reloads the canonical decision before resuming.

## Project Structure

### Documentation (this feature)

```text
specs/006-review-reject/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── review-reject-api.md
└── tasks.md              # Created later by /speckit.tasks
```

### Source Code (repository root)

```text
apps/api/app/web_trust/contracts.py
apps/api/app/web_trust/service.py
apps/api/app/web_trust/store.py
apps/api/app/web_research/store.py
apps/api/app/agent_runtime/research_workflow.py
apps/api/app/agentic_research/workflow_nodes.py
apps/api/app/main.py
apps/api/tests/test_web_trust.py
apps/api/tests/test_web_research.py
apps/api/tests/test_unified_research_workflow.py
apps/web/src/App.tsx
apps/web/src/styles.css
docs/local-evidence-intelligence.md
docs/adr/0015-local-policy-controlled-web-trust.md
docs/adr/0016-governed-local-agent-capability-requests.md
```

**Structure Decision**: Extend the current API trust-review modules, unified
workflow entry, official research status store, and existing React review
panel. Tests stay with the existing web-trust, research-store, and unified
workflow test suites. Documentation updates stay with the current local
evidence intelligence page and ADRs that already describe web trust and
agentic workflow boundaries.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitution violations are required for this plan.

## Phase 0 Research Summary

See [research.md](./research.md). Key decisions:

- Extend the current web-trust human decision owner instead of creating a new
  review workflow.
- Add an explicit human decision outcome while treating existing acceptance
  records as accepted.
- Resume the same LangGraph thread after either accepted or rejected decisions.
- Fix the official status transition table so relevance evaluation can pause
  for review.

## Phase 1 Design Summary

See [data-model.md](./data-model.md), [quickstart.md](./quickstart.md), and
[contracts/review-reject-api.md](./contracts/review-reject-api.md).

## Post-Design Constitution Re-Check

*GATE: Passed after Phase 1 design.*

The design extends existing owners and records: web trust owns the human
decision, research status stays in `research_runs.status`, LangGraph remains
the coordinator, Temporal remains unchanged, and PostgreSQL remains the
business/audit record. No model, MCP tool, background worker, or alternate
workflow can accept or reject evidence. The only new operator action is Reject,
which uses the same review boundary as Accept and keeps rejected evidence
excluded from automated model context.
