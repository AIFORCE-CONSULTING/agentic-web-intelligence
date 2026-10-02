# Implementation Plan: Grounded Final Reports

**Branch**: \`003-improve-final-report\` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)

## Summary

Extend the existing \`ResearchReportingService\` and LangGraph final-report node so a final report is a validated, traceable briefing rather than arbitrary Markdown returned by the local model. The platform will assemble a fixed snapshot of qualified topic evidence, request a structured report draft, validate it, make at most one correction request, and render stored report content into safe Markdown linked to source summaries. The platform, not the model, will create exclusion disclosures and retain every report package's evidence basis and attempt history.

This extends the unified research workflow. It does not introduce another report workflow, change source eligibility, add an operator action, or give the model authority over sources, policy, records, or workflow completion.

## Technical Context

**Language/Version**: Python 3.12 API; TypeScript 5.8 React client  
**Primary Dependencies**: FastAPI, Pydantic, Ollama Python client, LangGraph, React, \`react-markdown\`  
**Storage**: PostgreSQL through \`asyncpg\`; existing LangGraph PostgreSQL checkpoints  
**Testing**: \`pytest\` and \`ruff\`; TypeScript compiler and Vite build  
**Target Platform**: Local Docker Compose platform with a separately operated local Ollama provider  
**Project Type**: Web application (\`apps/api\` plus \`apps/web\`)  
**Performance Goals**: At most two local-model report attempts; when ten or more qualified inputs exist, normally 1,200-1,800 narrative words  
**Constraints**: Local/offline inference; temperature \`0.0\`; no raw evidence in the report prompt; input contains only eligible, relevant, evidence-sufficient summaries  
**Scale/Scope**: One report per canonical research run, with up to three planned topics

## Architecture Reconciliation

| Responsibility today | Existing owner and evidence | Plan |
| --- | --- | --- |
| Operator-visible research progress | \`UnifiedResearchWorkflowEntry\` and \`CanonicalResearchWorkflowNodes\` in \`apps/api/app/agent_runtime/research_workflow.py\`; \`research_runs.status\` via \`ResearchStore\` | Reuse unchanged. \`reporting -> completed\` happens after a report package is stored, whether its quality grade is `PASS` or `FAIL`. \`reporting -> failed\` is reserved for an inability to read inputs or store the report package. |
| Report sequence | LangGraph \`generate_final_report\` node in \`apps/api/app/agentic_research/workflow_nodes.py\` | Extend the same node. No second graph, route, or executor. |
| Report drafting and persistence | \`ResearchReportingService\` and \`AgenticResearchStore\` in \`apps/api/app/agentic_research/reporting.py\` and \`store.py\` | Extend. Replace nonempty-Markdown acceptance with typed draft validation, one correction attempt, and report provenance. |
| Report-input selection | \`AgenticResearchStore.report_sources\` joins topic coverage, summary, trust, and human-review facts | Reuse as the only input selector. Do not re-evaluate trust, relevance, coverage, summaries, or review. |
| Authority boundary | \`RuntimeService\`/\`ResearchAssignmentService\`, governed MCP host, \`RuntimeStore\`; ADR 0016 | Reuse unchanged. Report generation is an existing internal graph stage, not a new MCP capability. |
| Durable execution | Temporal-backed preflight and summary work; ADRs 0014/0016 | Reuse unchanged. Reporting remains direct inside the graph because it is bounded to two provider calls and adds no new external action. |
| Operator report view | Existing report endpoint in \`apps/api/app/main.py\` and Final report panel in \`apps/web/src/App.tsx\` | Extend response and panel to show safe stored-summary links, source lists, exclusions, and report failure state. |

### Ownership before and after

\`ResearchReportingService\` currently supplies dynamic qualified summaries to Ollama and accepts any nonempty Markdown. It will instead obtain a fixed input bundle from \`AgenticResearchStore\`, validate a structured model draft, and save a stored report package or an attempt record. \`AgenticResearchStore\` remains the sole owner of topics, coverage, reports, and report provenance.

\`ResearchStore\` remains the only writer of \`research_runs.status\`; the unified LangGraph wrapper calls \`ResearchStore.transition_status\`. The reporting service never marks a run complete. \`RuntimeService\` continues to authorize the existing research workflow but does not decide report quality, source qualification, or workflow status.

The existing single report endpoint and report panel remain the only report-reading path. A rejected draft, LangGraph checkpoint, or Temporal history is never displayed as a completed report. A structurally safe but incomplete model draft may be displayed only as the selected best usable report with a visible `FAIL` quality grade and its deterministic reasons. When no model draft is structurally safe, platform code creates a clearly labeled fallback evidence briefing from the fixed report input.

### Reuse, adaptation, retirement, and exclusions

| Area | Reuse | Adapt | Retire or exclude |
| --- | --- | --- | --- |
| LangGraph | Existing final-report node and status wrapper | Pass a stored report package to the existing completed transition; fail only when the package cannot be read or stored | No second graph, executor, or status machine |
| Research store | Qualified-source and coverage queries; report storage | Add immutable input, contribution, exclusion, quality-grade, and attempt records | Do not reinterpret a stored report from later live queries |
| Ollama | Existing provider, configured model, \`think=True\`, temperature, timeout | Use native JSON schema format for typed draft | No model-created URLs, Markdown links, eligibility, exclusions, or completion |
| API/UI | Existing report endpoint and panel | Add report package fields and safe link handling | No new Discover button, report-start API, or agent console |
| Historical reports | Existing rows remain audit data | New reports have contract, grade, and input snapshot | A legacy report is not represented as current complete work after a newer report or input mismatch |

### Direct-or-durable decision

The existing unified graph directly makes the report call. This feature allows only two local provider calls and introduces no independent retry loop, new external side effect, or batch. It stays direct. An unavailable provider or exhausted report contract produces a stored `FAIL` report-quality grade and fallback evidence briefing, not a failed research run. A future Temporal report workflow requires separate evidence and approval; it is not silently added here.

### ADR and documentation decision

Amend [ADR 0014](../../docs/adr/0014-governed-local-model-provider.md), rather than create a new ADR. The governed local-model boundary already owns response contracts and correction attempts; this feature makes that final-report contract stronger. It does not change the ownership of RuntimeService, LangGraph, Temporal, or trust policy.

## Constitution Check

**Pre-design result: PASS.** The design extends canonical owners and selected frameworks. It adds no competing workflow, policy, authority service, or business-state owner. All state, decision, transition, continuation, dependency-failure, and conflict rules are resolved below.

### State and Decision Ownership Matrix

| State or decision | Business question | Canonical record and field | Authorized writer | Readers | Derived copies | Allowed transitions | Conflict resolution |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Research workflow status | What stage or terminal outcome does the operator see? | \`research_runs.status\`, \`status_version\`, \`failed_stage\`, \`failure_code\`, \`failure_explanation\`, \`retryable\` | \`ResearchStore.transition_status\` through unified LangGraph wrapper | UI, API, RuntimeService, worker | LangGraph checkpoint, Temporal history, transition audit | Existing table: \`reporting -> completed\` after any report package is saved; \`reporting -> failed\` only when report inputs cannot be read or the package cannot be stored; retry resumes \`failed -> reporting\` | Optimistic version and transition IDs protect concurrent changes. Stored status wins over checkpoint/history. |
| Report input eligibility | Which summaries may support a report? | Existing \`agentic_topic_coverage_evidence\` joined with evidence-sufficient summary and active trust/review records | Existing coverage, trust, review, and summary owners | Reporting service, UI through stored package | Frozen report-input snapshot | Existing qualification lifecycle; no new transition | Existing coverage/trust records win. Snapshot mismatch makes report outdated, never silently reinterpreted. |
| Report-draft assessment | Did each model draft satisfy the report-quality contract, and what happened during the attempt? | New \`agentic_research_report_attempts.status\`, \`validation_errors\`, \`attempt_number\`, \`duration_ms\`, \`input_characters\`, and \`failure_code\` | \`ResearchReportingService\` through \`AgenticResearchStore\` | Reporting service, UI quality explanation, audit support | Retained raw Ollama response and diagnostic timing fields | \`started -> pass\`, \`started -> fail\`, or \`started -> unusable\`; only attempts 1 and 2 | Deterministic validator wins. Only schema-valid drafts whose every factual finding has a known, topic-scoped source reference and that contain no findings in insufficient sections are safe to render. Attempt diagnostics explain timeout, malformed-response, wrong-source, and quality-check failures without becoming report-quality authority. Among safe failing drafts, highest score wins across three equal-weight checks: planned-topic coverage, qualified-source representation, and applicable narrative length; a tie selects attempt two. |
| Report-quality grade | Did the stored report meet coverage, traceability, structure, and detail checks? | \`agentic_research_reports.quality_grade\` and \`quality_reasons\` | \`ResearchReportingService\` through \`AgenticResearchStore.save_report_package\` | Report endpoint, UI, audit support | Rendered quality badge and explanation | Created once as \`PASS\` or \`FAIL\`; immutable thereafter | Deterministic validator and fallback reason win. Grade does not alter source eligibility or research status. |
| Stored report | Which report may be shown as the current grounded report? | \`agentic_research_reports\` plus immutable child input, contribution, and exclusion rows | \`ResearchReportingService\` through \`AgenticResearchStore.save_report_package\` | Report endpoint, UI, audit support | Rendered Markdown/API DTO | Created from a passing draft, best usable failing draft, or platform fallback; never edited | Immutable input snapshot wins. Any mismatch causes stale/not-current display, not a false complete report. |
| Exclusion disclosure | Which sources were omitted and why? | New \`agentic_research_report_exclusions\` rows attached to stored report | \`AgenticResearchStore\` from existing source outcomes | Reporting service, API/UI | Rendered disclosure section | Created with report package; immutable thereafter | Recorded summary, relevance, trust, and review outcomes generate reason; model cannot add or suppress it. |
| Model authority | What can the local model decide or change? | No business-state field; versioned prompt, JSON schema, and validator | Trusted platform code | Reporting service and evaluation tests | Stored model/prompt/contract versions and attempt response | No authority transition | Anything outside schema or known source references is rejected. RuntimeService and trust policy stay independent. |

### Continuation, retry, and dependency rules

- **UI:** Displays \`research_runs.status\` and its failure fields, never a graph checkpoint or Temporal state. It displays a current stored report package with its `PASS` or `FAIL` quality grade and reasons.
- **Authorization:** RuntimeService evaluates existing assignment, role, capability, resource, workflow-stage, workspace, and budget facts; it does not evaluate report quality or write research progress.
- **Interrupted execution:** The graph checkpoint may resume work, but each node reloads \`research_runs\`. A checkpoint's \`report_stored\` value is not proof that a report was accepted.
- **Retries:** One invocation has at most two model attempts. A later operator retry creates a new idempotent attempt set and preserves previous attempt records. A failed quality grade alone does not require an operator retry because a report has already been stored.
- **Concurrent starts:** Existing normalized-question target keys and status versions ensure one canonical run; later callers read or resume it rather than start another report path.
- **Dependency failure:** Missing Ollama or unusable model output causes a stored fallback report with a `FAIL` grade. Only an unavailable report-input store or an inability to save the package causes \`research_runs.status = failed\`.

## Design

### Fixed report input and structured draft

1. \`AgenticResearchStore\` builds a report-input bundle from planned topics, qualified coverage records, and server-derived exclusions. Each input has a stable source reference, title or URL fallback, source URL, topic, summary artifact identity, evidence content hash, and exact summary text.
2. \`ResearchReportingService\` sends only that fixed bundle to Ollama, organized by planned topic. Its system instruction treats every supplied summary as untrusted reference data and forbids following instructions within it.
3. Ollama returns Pydantic-schema JSON: topic sections, source-referenced findings, section source references, and explicit insufficient-evidence sections. It does not emit URLs, HTML, raw Markdown links, exclusions, or completion state.
4. Trusted Python first validates structural safety: valid schema, every factual finding has at least one known topic-scoped source reference, and no findings appear in insufficient-evidence sections. It then evaluates three equal-weight quality checks: planned-topic coverage, qualified-source representation, and applicable narrative length. A `PASS` requires all three checks. A structurally safe `FAIL` retains the failed-check reasons; a fallback briefing is used when structural safety fails.
5. Python renders accepted output into Markdown and creates claim attributions and complete topic source lists from stored references. It adds server-generated exclusions outside model output. Links lead to stored summaries, not model URLs.
6. A failing first attempt is stored with raw response, validation reasons, model, prompt, contract, input fingerprint, fixed-input character count, elapsed duration, and failure code. One correction call receives the same fixed bundle plus only the unmet requirements. If neither attempt passes, trusted code considers only structurally safe drafts: valid schema, every factual finding has a known topic-scoped source reference, and no findings in insufficient sections. It selects the draft with the highest score across three equal-weight checks: planned-topic coverage, qualified-source representation, and applicable narrative length; a tie selects attempt two. If neither attempt is structurally safe or Ollama is unavailable, trusted code creates a clearly labeled fallback evidence briefing from the fixed input and gives it a `FAIL` grade. Its reason code distinguishes unavailable model, malformed response, and unsafe model draft. The existing graph completes after storing either report package.

### Attribution, source roles, and exclusions

Server-rendered claim links and section source lists use existing stored-summary UI selection behavior. The model cannot create arbitrary hyperlinks. The prompt requires cautious role wording. Deterministic code can prove cited source membership but cannot fact-check all natural-language semantics, so offline evaluation adds role fixtures for products, protocols, frameworks, organizations, and standards.

For a completed summary excluded from topic coverage, the server names every assessed topic and concise recorded reason, for example: \"Assessed for Agentic-web technologies: recorded relevance outcome was not relevant to this topic.\" Trust blocks, review-required sources without a current human acceptance, insufficient summaries, and failed summaries remain visibly separate from report evidence.

## Project Structure

\`\`\`text
specs/003-improve-final-report/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── final-report-api.md
└── tasks.md                  # Created later by /speckit.tasks

apps/
├── api/app/
│   ├── agentic_research/{contracts.py,reporting.py,store.py,workflow_nodes.py}
│   ├── agent_runtime/research_workflow.py
│   ├── web_research/store.py
│   └── main.py
│   └── tests/
└── web/src/App.tsx

docs/
├── adr/0014-governed-local-model-provider.md
└── roadmap.md
\`\`\`

**Structure Decision**: Extend existing API reporting, research-store, and UI modules. No service process, worker, store owner, or database outside PostgreSQL is added.

## Post-Design Constitution Check

**PASS.** The report package is provenance under \`AgenticResearchStore\`, not a second eligibility or workflow authority. LangGraph stays the sole application workflow; \`ResearchStore\` remains status writer; RuntimeService remains authority owner; and Temporal remains limited to its existing qualifying work. Model output is validated before it becomes operator-visible. Runtime or workflow code remains pending explicit design-alignment approval.
