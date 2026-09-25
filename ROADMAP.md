# Roadmap

## Phase 1 - Foundation (complete)

- Repository scaffold and contribution standards
- React + FastAPI application boundaries
- Docker Compose local environment
- MkDocs Material documentation site
- Architecture Decision Records
- CI validation and repository templates

## Phase 2 - Governed Web Intelligence (complete)

Deliver an evidence-producing web-research workflow through a governed MCP boundary.

- LangGraph workflow with approved web-search and extraction tools
- MCP host, source provenance, basic tool policy, and execution audit history
- Developer and operator portal for the console, API reference, documentation, and service health
- Publish the MkDocs documentation site with GitHub Pages

## Phase 3 - Agent Runtime (complete)

- Server-only LangGraph planning, execution, and review workflows
- Fixed roles and capabilities, typed state, policy-validated handoffs, and audit events
- Run-scoped, expiring provenance memory
- Bounded reviewer-to-researcher revision pattern with safe escalation

## Phase 4 - Enterprise Services (complete)

Add authentication, authorization, tool registry, secrets, and governance.

## Phase 5 - Durable Execution (complete)

Add Temporal, long-running workflows, and human-in-the-loop operations.

- Define the durable-workflow contract, including authority, retry, timeout,
  cancellation, idempotency, retention, and escalation rules.
- Add a local Temporal deployment and a server-only adapter for one approved
  runtime execution path.
- Persist validated checkpoints and let authenticated operators inspect,
  cancel, and resolve durable work.
- Add explicit human approval and revision wait states without creating an
  agent-controlled authority path.
- Validate restart, resume, workspace isolation, cancellation, and ambiguous
  effect behavior end to end.

## Phase 6 - Local Evidence Intelligence (complete)

Add a local-first, optional open-weight model capability for generated evidence
summaries and page-level keywords.

- Define the [local-model provider boundary](../adr/0014-governed-local-model-provider.md):
  native local Ollama by default, no automatic model download, no model tools,
  and no new agent authority.
- Add local-model configuration, model-artifact verification, health, and
  resource guidance for Qwen3 1.7B on modest local hardware.
- Create evidence-only summarization and keyword contracts with strict input,
  output, provenance, and schema validation rules.
- Process complete pages through bounded overlapping chunks, then consolidate
  page summaries and key phrases with coverage and source-chunk references.
- Run Temporal as mandatory platform infrastructure. The platform selects a
  direct path for one-source, one-chunk summaries and automatically uses the
  durable workflow for multi-source or multi-chunk processing; an operator
  never chooses the execution mechanism.
- Add an operator UI to request, inspect, and distinguish generated summaries
  from extracted source evidence.
- Validate local quality, model-unavailable behavior, prompt-injection
  resistance, workspace isolation, and direct-versus-durable routing.

## Phase 7

### Refactoring

- [ ] Use the existing keyword groups to generate a cross-source synthesis for
  each shared keyword. Each synthesis identifies what the linked source
  summaries have in common, where they differ, and their relevant caveats.
- [x] Keep one canonical research run for each normalized web-search target. A
  repeated **Discover sources** action performs a fresh provider search but
  never creates a duplicate target container.
- [x] On repeated discovery, append and acquire/preflight only source URLs that
  are not already present anywhere in the workspace database. Preserve prior
  evidence, trust evaluations, and summaries without re-fetching or
  re-summarizing them.
- [x] Add a workspace-wide keyword-centered operator view: render each keyword
  as a visual card and list every related stored source summary beneath it. A
  source may appear under more than one keyword, and each source link opens its
  stored source summary rather than the original external webpage.
- [x] Raise the governed discovery result limit from 5 to 50 sources so the
  platform can acquire and evaluate a broader initial evidence set.
- [x] Revisit both the chunk and final summarization prompts and their output
  contracts. Every stored keyword now has a persisted, validated supporting
  sentence from its source summary, and source summaries record the fixed
  prompt version used to create them.

### Agentic Research Workflow

Build a local research agent that can carry out a bounded web-research task.
The operator owns the research question. The agent identifies useful research
steps, while platform code validates and performs each search, evidence, trust,
storage, and execution action.

#### Foundations already completed

- [x] Define the general capability boundary in ADR 0016. A local model may
  request an approved platform capability, but platform code remains responsible
  for validating, executing, recording, and routing the request.
- [x] Complete a narrow offline evaluation of `qwen3:1.7b` requesting a future
  public cookie-preference capability. Retain the result as preliminary evidence
  about that one request. It does not establish that the model can complete the
  full research workflow.

#### Research-agent design and evaluation

- [x] Rewrite ADR 0016 around the complete agentic research workflow, including
  topic planning, source research, evidence eligibility, topic coverage, bounded
  gap searches, final reporting, platform authority, and human review.
- [x] Update ADR 0014 so the existing evidence summarizer remains a separate,
  no-tool model role while ADR 0016 governs the research agent.
- [x] Define and validate the topic-planning response. For one operator question,
  the model may propose no more than three focused topics. Each topic contains a
  stable `topic_id`, a plain-language topic description, and one web-search query.
- [x] Store topic coverage separately from source keywords. Evidence counts
  toward a topic only after the platform has acquired usable content, allowed it
  through the trust workflow, accepted it as relevant to that topic, and stored
  its summary and keywords.
- [x] Add a strict topic-relevance decision using the topic description and a
  bounded excerpt from an eligible evidence version. Accept only an exact `YES`
  or `NO`; record every malformed response as a model failure instead of
  silently interpreting it as approval.
- [x] Define the agent's initial research capability catalog. It begins with
  bounded search and evidence-acquisition requests through the existing governed
  runtime and MCP host. Cookie-preference handling may be added only after that
  capability is separately implemented and approved.
- [x] Keep request validation, source reuse and de-duplication, trust-policy
  enforcement, database writes, retry limits, loop counters, and audit records
  in platform code. The model may suggest the next research action, but the
  application checks whether it is allowed, prevents repeated searches, limits
  evidence-acquisition attempts, and stops additional missing-evidence searches
  after two rounds. These decisions and counts are stored in the database so a
  restart cannot erase them. Existing application components continue to reuse
  evidence, prevent duplicate sources, apply the trust policy, save records, and
  retain the history of accepted and denied requests.
- [x] Build a versioned offline evaluation for the complete workflow. Cover topic
  planning, relevance decisions, duplicate sources, eligible, blocked, and
  review-required evidence, malformed model responses, hostile webpage
  instructions, missing-topic searches, loop limits, and final-report grounding.
- [x] Run every evaluation case repeatedly with fixed model settings. Record the
  model version, prompt version, test version, expected result, actual result,
  and resource use.
- [x] Select `qwen3:1.7b` for the bounded research workflow after it passed all
  20 complete-workflow evaluation cases in five repeated attempts. Fourteen of
  15 topic plans passed on the first response; the remaining response omitted
  the website perspective and passed after the one permitted correction. Keep
  prompt and response validation, one bounded correction, and fail-closed
  handling as required parts of the selected system. This decision prioritizes
  useful local research on modest hardware without requiring a paid cloud model.
  It clears the model-evaluation gate but does not by itself enable live research
  capabilities.

#### Implementation

The approved unified LangGraph refactor is the implementation plan for this
group. It replaces the active inline research sequence with one cohesive
LangGraph workflow while preserving the services and stored records that
already work.

1. [x] **Define the unified workflow state.** The LangGraph working state now
   carries the research run and workspace identifiers, operator question, total
   source limit, planned topics, uncovered topics, gap-search count, workflow
   stage, and failure information. This is temporary execution context;
   PostgreSQL remains the official business and audit record.
2. [ ] **Build the unified LangGraph workflow.** Coordinate topic planning,
   topic searches, the task-wide source limit, duplicate skipping, governed
   evidence acquisition, trust evaluation, topic relevance, summaries and
   keywords, topic coverage, no more than two missing-topic search rounds, and
   a grounded final report. The graph structure and bounded coverage routing are
   complete. Connection to production services is in progress: the production
   topic-planning service and its graph node are complete, while the remaining
   nodes are not yet connected.
3. [ ] **Reuse the existing platform services.** The graph must coordinate the
   governed search and extraction boundary, `ResearchStore`, candidate
   preflight, evidence trust and review, topic planning and relevance, summary
   and keyword generation, topic-coverage storage, and Temporal scheduling. It
   must not copy their business rules or create replacement stores.
4. [ ] **Preserve the existing user trigger.** Research continues to start when
   the operator enters a question, chooses the total source count, and clicks
   **Discover Sources**. Do not introduce another start button or a separate
   agent interface.
5. [ ] **Simplify the active research API route.** `POST /v1/research/runs`
   authenticates and validates the request, finds or creates the research record
   for the question, starts the unified LangGraph workflow, and returns stored
   research status. The route no longer owns the detailed research sequence.
6. [ ] **Keep Temporal for durable work.** LangGraph defines the research
   sequence. Temporal automatically supplies recovery and retries when platform
   thresholds require durable execution. Preserve the active
   `CandidatePreflightWorkflow` and `EvidenceSummaryWorkflow`; neither the model
   nor the operator chooses whether Temporal is used.
7. [ ] **Fold in and retire the standalone agentic router.** Move its typed
   stages, bounded transitions, human-review wait, two-round gap-search limit,
   and incomplete-report behavior into LangGraph. Transfer its useful tests,
   then remove it as a separate workflow path. Keep the offline model evaluation
   as an independent test suite.
8. [ ] **Retire the unused earlier runtime workflow.** After confirming that
   stored runtime records remain readable, remove the old deterministic planner,
   first-result executor, reviewer cycle, unused scheduling boundary and
   activities, and `GovernedRuntimeWorkflow` registration. Do not remove the
   active candidate-preflight or evidence-summary Temporal workflows.
9. [ ] **Decide the Admin Durable Work view separately.** Preserve read-only
   visibility of historical runtime records during this refactor. Repurposing
   the view for unified research progress, or removing it, requires a separate
   operator-interface decision.
10. [ ] **Verify the complete workflow.** Integration tests must prove that the
    Discover Sources action starts the graph; topic and source limits hold;
    known URLs are skipped; direct and Temporal-backed work succeeds; blocked
    and review-required evidence stays outside automated model context; strict
    relevance decisions fail safely; gap searches stop after two rounds;
    retries do not duplicate records; reports use only eligible, relevant stored
    evidence; and existing research records remain readable.

Implementation proceeds in this order:

1. [x] Add the unified LangGraph state and graph structure.
2. [ ] Connect existing services through typed graph nodes. **In progress:** the
   production topic-planning service is connected and validated; search,
   acquisition, trust, relevance, summaries, coverage, and reporting remain.
3. [ ] Add end-to-end integration tests.
4. [ ] Change the active research API route to call the graph.
5. [ ] Verify existing research records and UI polling.
6. [ ] Remove the standalone plain-Python router.
7. [ ] Retire the unused old runtime and Temporal workflow.
8. [ ] Update the remaining documentation and mark this implementation complete.

### Local Policy-Controlled Web Trust

Add a browser-agnostic control point that determines whether a captured web
evidence version may enter the platform's evidence and AI workflows. This phase
governs local eligibility; it does not make a universal claim about a source's
truthfulness or replace browser safety protections.

- [x] Define the source-trust boundary, authority, and enforcement rules in an ADR.
- [x] Establish the initial, versioned local trust policy and expose it for
  read-only operator review. The current policy deterministically evaluates
  HTTPS, supported content types, extraction integrity, and extracted-size
  limits. It records redirects only as retrieval diagnostics: requested
  candidate URL, final evidence URL, and one bounded result (`no_redirect`,
  `redirected`, `redirect_limit_exceeded`, or `unsafe_destination_blocked`).
  Redirect metadata explains how evidence was reached but does not independently
  allow, flag, or block it.
- [x] Discover and automatically preflight every returned candidate before the
  operator selects it. Persist useful evidence, trust results, and failed or
  blocked candidate metadata so future agents can reuse the findings without
  treating a past URL result as a permanent verdict.
- [x] Automatically summarize eligible preflight evidence and accepted reviewed
  evidence through platform-selected direct or Temporal execution without
  exposing manual extraction or regeneration controls.
- [x] Evaluate an evidence version after acquisition and before it is eligible for
  summaries, keywords, or future evidence-grounded capabilities.
- [x] Enforce `eligible`, `eligible_with_notice`, `review_required`, and `blocked`
  dispositions. Preserve raw capture for audit regardless of disposition, but
  prevent evidence requiring review or blocked evidence from automated model
  context.

#### Open work

- [x] Add a review experience for evidence requiring review. A human acceptance
  records its identity, reason, exact evidence-version scope, and optional expiry
  independently of the UI and execution mechanism.
- [ ] Re-evaluate evidence after refresh or an applicable policy change. The
  platform uses direct execution for one ordinary evaluation and automatically
  uses its mandatory Temporal infrastructure when workload, retry, or review
  thresholds require durable execution.
- [ ] Validate C2PA provenance for supported file assets while recording ordinary
  HTML as a distinct case, not as invalid solely because it has no asset-level
  provenance manifest.
- [ ] Validate policy enforcement, policy changes, refresh, overrides, workspace
  isolation, prompt-injection resistance, and direct-versus-durable routing.

## Parking Lot

The following work remains planned but is intentionally deferred until concrete
product and deployment requirements justify it.

- **Topic-plan feedback** — add optional thumbs-up and thumbs-down feedback to
  the operator's topic-plan view. For negative feedback, record a simple reason
  such as a missing subject, irrelevant topic, overlapping topics, weak search
  query, or unsuitable topic count, with optional comments. Associate feedback
  with the research task, plan, model artifact, and prompt version so recurring
  failures can become new offline evaluation cases. Do not automatically train
  or change the model from an individual response.

- **Trust-policy management** — design a separately authorized workflow for
  changing local trust-policy rules, potentially through a purpose-built MCP
  capability. The current operator view remains read-only; no UI or agent may
  change enforcement rules directly.
- **Evidence freshness and re-capture** — design a governed way to refresh a
  stored source before enforcing a freshness limit. Today the platform reuses
  evidence already retained for a source and intentionally does not re-fetch it
  during discovery, so a freshness rule would otherwise make evidence stale
  without a way to renew it.
- **Agent-readiness profile** — record observed agent-facing capabilities for a
  source without treating them as a trust score or eligibility decision. Future
  observations may include semantic structure, JSON-LD, documented APIs,
  declared WebMCP tools, and read-only or consequential tool hints. The profile
  may use statuses such as `no_agent_interface_observed`,
  `structured_content_observed`, `machine_interface_declared`, and
  `agent_tools_observed` to inform future agent behavior only.
- **Evidence adequacy** — determine whether extraction produced meaningful
  source content rather than a navigation shell, paywall, login page, or shared
  template. This is needed before an automated workflow treats a technically
  successful capture as substantive research evidence.
- **Publisher access declaration** — record applicable `robots.txt` instructions
  for the platform's declared automated client identity. Use this to inform
  responsible retrieval behavior, never as authorization or a source trust
  score.
- **Agent-action boundary and safe inspection** — when a source declares
  WebMCP, OpenAPI, MCP, or another machine-action interface, record its
  existence while keeping it outside the research extractor. A future tightly
  controlled browser-inspection capability may observe declared WebMCP tools,
  but must never invoke them. The platform remains read-only with respect to
  website-provided tools.

- **GitHub Projects integration** — connect the platform's planning workflow
  to GitHub Projects so an operator can build a roadmap, create tasks, and
  update their priority quickly.
- **Source-candidate review usability** — make each source candidate URL a
  clickable external link that opens in a new browser tab, and request/display
  longer article descriptions so an operator has more context before choosing
  a source for extraction.
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
