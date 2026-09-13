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

## Phase 4 - Enterprise Services

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

## Phase 5 - Durable Execution

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

## Phase 6 - Local Evidence Intelligence

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

## Phase 7 - Grounded Research Chat

Build an authenticated, evidence-grounded chat experience on the same local
model-provider boundary.

- Answer only from the selected, workspace-owned research evidence with source
  citations and explicit uncertainty when evidence is insufficient.
- Keep chat sessions, permissions, retention, and model configuration
  platform-owned; the model receives no MCP tools, browser, filesystem,
  database, runtime, or credential access.
- Support optional future hosted providers behind the same adapter without
  making cloud credentials a requirement for local open-source deployments.

## Future Parking Lot

The following work remains planned but is intentionally deferred until the
local evidence-intelligence and grounded-chat capabilities are established.

- **Observability** — LangFuse, OpenTelemetry, metrics, and evaluation.
- **Durable data lifecycle** — configurable retention and archival operations
  for durable workflow metadata when real deployment requirements justify them;
  security audit history remains separately governed.
- **Production deployment** — Kubernetes, Azure deployment patterns, scaling,
  security hardening, and release automation.
