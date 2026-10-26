# Architecture Glossary

This glossary defines every named component in the
[current architecture](current-platform-architecture.md). Inputs are accepted
facts or requests; outputs are validated results, not merely model text.

## Operator and entry points

### Operator
- **Purpose:** Owns the research question and any required human evidence decision.
- **Inputs:** Platform results and review details.
- **Outputs:** Question, source limit, and explicit review decision.
- **Connected to:** Research UI and Admin Durable Work view.

### Research UI
- **Purpose:** Starts and displays the research workflow without exposing execution choices.
- **Inputs:** Operator question and total source count; stored API status.
- **Outputs:** `POST /v1/research/runs` and read requests.
- **Connected to:** Operator, FastAPI research APIs.

### Admin Durable Work view
- **Purpose:** Shows workspace-scoped preflight and summary work as read-only operational status.
- **Inputs:** Stored durable-work records.
- **Outputs:** Human-readable status; no workflow controls.
- **Connected to:** Operator, research durable-work API.

### `POST /v1/research/runs`
- **Purpose:** Authenticates and validates a request, finds or creates its research record, and enters the unified workflow.
- **Inputs:** Authenticated workspace, question, source limit.
- **Outputs:** Stored research status.
- **Connected to:** Research UI, ResearchStore, UnifiedResearchWorkflowEntry.

### UnifiedResearchWorkflowEntry
- **Purpose:** Starts or resumes the one production graph with a stable research and thread identity.
- **Inputs:** Research ID, workspace ID, validated workflow input.
- **Outputs:** Current stored workflow result or a durable wait state.
- **Connected to:** Research route, unified LangGraph, PostgreSQL checkpointer.

## Coordination and authority

### Unified LangGraph workflow
- **Purpose:** Coordinates topics, search, acquisition, trust, relevance, summaries, coverage, bounded gap searches, and reporting.
- **Inputs:** Stored research facts and typed service results.
- **Outputs:** Authorized service requests, business-state transitions, and final report.
- **Connected to:** RuntimeService, research services and stores, checkpointer, Temporal continuation.

### RuntimeService
- **Purpose:** Decides whether the assigned agent or platform step may perform a requested capability now.
- **Inputs:** Stable research, assignment, step, capability, resource, workspace, stage, and limit identifiers.
- **Outputs:** Stored allow or deny decision with reason, policy version, and correlation identity.
- **Connected to:** Unified graph, RuntimeStore, governed MCP host, ResearchStore.

### RuntimeStore
- **Purpose:** Persists agent assignments, capability grants, reservations, limits, and authorization decisions.
- **Inputs:** RuntimeService-owned records.
- **Outputs:** Canonical authority facts and audit history.
- **Connected to:** RuntimeService, MCP host, PostgreSQL, Admin Durable Work view.

### Governed MCP Host
- **Purpose:** Executes only registered capabilities after verifying a correlated RuntimeService allow decision.
- **Inputs:** Typed tool request plus stored authorization identity.
- **Outputs:** Normalized result, typed failure, and execution audit.
- **Connected to:** RuntimeService, RuntimeStore, SearXNG, governed extractor.

## Research and evidence services

### ResearchStore
- **Purpose:** Owns research records, discovered sources, captured evidence, audit events, and official workflow status.
- **Inputs:** Validated graph transitions and service results.
- **Outputs:** Canonical research state and known-source facts.
- **Connected to:** Research route, unified graph, RuntimeService, PostgreSQL.

### AgenticResearchStore
- **Purpose:** Owns planned topics, relevance decisions, topic coverage, gap attempts, and reports.
- **Inputs:** Validated graph-node results.
- **Outputs:** Research planning and coverage records.
- **Connected to:** Unified graph, topic and reporting services, PostgreSQL.

### SearXNG
- **Purpose:** Discovers public candidates for an authorized query.
- **Inputs:** Query and bounded result count.
- **Outputs:** Normalized candidate metadata.
- **Connected to:** Governed MCP host.

### Governed web extractor
- **Purpose:** Retrieves public content while enforcing network, redirect, type, and size safety.
- **Inputs:** Authorized candidate URL and retrieval limits.
- **Outputs:** Bounded evidence or typed failure.
- **Connected to:** Governed MCP host, CandidatePreflightService.

### CandidatePreflightService
- **Purpose:** Acquires candidates and coordinates their initial trust evaluation.
- **Inputs:** Research-owned candidates and acquisition policy.
- **Outputs:** Stored evidence and eligible, review-required, blocked, or failed status.
- **Connected to:** Unified graph, extractor, EvidenceTrustService, CandidatePreflightWorkflow.

### EvidenceTrustService
- **Purpose:** Decides whether an exact captured evidence version may enter automated model context.
- **Inputs:** Evidence and retrieval facts, policy version, applicable human review decision.
- **Outputs:** Explainable trust disposition and rule outcomes.
- **Connected to:** CandidatePreflightService, WebTrustStore, graph and model-facing services.

### WebTrustStore
- **Purpose:** Persists trust evaluations and exact-version human review decisions.
- **Inputs:** Trust-service decisions and authorized review decisions.
- **Outputs:** Effective evidence eligibility and audit details.
- **Connected to:** EvidenceTrustService, review API, PostgreSQL.

### TopicPlanningService
- **Purpose:** Validates up to three model-proposed topics for the operator question.
- **Inputs:** Question, prompt and model versions.
- **Outputs:** Valid topic plan or recorded model failure.
- **Connected to:** Unified graph, local model, AgenticResearchStore.

### TopicRelevanceService
- **Purpose:** Determines whether eligible evidence helps answer a planned topic.
- **Inputs:** Topic description and bounded eligible excerpt.
- **Outputs:** Exact YES/NO decision or recorded malformed-response failure.
- **Connected to:** Unified graph, local model, AgenticResearchStore.

### EvidenceSummaryService
- **Purpose:** Produces validated summaries, keywords, and keyword coverage from eligible evidence.
- **Inputs:** Stored eligible evidence and fixed processing contracts.
- **Outputs:** Summary artifacts or typed failure.
- **Connected to:** Unified graph, local model, EvidenceSummaryStore, EvidenceSummaryWorkflow.

### EvidenceSummaryStore
- **Purpose:** Owns summary execution status, source processing records, and summary artifacts.
- **Inputs:** EvidenceSummaryService results.
- **Outputs:** Reusable summaries, keywords, provenance, and durable status.
- **Connected to:** Summary service, graph, APIs, PostgreSQL.

### ResearchReportingService
- **Purpose:** Builds a grounded report only from eligible, relevant stored summaries.
- **Inputs:** Topics, coverage, summaries, and source references.
- **Outputs:** Validated Markdown report or typed failure.
- **Connected to:** Unified graph, local model, AgenticResearchStore.

### Research Topic
- **Purpose:** Durable operator notebook that groups related research
  questions, retained sources, and immutable wiki revisions.
- **Inputs:** Workspace identity, operator-chosen topic name, and existing
  research-run identifiers.
- **Outputs:** Topic membership, source provenance, current wiki pointer, and
  revision history.
- **Connected to:** TopicWorkspaceService, ResearchStore, AgenticResearchStore,
  Unified LangGraph workflow, and the topic workspace UI.

- **Purpose:** Creates and reads Topics, attaches a research question to one
  Topic, and derive whether a required evidence-review decision is pending.
- **Inputs:** Workspace identity, topic identity, question, canonical run state,
  and existing trust-review records.
- **Outputs:** Topic-scoped run creation or reuse, and a derived **Needs your
  decision** queue when a human decision is required.
- **Connected to:** AgenticResearchStore, ResearchStore, WebTrustStore, topic
  API routes, and the UnifiedResearchWorkflowEntry.

### Local Ollama model
- **Purpose:** Supplies bounded semantic proposals without platform authority.
- **Inputs:** Versioned prompt, bounded content, schema, fixed settings.
- **Outputs:** Untrusted response for service validation.
- **Connected to:** Planning, relevance, summary, gap-query, and reporting services.

## Durable execution and persistence

### Temporal
- **Purpose:** Preserves qualifying work across process failures and retries.
- **Inputs:** Server-selected workflow with stable stored identifiers.
- **Outputs:** Execution history and workflow result.
- **Connected to:** Temporal worker and registered workflows.

### Temporal worker
- **Purpose:** Runs the fixed preflight and summary workflows and continuation activity.
- **Inputs:** Temporal tasks.
- **Outputs:** Persisted service results and graph continuation request.
- **Connected to:** Temporal, CandidatePreflightWorkflow, EvidenceSummaryWorkflow, `continue_unified_research`.

### CandidatePreflightWorkflow
- **Purpose:** Makes threshold-selected multi-source acquisition restart-safe.
- **Inputs:** Stable research and candidate identifiers.
- **Outputs:** Persisted preflight results followed by graph continuation.
- **Connected to:** Worker, CandidatePreflightService, continuation activity.

### EvidenceSummaryWorkflow
- **Purpose:** Makes threshold-selected summary work restart-safe.
- **Inputs:** Stable summary execution and evidence identifiers.
- **Outputs:** Persisted summary results followed by graph continuation.
- **Connected to:** Worker, EvidenceSummaryService, continuation activity.

### `continue_unified_research`
- **Purpose:** Reloads canonical records and resumes the same graph after durable work finishes.
- **Inputs:** Stable research and graph thread identifiers plus completed-work type.
- **Outputs:** Resumed graph execution or a typed stop for stale, conflicting, terminal, or unauthorized state.
- **Connected to:** Temporal worker, ResearchStore, unified graph, checkpointer.

### LangGraph PostgreSQL checkpointer
- **Purpose:** Stores temporary graph bookmarks needed to resume node execution.
- **Inputs:** LangGraph thread state.
- **Outputs:** Latest valid execution checkpoint.
- **Connected to:** Unified graph, PostgreSQL.

### PostgreSQL
- **Purpose:** Holds all canonical business and audit records plus clearly separate graph checkpoints.
- **Inputs:** Writes through each owning store and the LangGraph checkpointer.
- **Outputs:** Durable state for services, APIs, graph recovery, and operator views.
- **Connected to:** All stores and the checkpointer; it is not accessed directly by the model.
