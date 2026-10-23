# Implementation Plan: Topic Research Wiki

**Branch**: `011-topic-research-wiki` | **Date**: 2026-10-21 | **Spec**: [spec.md](spec.md)

## Summary

Turn the current local, source-grounded research run into one contribution to a
durable, workspace-scoped research topic. A topic becomes the operator-facing
notebook: it keeps question history, a traceable source library, immutable wiki
revisions, and a concise explanation of the latest change.

This extends the existing unified LangGraph workflow and `ResearchReportingService`.
It does not introduce another research orchestrator, trust-policy implementation,
or workflow-status state machine. A completed run supplies new qualified evidence
to the topic; the existing reporting boundary creates a new revision only when
the topic's qualified-evidence snapshot has actually changed.

## Technical Context

**Language/Version**: Python 3.12; TypeScript 5.8 / React 19  
**Primary Dependencies**: FastAPI, Pydantic, asyncpg, LangGraph, Temporal,
Ollama Python client, React, react-markdown  
**Storage**: PostgreSQL; LangGraph PostgreSQL checkpoints are execution-only  
**Testing**: pytest, FastAPI contract/integration tests, TypeScript build  
**Target Platform**: Local Docker Compose API, worker, PostgreSQL, Temporal,
Ollama, and browser UI  
**Project Type**: Local web application with API, worker, governed MCP host, and
React frontend  
**Performance Goals**: Preserve bounded local-model prompts and existing
durable-routing thresholds; topic reads must use stored artifacts and must not
start model work  
**Constraints**: Local-first; `qwen3:1.7b` remains untrusted and bounded;
blocked or unreviewed evidence never enters model context; no cloud service,
second state machine, or duplicate orchestration path  
**Scale/Scope**: One workspace may contain many topics; each topic may contain
many governed research runs and append-only wiki revisions. Studio is read-only
in this release.

## Constitution Check

### Existing ownership reconciliation

| Existing responsibility | Current owner and evidence | Plan decision |
| --- | --- | --- |
| Operator-visible research progress | `ResearchStore`, `research_runs.status`, and guarded transitions in `apps/api/app/web_research/store.py` | Reuse unchanged. A topic reads associated run status; it does not store duplicate progress. |
| Application sequence | `UnifiedResearchWorkflowEntry` and the LangGraph graph in `apps/api/app/agent_runtime/research_workflow.py` | Extend the existing entry and graph state with the selected topic identity. Do not create a notebook workflow. |
| Authority and agent capability grants | `RuntimeService` / `RuntimeStore`, governed MCP host, ADR 0016 | Reuse unchanged. Topic membership grants no search, extraction, browser, or policy authority. |
| Trust and human evidence review | `EvidenceTrustService` / `WebTrustStore` | Reuse unchanged. A wiki sees only evidence admitted by that boundary. |
| Summary and durable work | `EvidenceSummaryService` / `EvidenceSummaryStore` and Temporal | Reuse unchanged. A wiki reads stored completed artifacts only. |
| Planned subtopics, relevance, coverage, reports | `AgenticResearchStore` and `ResearchReportingService` | Extend this owner. A user Research Topic is distinct from the existing per-run Planned Topic. |
| Run report UI/API | `GET /v1/research/runs/{run_id}/report` and Research Workspace UI | Replace as the primary operator experience after cutover. Test-era report rows need not be preserved. |

### State and Decision Ownership Matrix

| State or decision | Business question | Canonical record and field | Authorized writer | Readers | Derived copies | Allowed transitions | Conflict resolution |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Topic identity | Which durable notebook contains this work? | `research_topics.id`, `workspace_id`, `normalized_name` | `TopicWorkspaceService` through `AgenticResearchStore` | API, UI, graph entry, reporting | Topic list and routes | Created once; rename is a separate future action | Unique workspace/name returns existing topic. |
| Question membership | Which topic owns this run? | `research_topic_runs.topic_id`, `run_id`, `input_kind` | `TopicWorkspaceService` transactionally | Graph, UI, reporting | Research view | Attached once; never silently moved | Unique run prevents two topic owners; same normalized question returns existing run. |
| Research progress | What stage is the question in? | `research_runs.status`, `status_version`, failure fields | Unified LangGraph through `ResearchStore` | UI, RuntimeService, API | transition history, checkpoints, Temporal history | Existing guarded transition table | Optimistic version wins; stale continuations reload and stop. |
| Topic attention gate | Must the operator resolve a required evidence decision before asking another question in this topic? | `web_evidence_trust_evaluations.disposition = review_required`, joined to `research_topic_runs.topic_id` through the evaluation's `run_id`; an item is resolved only when its latest `web_evidence_trust_overrides.outcome` is `accepted` or `rejected` and the override is active (`expires_at` is null or in the future) | `EvidenceTrustService` through `WebTrustStore` writes accept/reject overrides; unified graph writes question status through `ResearchStore` | `TopicWorkspaceService`, topic API, UI | Topic-level **Needs your decision** queue | Clear -> action required when a topic-associated run has review-required evidence with no active accepted/rejected override; action required -> clear when every pending evaluation has an active decision | The question route reloads the evaluation and active-override records while creating/reusing a question. A stale client receives a typed conflict with the current pending items. An expired acceptance becomes pending again. |
| Topic source membership | Which evidence versions are in the topic library? | `research_topic_sources.topic_id`, `evidence_id` | Topic contribution service through `AgenticResearchStore` | Sources UI, reporting | introduction history | Associate once; later encounters append provenance | Unique pair preserves one library item. |
| Wiki revision | What is the current grounded understanding? | `research_topic_wiki_revisions` and `research_topics.current_revision_id` | `ResearchReportingService` through `AgenticResearchStore`, called only by final-report node | Wiki UI, API, Research view | revision inputs/contributions/cache | No revision -> immutable N; current pointer advances only after snapshot persists | Topic row lock plus fingerprint comparison prevents stale overwrite. |
| Latest update | What did the newest qualifying question add or change? | `research_topic_wiki_updates.revision_id` and fields | `ResearchReportingService` transactionally | Wiki UI, Research view | rendered card | Written once with revision | Revision is not published without its update record. |
| Evidence use | May this evidence support model/wiki content? | Existing trust evaluations, overrides, relevance, coverage, summary records | Existing trust/review and coverage owners | Graph, reports, UI | topic views | Existing transitions only | Trust and exact-version human override win. |
| Capability authorization | May a node execute bounded web work? | Existing RuntimeStore assignment/grant/decision records | `RuntimeService` | Graph, MCP host, audit UI | MCP audit | Existing allow/deny lifecycle | Missing or stale grant is denied. |

### Plain-Language Decision Examples

**Example: evidence review blocks a follow-up question only until the operator
decides.** An operator researches a question in **Agentic web**. One captured
source requires review, so the topic workspace shows **Needs your decision**
with that source's title, URL, and reason. When the operator selects **Reject
evidence**, `WebTrustStore` records an override with `outcome = rejected` for
that exact trust evaluation. The source remains excluded from model context and
the wiki, but the attention item disappears because the operator has made the
required decision. The existing graph can continue its current question, and
the operator may now submit a later question in **Agentic web**. If the
operator's acceptance had an expiry and that expiry passes, the item becomes
pending again; a rejection has no expiry in the current review workflow.

### Operational checkpoint

- **Trigger**: authenticated operator creates/selects a topic and submits a
  plain-language research question. Before creating or reusing that question,
  the topic service checks the derived topic attention gate.
- **Authority/state**: `TopicWorkspaceService` creates topic-to-run membership.
  The unified graph remains the sole research sequence and sole writer of
  `research_runs.status` through `ResearchStore`.
- **Canonical storage**: PostgreSQL topic records hold notebook identity,
  membership, source association, and revisions. Existing evidence, trust,
  relevance, summary, and runtime records retain their current authority.
- **Direct/durable rule**: Topic creation and reads are direct. Existing
  thresholds still route preflight and summary work to Temporal. Wiki creation is
  bounded reporting work and never chooses its own infrastructure.
- **Human decision**: Existing exact-version accept/reject records remain the
  only review decision. The workspace presents them in a **Needs your
  decision** queue. An unresolved item prevents another question in the same
  topic; recording accept or reject clears that item without changing the
  topic's own state. Topic selection and wiki publication do not accept
  evidence.
- **Excluded**: no publishing, collaboration, free-form editing, Studio output
  generation, agent browser actions, or policy/capability changes.

### Migration and retirement

An ADR is required because this changes the durable product boundary from a
standalone report to a topic notebook. It will amend ADR 0016 without changing
the LangGraph, RuntimeService, Temporal, or trust boundaries.

The approved clean-start policy applies: test-era standalone runs and report
packages need not be regrouped. The standalone run-report UI/API is retired
after the topic API/UI and migration tests are complete. There will not be two
active report-generation paths.

**Gate status before design**: PASS.

### Design-alignment approval

**Approved on 2026-10-22.** The operator approved clean-start retirement of
test-era standalone reports, topic-scoped question reuse, extension of the
unified graph, `ResearchReportingService` as the sole wiki-revision builder,
operator-question-only entry in this release, and the derived **Needs your
decision** gate. The gate uses existing exact-version trust decisions and does
not create a topic workflow state.

## Project Structure

```text
specs/011-topic-research-wiki/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/topic-research-api.md
└── tasks.md                 # Created by /speckit-tasks

apps/api/app/
├── main.py
├── agent_runtime/research_workflow.py
├── agentic_research/{contracts.py,store.py,reporting.py,workflow_nodes.py}
├── web_research/{contracts.py,store.py}
└── tests/

apps/web/src/
└── App.tsx
```

**Structure Decision**: Extend the existing API, unified graph,
`AgenticResearchStore`, and React workspace. No new executable service,
worker, or orchestration project is introduced.

## Implementation Sequence

1. Write ADR 0017 and update roadmap, architecture diagram, and glossary. It
   must distinguish the durable user-facing Research Topic from existing
   model-planned subtopics.
2. Add topic identity, topic-to-run membership, topic-source provenance, wiki
   revision, and latest-update records through the explicit database
   bootstrap/migration boundary. Adopt topic-scoped question idempotency.
3. Add topic API contracts and routes: create/list/read topic, topic question,
   wiki/revision reads, research history, and source library reads.
4. Adapt `UnifiedResearchWorkflowEntry` so a topic question enters the existing
   graph with topic context. Keep all current stages and RuntimeService/MCP
   checks.
5. Adapt the final-report node and `ResearchReportingService` to create a
   topic-wide wiki revision from qualified stored summaries. A completed question
   produces zero or one revision; unchanged fingerprints record a no-change
   outcome.
6. Implement Wiki, Research, Sources, and read-only Studio views. The UI shows
   canonical run status and stored revision data only.
7. Retire the standalone run-report UI/API as the active path and remove
   obsolete callers/tests.
8. Add persistence, API, graph, migration, and UI tests for isolation, dedupe,
   provenance, review-required evidence and the topic attention gate, revision
   conflicts, no-change runs, failure/retry behavior, and source links.

## Approval Required Before Runtime Changes

Before runtime or UI code changes, confirm:

1. clean-start retirement of standalone test-era reports is acceptable;
2. topic names are unique per workspace and question dedupe is per topic;
3. the unified graph is extended, not replaced;
4. the existing report service is the sole wiki-revision builder; and
5. only an operator-initiated research question can start work in this feature;
   and
6. unresolved evidence-review decisions are shown and resolved before another
   question can begin in that same topic, without adding a topic workflow state.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| New durable topic and revision records | A notebook is distinct from a single run and needs immutable history | Fields only on `research_runs` cannot represent many questions, a current wiki pointer, and revision history without duplicating run status. |
