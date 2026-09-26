# Architecture Diagram Glossary

This glossary defines every person, boundary, service, workflow, store, and
external component shown on the [Current Platform Architecture](current-platform-architecture.md)
diagram. It describes the platform as it works today, including components that
are implemented but disconnected or overlap an earlier component.

The definitions are grounded in the platform ADRs, especially
[ADR 0004](adr/0004-governed-web-research-mvp.md),
[ADR 0005](adr/0005-governed-agent-runtime-contract.md),
[ADR 0013](adr/0013-governed-durable-execution-contract.md),
[ADR 0014](adr/0014-governed-local-model-provider.md),
[ADR 0015](adr/0015-local-policy-controlled-web-trust.md), and
[ADR 0016](adr/0016-governed-local-agent-capability-requests.md).

## People and user interfaces

### Operator

- **Purpose:** The person who starts research, reviews results, and inspects
  durable work. The operator remains responsible for decisions that require
  human judgment.
- **Inputs:** A research question, a requested source count, and any later
  review or control decisions.
- **Outputs:** Research requests and explicit operator decisions.
- **Connected to:** The **Research UI** and **Admin UI**.

### User Interfaces

- **Purpose:** The diagram boundary containing the screens through which an
  operator uses and monitors the platform.
- **Inputs:** Operator questions, settings, and control actions, plus status and
  evidence returned by the API.
- **Outputs:** Validated API requests and human-readable research or operational
  views.
- **Connected to:** The **Operator** and the **FastAPI Application**.

### Research UI

- **Purpose:** The primary research screen. It lets an operator enter a
  question, choose the total number of sources, start discovery, and review
  stored research results.
- **Inputs:** The operator's question, requested source count, and review
  actions.
- **Outputs:** A request to `POST /v1/research/runs` and polling requests to the
  research status and evidence APIs.
- **Connected to:** The **Operator**, **POST `/v1/research/runs`**, and
  **Research status and evidence APIs**.

### Admin UI

- **Purpose:** Gives an operator visibility into durable and governed runtime
  work, including status and permitted control actions.
- **Inputs:** Operator inspection and control requests.
- **Outputs:** Requests to the runtime inspection and control APIs and displays
  of the returned runtime state.
- **Connected to:** The **Operator** and **Runtime inspection and control APIs**.

## API application

### FastAPI Application

- **Purpose:** The server boundary that authenticates requests, validates API
  contracts, exposes research and administrative endpoints, and hosts the
  application services shown inside it.
- **Inputs:** HTTP requests from the user interfaces and completion results from
  internal or durable services.
- **Outputs:** Stored status, evidence, reports, and typed error responses.
- **Connected to:** Both user interfaces, the research paths, the governed web
  and evidence services, Temporal workflows, and PostgreSQL-backed stores.

### POST `/v1/research/runs`

- **Purpose:** Starts or returns research for an operator question. Today this
  route still controls the detailed inline sequence; the planned design makes
  it a thin entry point into the unified LangGraph.
- **Inputs:** An authenticated research request containing the question and
  source limit.
- **Outputs:** A stored research-run status response and work started through
  the active research path.
- **Connected to:** The **Research UI** and **Inline orchestration in
  `main.py`**. Its dotted connection to **Unified LangGraph** marks work that is
  not yet completed.

### Research status and evidence APIs

- **Purpose:** Let the Research UI read research progress, discovered sources,
  trust outcomes, summaries, keywords, and other stored evidence results.
- **Inputs:** Authenticated identifiers and read or review requests from the
  Research UI.
- **Outputs:** Stored research state and evidence suitable for operator review.
- **Connected to:** The **Research UI** and the research data held in
  PostgreSQL through application stores.

### Runtime inspection and control APIs

- **Purpose:** Expose the earlier governed runtime for inspection and permitted
  controls. They do not currently provide an endpoint that creates a runtime
  research run.
- **Inputs:** Authenticated administrative inspection or control requests.
- **Outputs:** Runtime status, events, and accepted control results.
- **Connected to:** The **Admin UI** and **RuntimeService**.

## Active research path

### Active Research Path

- **Purpose:** The diagram boundary for the research sequence currently started
  by the Discover Sources button.
- **Inputs:** A validated research request from `POST /v1/research/runs`.
- **Outputs:** Stored sources, evidence, trust results, summaries, keywords, and
  research status.
- **Connected to:** The research route, governed search and evidence services,
  and PostgreSQL through **ResearchStore**.

### Inline orchestration in `main.py`

- **Purpose:** Coordinates today's active sequence of search, source storage,
  candidate preflight, and summary processing directly from the API route.
- **Inputs:** The validated question, source limit, current research record, and
  results returned by each called service.
- **Outputs:** Service calls, stored progress, and the status returned to the
  route.
- **Connected to:** **POST `/v1/research/runs`**, **ResearchStore**,
  **SearXNG search provider**, **CandidatePreflightService**, and
  **EvidenceSummaryService**.

### ResearchStore

- **Purpose:** Provides the active workflow's database operations for research
  runs, sources, captured evidence, and research audit events.
- **Inputs:** Validated records and state changes from the active research path.
- **Outputs:** Stored identifiers, current research state, known-source checks,
  and evidence records.
- **Connected to:** **Inline orchestration in `main.py`** and **PostgreSQL**.

## New agentic research path

### New Agentic Research Path

- **Purpose:** The diagram boundary for the implemented agentic workflow that
  will eventually replace detailed route-level coordination.
- **Inputs:** A validated research objective and limits from the API entry point.
- **Outputs:** Planned topics, governed research actions, relevance decisions,
  topic coverage, and a grounded final report.
- **Connected to:** The planned research route connection, the unified graph,
  agentic control and storage services, governed evidence services, and
  PostgreSQL.

### Unified LangGraph

- **Purpose:** Represents the intended single application-level research
  workflow: plan topics, search, acquire and evaluate evidence, decide topic
  relevance, summarize, check coverage, and produce a report. It is implemented
  but is not yet started by Discover Sources.
- **Inputs:** A validated research objective, source and loop limits, stored
  state, and typed results from platform services.
- **Outputs:** The next permitted service request, updated graph state, topic
  coverage, and final report status.
- **Connected to:** **AgenticResearchControlService**,
  **AgenticResearchStore**, **SearXNG search provider**,
  **CandidatePreflightService**, **TopicRelevanceService**,
  **EvidenceSummaryService**, and **ResearchReportingService**. The dotted
  Temporal links show that durable completion cannot yet resume this graph.

### AgenticResearchControlService

- **Purpose:** Applies platform-owned limits to model-proposed research work,
  including capability checks, query reservations, attempt limits, and the
  maximum number of gap-search rounds. It currently overlaps some authority
  already represented by RuntimeService and therefore requires consolidation.
- **Inputs:** A proposed research action, authenticated research context,
  available capabilities, and current attempt or loop counts.
- **Outputs:** A typed allow or reject result and an audit record of the
  decision.
- **Connected to:** **Unified LangGraph**, **AgenticResearchStore**, and, by the
  red dotted relationship, **RuntimeService**.

### AgenticResearchStore

- **Purpose:** Stores records introduced for the agentic workflow separately
  from source keywords, including planned topics, relevance decisions, topic
  coverage, capability audits, and final reports.
- **Inputs:** Validated agentic workflow records and state changes.
- **Outputs:** Current topic and coverage state, previous decisions, audit
  history, and stored reports.
- **Connected to:** **Unified LangGraph**, **AgenticResearchControlService**, and
  **PostgreSQL**.

## Earlier governed runtime

### Earlier Governed Runtime

- **Purpose:** The diagram boundary for the platform's earlier general-purpose
  governed agent runtime. Its authority model remains important, but its old
  research execution path has no active creation or scheduling caller.
- **Inputs:** Runtime control requests and, historically, durable runtime work.
- **Outputs:** Governed runtime state, steps, events, and approved capability
  requests.
- **Connected to:** The runtime APIs, old LangGraph executor, governed MCP host,
  Temporal, and PostgreSQL.

### RuntimeService

- **Purpose:** Enforces the earlier runtime contract for roles, capability
  grants, state transitions, human gates, retries, handoffs, and runtime audit.
  It is an authority boundary, not the local web-trust policy itself.
- **Inputs:** Validated runtime commands, current runtime state, capability
  requests, and human decisions.
- **Outputs:** Permitted state transitions, rejected commands, capability
  grants, and audit events.
- **Connected to:** **Runtime inspection and control APIs**, **RuntimeStore**,
  **Old LangGraph executor**, and historically **GovernedRuntimeWorkflow**. Its
  authority overlaps **AgenticResearchControlService**.

### RuntimeStore

- **Purpose:** Provides database access for the earlier runtime's runs, steps,
  memory records, and events.
- **Inputs:** Validated runtime records and transitions from RuntimeService.
- **Outputs:** Canonical runtime state and history.
- **Connected to:** **RuntimeService** and **PostgreSQL**.

### Old LangGraph executor

- **Purpose:** Executes the earlier research graph, which searches the complete
  goal and extracts only the first result. It is used by the older durable
  runtime workflow, not by the Research UI's active Discover Sources path.
- **Inputs:** A governed runtime goal and permitted web capabilities.
- **Outputs:** Runtime transitions and requests to the governed MCP tools.
- **Connected to:** **GovernedRuntimeWorkflow**, **RuntimeService**, and the
  **Governed MCP Host**.

## Governed web and evidence services

### Governed Web and Evidence Services

- **Purpose:** The diagram boundary containing the platform's controlled search,
  retrieval, trust, relevance, summarization, and reporting capabilities.
- **Inputs:** Typed requests from an approved orchestration path and content or
  model results from controlled providers.
- **Outputs:** Normalized search results, captured evidence, trust decisions,
  relevance decisions, summaries, keywords, and reports.
- **Connected to:** The active research path, unified LangGraph, earlier runtime,
  Temporal workflows, Ollama, service stores, and external web providers.

### Governed MCP Host

- **Purpose:** The sole agent-facing boundary for web capabilities established
  by ADR 0004. It validates and audits bounded `web.search` and `web.extract`
  requests so an agent never receives raw provider or browser access.
- **Inputs:** Typed search or extraction requests from an authorized runtime.
- **Outputs:** Normalized search results or extracted evidence, plus audit data
  and typed failures.
- **Connected to:** **Old LangGraph executor**, **SearXNG search provider**, and
  **Governed web extractor**.

### SearXNG search provider

- **Purpose:** Performs open-source web discovery for a supplied query. It is a
  provider, not the owner of research policy or workflow decisions.
- **Inputs:** A search query and bounded result count.
- **Outputs:** Candidate source metadata, including URLs, titles, and available
  search-result descriptions.
- **Connected to:** **Inline orchestration in `main.py`**, **Unified LangGraph**,
  and the **Governed MCP Host**.

### Governed web extractor

- **Purpose:** Retrieves a permitted public webpage and turns the response into
  bounded evidence while enforcing network and redirect safety controls.
- **Inputs:** A candidate URL and platform-owned retrieval limits.
- **Outputs:** Captured content, requested and final URL facts, redirect outcome,
  retrieval metadata, or a typed extraction failure.
- **Connected to:** The **Governed MCP Host** and
  **CandidatePreflightService**.

### CandidatePreflightService

- **Purpose:** Acquires candidate sources early, evaluates whether their content
  can enter the evidence workflow, and records the outcome. It routes larger
  batches to Temporal for durable execution.
- **Inputs:** Candidate source records, research context, acquisition limits,
  and the requested batch size.
- **Outputs:** Captured evidence and per-source states such as eligible,
  review-required, blocked, or failed.
- **Connected to:** **Inline orchestration in `main.py`**, **Unified LangGraph**,
  **Governed web extractor**, **EvidenceTrustService**, and
  **CandidatePreflightWorkflow**.

### EvidenceTrustService

- **Purpose:** Serves as the single local trust-policy authority for captured
  webpage versions. It evaluates deterministic policy and controls whether
  evidence may enter automated model context. It does not decide topic
  relevance.
- **Inputs:** Captured evidence facts, policy version, source and retrieval
  metadata, and any applicable recorded human override.
- **Outputs:** An explainable disposition such as `eligible`,
  `eligible_with_notice`, `review_required`, or `blocked`, with rule outcomes.
- **Connected to:** **CandidatePreflightService**, **TopicRelevanceService**,
  **EvidenceSummaryService**, and **WebTrustStore**.

### WebTrustStore

- **Purpose:** Stores trust evaluations, the policy version used, individual
  rule outcomes, observed source and retrieval facts, and authorized human
  review decisions.
- **Inputs:** Validated records from EvidenceTrustService and approved review
  actions.
- **Outputs:** Existing trust decisions and overrides for later enforcement and
  explanation.
- **Connected to:** **EvidenceTrustService** and **PostgreSQL**.

### TopicRelevanceService

- **Purpose:** Determines whether an eligible evidence version actually helps
  answer a planned research topic. It accepts only an exact `YES` or `NO` model
  response; malformed responses are recorded as model failures.
- **Inputs:** A topic description and a bounded excerpt from evidence that has
  passed the trust workflow.
- **Outputs:** A stored relevant, not-relevant, or model-failure decision.
- **Connected to:** **Unified LangGraph**, **EvidenceTrustService**, and the
  **Local Ollama model**.

### EvidenceSummaryService

- **Purpose:** Produces source summaries and keywords from stored evidence that
  is allowed into automated model context. It preserves whole-page coverage by
  chunking and consolidating bounded model responses.
- **Inputs:** Eligible stored evidence, fixed server-owned prompts, model and
  chunking settings, and source provenance.
- **Outputs:** Validated summaries, keywords, chunk coverage, provenance, or a
  typed model failure.
- **Connected to:** **Inline orchestration in `main.py`**, **Unified LangGraph**,
  **EvidenceTrustService**, **Local Ollama model**, **EvidenceSummaryStore**, and
  **EvidenceSummaryWorkflow**.

### EvidenceSummaryStore

- **Purpose:** Stores source summaries, keywords, chunk and consolidation
  records, processing status, prompt and model versions, and source provenance.
- **Inputs:** Validated derivative evidence produced by EvidenceSummaryService.
- **Outputs:** Existing summaries and processing records for display, reuse,
  topic coverage, and final reporting.
- **Connected to:** **EvidenceSummaryService** and **PostgreSQL**.

### ResearchReportingService

- **Purpose:** Produces the final research report from stored evidence that is
  both trust-eligible and relevant to an approved topic. It must not synthesize
  from blocked, review-required, irrelevant, or raw unapproved content.
- **Inputs:** Stored eligible source summaries, topic descriptions, coverage
  records, and a fixed report prompt.
- **Outputs:** A grounded final report or a typed failure when the supporting
  evidence is insufficient or the model response is invalid.
- **Connected to:** **Unified LangGraph** and the **Local Ollama model**.

### Local Ollama model (`qwen3:1.7b`)

- **Purpose:** Provides local semantic reasoning for bounded tasks such as topic
  planning, relevance classification, evidence summarization, keyword
  extraction, and report synthesis. It proposes content; it has no platform
  authority.
- **Inputs:** Bounded text, explicit server-owned instructions, a required
  response format, and fixed model settings.
- **Outputs:** Untrusted model responses that platform code must validate before
  use or storage.
- **Connected to:** **TopicRelevanceService**, **EvidenceSummaryService**, and
  **ResearchReportingService**. ADRs 0014 and 0016 prohibit direct access to the
  database, MCP, Temporal, credentials, files, or the network.

## Temporal durable execution

### Temporal Durable Execution

- **Purpose:** The diagram boundary for work that must survive API timeouts,
  process restarts, or longer processing times. Temporal makes approved work
  durable; it does not set policy or grant authority.
- **Inputs:** Already validated work descriptions and stable identifiers from
  platform services.
- **Outputs:** Durable progress, retries, completion results, and operational
  status.
- **Connected to:** The API services that start durable work, the Temporal
  workflows, the Temporal worker, and PostgreSQL-backed canonical records.

### Temporal worker

- **Purpose:** Runs registered Temporal workflow and activity code outside the
  API request process.
- **Inputs:** Scheduled workflow tasks for preflight, evidence summaries, or the
  earlier governed runtime.
- **Outputs:** Activity results, retry and completion status, and updates made
  through platform-owned services and stores.
- **Connected to:** **CandidatePreflightWorkflow**,
  **EvidenceSummaryWorkflow**, and **GovernedRuntimeWorkflow**.

### CandidatePreflightWorkflow

- **Purpose:** Makes multi-source preflight work durable when the batch contains
  more than two sources.
- **Inputs:** An already accepted preflight job containing stable research and
  candidate identifiers.
- **Outputs:** Per-source acquisition and trust results that can be stored and
  inspected after retries or restarts.
- **Connected to:** **CandidatePreflightService** and the **Temporal worker**.
  Its dotted connection to **Unified LangGraph** records the current missing
  continuation: completion does not yet resume the graph.

### EvidenceSummaryWorkflow

- **Purpose:** Makes evidence summarization durable when the platform's
  deterministic workload threshold is reached.
- **Inputs:** An already approved summary job referencing stored evidence and
  fixed processing settings.
- **Outputs:** Persisted summary and keyword results, typed failures, and durable
  completion status.
- **Connected to:** **EvidenceSummaryService** and the **Temporal worker**. Its
  dotted connection to **Unified LangGraph** records the current missing
  continuation.

### GovernedRuntimeWorkflow

- **Purpose:** The older durable workflow for the earlier governed runtime. It
  can run the old LangGraph executor, but no active caller currently creates or
  schedules this workflow.
- **Inputs:** Historically, an authorized runtime run identifier and immutable
  execution envelope.
- **Outputs:** Durable execution of the old graph and runtime state updates.
- **Connected to:** **Old LangGraph executor**, **RuntimeService**, and the
  **Temporal worker**.

## Canonical data

### PostgreSQL

- **Purpose:** Holds the platform's canonical persisted state. Services may
  compute decisions, and Temporal may execute work durably, but neither replaces
  the database as the lasting business record.
- **Inputs:** Validated research, evidence, trust, runtime, audit, summary,
  topic, coverage, and report records written through platform stores.
- **Outputs:** Durable current state and history returned through those stores
  to APIs, services, workflows, and user interfaces.
- **Connected to:** **ResearchStore**, **AgenticResearchStore**,
  **RuntimeStore**, **WebTrustStore**, and **EvidenceSummaryStore**.

