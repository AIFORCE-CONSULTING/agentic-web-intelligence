# Agentic Web Intelligence

Agentic Web Intelligence is a local-first research platform for finding web
sources, deciding whether they are safe and useful to use, preserving the
supporting evidence, and producing grounded summaries and reports. It is built
for people who need credible research without making cloud-model access or
expensive research subscriptions a requirement.

The [roadmap](foundation/roadmap.md) is the authoritative delivery record. It
lists every phase, what is complete, active refactoring, and intentionally
deferred work. This Home page describes the platform as it exists and the
direction it is taking, rather than repeating a partial phase history.

## What The Platform Does

- An operator enters a research question, chooses how many sources to seek, and
  starts one research task.
- LangGraph coordinates the research flow: topic planning, discovery,
  retrieval, trust evaluation, relevance, summaries, topic coverage, gap
  searches, and an evidence-grounded final report.
- The governed MCP host is the platform's only web-tool boundary. It exposes
  approved, typed capabilities such as web search and evidence extraction while
  preventing agents from calling external providers, browsers, or arbitrary
  network tools directly.
- The platform stores original evidence, generated summaries, keywords, trust
  decisions, and safe operational outcomes in PostgreSQL.
- Local Ollama models perform bounded semantic work such as topic planning,
  relevance decisions, summarization, keywords, and report writing. They do
  not receive browser, database, shell, credential, or execution authority.
- Temporal is mandatory platform infrastructure for work that needs durable
  execution. The platform selects it automatically; an operator never chooses
  a separate durable-execution mode.

## How It Stays Governed

The local web-trust layer evaluates retrieved evidence before it can enter
automated model context. It records the requested and final URLs, redirect
result, retrieval facts, content and extraction outcomes, and the resulting
eligibility decision. `blocked` evidence never enters a model prompt.
`review_required` evidence remains visible to an operator and needs a recorded
human acceptance for that exact evidence version before it can be used. A
human rejection records that the exact evidence version must remain excluded
while the workflow continues with other usable evidence.

RuntimeService remains the platform's authority layer. It evaluates who or
what may request a capability. LangGraph coordinates the work; PostgreSQL holds
the operator-facing research status; and Temporal provides durable execution
tracking. These roles deliberately remain separate.

## Where It Is Going

The platform is being consolidated around one coherent, agentic research
workflow. The model can help plan and reason within tightly defined contracts,
while deterministic platform code retains authority over limits, source reuse,
trust rules, database writes, retries, and audit records. Future capabilities
such as agent-readiness profiles, publisher access declarations, and carefully
bounded consent handling are tracked in the [Parking Lot](foundation/roadmap.md#parking-lot),
not treated as current behavior.

## Start Here

- Follow the [Quickstart](quickstart.md) to start a private local platform.
- Review the [roadmap](foundation/roadmap.md) for current phases, completed
  work, refactoring, and deferred ideas.
- Read the [current platform architecture](current-platform-architecture.md)
  and the [architecture glossary](architecture-glossary.md) for the components
  and their responsibilities.
- Read [Local Evidence Intelligence](local-evidence-intelligence.md) for the
  operator workflow, trust boundary, local summaries, and reports.
- Read [Governed Web Research](governed-web-research.md) for the MCP host, its
  approved tool catalog, and the execution safeguards around every tool call.
- Review [ADR 0014](adr/0014-governed-local-model-provider.md) and
  [ADR 0016](adr/0016-governed-local-agent-capability-requests.md) for the
  model and agentic-research decisions.
- Use the [contribution guide](contributing.md) to run the platform locally.
- Read [Governance](governance.md) and [Support](support.md) before opening a
  public contribution or support request.
