# Roadmap

This roadmap emphasizes what the platform will do next. Earlier work is retained
in the [Completed work](#completed-work) section for context, not as the main
planning view.

## Phase 10 - Automated Wiki Builder

Turn the completed topic wiki foundation into a research assistant that keeps a
topic current over time. The operator remains responsible for choosing the
research goal and resolving consequential feedback; the platform performs the
bounded, repeatable research work.

- [ ] Let an operator schedule recurring research for a topic, including the
  question or research angle, cadence, and an initial limit of **30 discovered
  sources per scheduled research cycle**.
- [ ] Run scheduled discovery, source reuse, acquisition, trust evaluation,
  relevance, summarization, and topic coverage through the existing governed
  workflow. A schedule must never bypass the local trust policy, human evidence
  review, source de-duplication, or platform-selected direct/Temporal routing.
- [ ] Incorporate qualified findings from each completed cycle into the living
  wiki as a dated update. Clearly show what was added, revised, excluded, or
  remains unanswered since the preceding update.
- [ ] Surface a pending human decision prominently and stop the affected topic's
  automated progression until the operator accepts or rejects the exact evidence
  version. A scheduled job must not silently ignore a feedback loop.
- [ ] Provide a simple operator view to inspect, pause, resume, and remove a
  topic schedule and review its completed and skipped research cycles.

## Phase 11 - Private Access and Portable Wiki Sharing

Make a locally run wiki useful beyond the computer that created it, without
turning the current local development deployment into an accidental public
service.

- [ ] Design and implement authenticated private-network access so an operator
  can use their local wiki from another personal device, such as a phone. Define
  the network, identity, session, and device-trust boundary before exposing the
  platform beyond `localhost`.
- [ ] Export a selected topic as a portable wiki package containing its readable
  wiki revisions, source summaries, original URLs, provenance, keywords, and
  clearly labeled inclusion or exclusion outcomes.
- [ ] Let another locally run platform import a shared package without treating
  imported material as newly retrieved or automatically trusted evidence. Keep
  the package origin and its source history visible to the receiving operator.
- [ ] Provide an intentional sharing path for publishing a downloadable topic
  package online, with operator control over what is included and no automatic
  exposure of local credentials, audit-only information, or private workspace
  data.

## Phase 12 - Personal Email Organizer

After the automated wiki builder is reliable, apply the same source-grounded
research and organization approach to a person's email.

- [ ] Design narrowly scoped, provider-approved email intake for major email
  services, with explicit account consent, read-only access, and local handling
  of message content.
- [ ] Organize email-derived information into topic wikis using the established
  evidence, summary, keyword, provenance, review, and feedback-loop patterns.
- [ ] Define separate privacy, retention, deletion, and sharing controls for
  email before any provider integration is enabled.

## Parking Lot

The following work remains planned but is intentionally deferred until concrete
product and deployment requirements justify it.

### Later product and collaboration opportunities

- **Coverage follow-up strategy** — after the current bounded gap-search limit
  is reached, decide whether an operator should be offered additional targeted
  research, a different follow-up question, or a clearly labeled partial wiki
  update. This must remain an explicit product decision: the current workflow
  performs no more than two automated follow-up searches and then reports from
  the qualified evidence it has.
- **Topic-plan feedback** — add optional thumbs-up and thumbs-down feedback to
  the operator's topic-plan view. For negative feedback, record a simple reason
  such as a missing subject, irrelevant topic, overlapping topics, weak search
  query, or unsuitable topic count, with optional comments. Associate feedback
  with the research task, plan, model artifact, and prompt version so recurring
  failures can become new offline evaluation cases. Do not automatically train
  or change the model from an individual response.
- **GitHub Projects integration** — connect the platform's planning workflow
  to GitHub Projects so an operator can build a roadmap, create tasks, and
  update their priority quickly.
- **Source-candidate review usability** — make each source candidate URL a
  clickable external link that opens in a new browser tab, and request/display
  longer article descriptions so an operator has more context before choosing
  a source for extraction.
- **Manual topic-source intake** — let an operator deliberately submit a known
  URL, document, or file to an existing research topic. It must enter the same
  governed research path as discovered material, retain its operator-provided
  origin, and never bypass RuntimeService, web trust, human review, relevance,
  summary, or provenance. Define the document/file intake boundary separately
  before implementation.
- **Grounded Research Chat** — an authenticated, evidence-grounded chat
  experience on the local model-provider boundary. It would answer only from
  selected workspace-owned research evidence, cite sources, surface uncertainty
  when evidence is insufficient, and keep sessions, permissions, retention, and
  model configuration platform-owned. The model would receive no MCP tools,
  browser, filesystem, database, runtime, or credential access. Future hosted
  providers could use the same adapter without making cloud credentials a
  requirement for local open-source deployments.
- **Observability** — LangFuse, OpenTelemetry, metrics, and evaluation.
- **Durable data lifecycle** — configurable retention and archival operations
  for durable workflow metadata when real deployment requirements justify them;
  security audit history remains separately governed.
- **Production deployment** — Kubernetes, Azure deployment patterns, scaling,
  security hardening, and release automation.

### Later security and policy work

These items remain important, but they are not on the critical path to the
automated wiki-builder outcome above. Revisit them when their related product
capability is ready to use them.

- **Monitor Cerbos for future authorization needs** — revisit Cerbos as a
  possible policy evaluator behind `RuntimeService` when the platform has many
  more roles, tools, resource types, tenant-specific policies, or policy changes
  managed independently of application releases. This is not approval to replace
  the current authority boundary or create another live capability path.
- **Trust-policy re-evaluation after refresh or policy change** — re-evaluate
  evidence when governed refresh functionality or an applicable policy change
  exists.
- **C2PA provenance validation** — validate C2PA provenance for supported file
  assets while recording ordinary HTML as a distinct case, not as invalid solely
  because it has no asset-level provenance manifest.
- **Expanded trust-policy validation** — validate policy enforcement, policy
  changes, refresh, overrides, workspace isolation, prompt-injection resistance,
  and direct-versus-durable routing.
- **Trust-policy management** — design a separately authorized workflow for
  changing local trust-policy rules, potentially through a purpose-built MCP
  capability. The current operator view remains read-only; no UI or agent may
  change enforcement rules directly.
- **Evidence freshness and re-capture** — design a governed way to refresh a
  stored source before enforcing a freshness limit. Today the platform reuses
  evidence already retained for a source and intentionally does not re-fetch it
  during discovery.
- **Agent-readiness profile** — record observed agent-facing capabilities for a
  source without treating them as a trust score or eligibility decision. Future
  observations may include semantic structure, JSON-LD, documented APIs,
  declared WebMCP tools, and read-only or consequential tool hints.
- **Evidence adequacy** — determine whether extraction produced meaningful
  source content rather than a navigation shell, paywall, login page, or shared
  template.
- **Publisher access declaration** — record applicable `robots.txt` instructions
  for the platform's declared automated client identity. Use this to inform
  responsible retrieval behavior, never as authorization or a source trust score.
- **Agent-action boundary and safe inspection** — when a source declares
  WebMCP, OpenAPI, MCP, or another machine-action interface, record its
  existence while keeping it outside the research extractor. A future tightly
  controlled browser-inspection capability may observe declared tools, but must
  never invoke them.

## Completed work

<details>
<summary>Show completed Phases 1–9</summary>

### Phases 1–2 - Foundation and Governed Web Intelligence

Established the monorepo, React/FastAPI applications, Docker environment,
documentation site, CI, governed MCP web discovery and extraction, provenance,
operator/developer experiences, and GitHub Pages documentation publishing.

### Phase 3 - Agent Runtime

Established server-owned LangGraph workflows, typed capability boundaries,
bounded roles and handoffs, audit events, and expiring run-scoped provenance
memory.

### Phase 4 - Enterprise Services

Added authentication, authorization, tool governance, secret handling, and
related operational controls.

### Phase 5 - Durable Execution

Added mandatory Temporal infrastructure for qualifying long-running work,
durable workflow contracts, checkpointing, restart/resume behavior, and
operator-visible durable-work controls.

### Phase 6 - Local Evidence Intelligence

Added a governed local Ollama provider, chunked evidence summarization,
keywords, prompt and output validation, and automatic direct-versus-Temporal
routing without an operator choosing the execution mechanism.

### Phase 7 - Governed Web Trust and Architecture Refactoring

Added the local web-trust policy, candidate preflight, redirect diagnostics,
human evidence review, and the unified architecture that keeps RuntimeService
as the authority boundary, LangGraph as the one research coordination path,
Temporal as the durable-execution mechanism, and PostgreSQL as the canonical
business record.

### Phase 8 - Agentic Research Workflow

Added bounded topic planning, topic coverage, relevance decisions, offline
model evaluation, governed capability requests, quality-graded final reports,
topic-scoped source references, and resilient topic-report rendering.

### Phase 9 - Topic Research Wiki

Added durable Research Topics, topic-scoped question reuse, evidence and source
history, versioned wiki revisions, latest-update summaries, visible human
review feedback loops, and Wiki, Sources, and Tools views.

</details>
