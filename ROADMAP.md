# Roadmap

## Phase 1 - Foundation

- Repository scaffold and contribution standards
- React + FastAPI application boundaries
- Docker Compose local environment
- MkDocs Material documentation site
- Architecture Decision Records
- CI validation and repository templates

## Phase 2 - Governed Web Intelligence

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

## Post-Phase-4 Parking Lot

These items are intentionally captured for the next planning pass. They do not
expand the active Phase 4 scope or replace the existing Durable Execution
roadmap phase.

1. **GitHub Projects integration** — connect the platform's planning workflow
   to GitHub Projects so an operator can build a roadmap, create tasks, and
   update their priority quickly.
2. **Source-candidate review usability** — make each source candidate URL a
   clickable external link that opens in a new browser tab, and request/display
   longer article descriptions so an operator has more context before choosing
   a source for extraction.

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
- Run short single-page summaries directly; use Temporal only for multi-page or
  restart-sensitive chunk processing.
- Add an operator UI to request, inspect, and distinguish generated summaries
  from extracted source evidence.
- Validate local quality, model-unavailable behavior, prompt-injection
  resistance, workspace isolation, and direct-versus-durable routing.

## Phase 7 - Local Policy-Controlled Web Trust

Add a browser-agnostic control point that determines whether a captured web
evidence version may enter the platform's evidence and AI workflows. This phase
governs local eligibility; it does not make a universal claim about a source's
truthfulness or replace browser safety protections.

- Define the source-trust boundary, authority, and enforcement rules in an ADR.
- Add a versioned, local trust policy with deterministic rules for approved
  sources, HTTPS, redirects, content types, extraction integrity, freshness,
  and size limits.
- Discover and automatically preflight every returned candidate before the
  operator selects it. Persist useful evidence, trust results, and failed or
  blocked candidate metadata so future agents can reuse the findings without
  treating a past URL result as a permanent verdict.
- Automatically summarize eligible preflight evidence and accepted reviewed
  evidence through platform-selected direct or Temporal execution without
  exposing manual extraction or regeneration controls.
- Evaluate an evidence version after acquisition and before it is eligible for
  summaries, keywords, or future evidence-grounded capabilities.
- Persist an immutable evaluation record with retrieval facts, policy version,
  rule outcomes, observed provenance and identity signals, disposition,
  timestamps, and component versions.
- Enforce `eligible`, `eligible_with_notice`, `review_required`, and `blocked`
  dispositions. Preserve raw capture for audit regardless of disposition, but
  prevent evidence requiring review or blocked evidence from automated model
  context.

### Current Phase 7 priorities

1. Keep one canonical research run for each normalized web-search target. A
   repeated **Discover sources** action performs a fresh provider search but
   never creates a duplicate target container.
2. On repeated discovery, append and acquire/preflight only source URLs that
   are not already present anywhere in the workspace database. Preserve prior
   evidence, trust evaluations, and summaries without re-fetching or
   re-summarizing them.
3. Add a workspace-wide keyword-centered operator view: render each keyword
   as a visual card and list every related stored source summary beneath it.
   A source may appear under more than one keyword, and each source link opens
   its stored source summary rather than the original external webpage.
4. Raise the governed discovery result limit from 5 to 50 sources so the
   platform can acquire and evaluate a broader initial evidence set.
5. After eligible sources are summarized, group sources that share keywords
   and generate a cross-source synthesis describing what their summaries have
   in common and where they differ.
6. Revisit both the chunk and final summarization prompts and their output
   contracts so every generated keyword is substantively represented in that
   source's summary.

### Remaining Phase 7 trust-layer work

- Add a review experience for evidence requiring review. A human acceptance or
  override records its identity, reason, scope, and expiry independently of the
  UI and execution mechanism.
- Re-evaluate evidence after refresh or an applicable policy change. The
  platform uses direct execution for one ordinary evaluation and automatically
  uses its mandatory Temporal infrastructure when workload, retry, or review
  thresholds require durable execution.
- Validate C2PA provenance for supported file assets while recording ordinary
  HTML as a distinct case, not as invalid solely because it has no asset-level
  provenance manifest.
- Validate policy enforcement, policy changes, refresh, overrides, workspace
  isolation, prompt-injection resistance, and direct-versus-durable routing.

## Future Parking Lot

The following work remains planned but is intentionally deferred until concrete
product and deployment requirements justify it.

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
