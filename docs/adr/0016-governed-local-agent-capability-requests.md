# ADR 0016: Govern the local agentic research workflow

- Status: Accepted
- Date: 2026-09-22
- Model selection recorded: 2026-09-24
- Canonical orchestration clarified: 2026-09-24
- Consolidated implementation recorded: 2026-09-29

## Context

The platform can already search the web, acquire and evaluate evidence, create
source summaries and keywords, and reuse stored evidence. Those operations are
coordinated by platform code. The local model used by ADR 0014 receives evidence
only after the platform has approved it and has no research-planning or tool
role.

The next capability is a local research agent that can work toward an operator's
research question across several steps. It should be able to divide a broad
question into focused topics, request searches, judge whether eligible evidence
helps answer a topic, identify topics that still lack evidence, and prepare a
report from stored source summaries.

The model is useful for these meaning-based decisions, but it is not reliable or
authorized enough to own database state, security policy, execution, or external
effects. Retrieved webpages and search results may also contain instructions
intended to redirect the model away from the operator's goal.

NIST identifies indirect prompt injection through retrieved information as a
risk for systems that combine language models with external data. See the
[NIST AI RMF Generative AI Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf).
OWASP recommends limiting agent capabilities and enforcing authorization outside
the model. See [OWASP guidance on excessive agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/).

This ADR replaces the earlier cookie-preference-centered description of ADR
0016. The completed cookie-preference evaluation remains useful evidence about
one narrowly defined model request, but it does not demonstrate that the model
can complete the research workflow described here.

## Decision

The platform will use a local model as the reasoning component of a bounded
research workflow. The authenticated operator owns the research question. The
model may propose focused topics and approved research actions. Trusted platform
code validates each proposal, performs allowed work, stores the official state,
and decides how execution is scheduled.

### Canonical orchestration

The existing LangGraph runtime governed by ADR 0005 is the platform's one
application and agent orchestration path. This research workflow extends that
runtime; it does not create a second orchestration service or state machine.
`RuntimeService` continues to own run authority, capability grants, allowed
state transitions, retry boundaries, human gates, and runtime audit events.

The topic-planning, search, acquisition, trust, relevance, summary, coverage,
gap-search, and final-report stages are typed nodes in one LangGraph workflow. Deterministic
Python code inside those nodes validates model responses, enforces counters and
limits, and calls the existing research services. Python helpers may calculate
a next action, but they are not an independent workflow engine or source of
runtime state.

The earlier deterministic first-result executor, reviewer cycle, standalone
agentic control service, orchestration service, and governed-runtime Temporal
workflow have been retired. Their callers now enter the unified graph. The
clean-start migration removed obsolete test-era runtime and checkpoint state;
no compatibility path remains active.

LangGraph carries bounded execution context. PostgreSQL remains the official
record described below. Temporal remains the mandatory durable-execution system
when platform thresholds require recovery or retry. These three responsibilities
must not be combined into a competing store or workflow path.

### Trigger and ownership

An authenticated operator starts a research task with a question and a requested
source limit. The platform records that request before asking the model to plan
the research.

The research agent may decide which approved research action would help advance
the recorded question. It cannot change the question, increase limits, add a
capability, accept evidence requiring human review, alter trust policy, or mark
its own work complete without satisfying the platform's completion checks.

### Canonical state

PostgreSQL is the official record for:

- the operator's research question and limits;
- planned topics and their search queries;
- model, prompt, contract, and policy versions;
- discovered sources and reused evidence;
- retrieval, trust, and human-review outcomes;
- topic-specific relevance decisions;
- source summaries and keywords;
- topic-coverage status and gap-search attempts;
- model requests, platform validation results, and tool outcomes; and
- the final report and terminal task status.

A model response is a proposal or derived artifact. It becomes workflow state
only after platform code validates it against the current task and its contract.

### Research workflow

#### 1. Plan focused topics

The model receives the operator's question and proposes no more than three
focused topics. Each proposed topic contains:

- a unique, stable `topic_id` used for tracking;
- a plain-language `topic` describing the information to find; and
- one `search_query` intended to find evidence for that topic.

Platform code validates the JSON shape, topic limit, field lengths, unique topic
identifiers, and non-empty values. A malformed plan is recorded as a model
failure and does not start searches.

The topic plan defines what the workflow will try to cover. Evaluation fixtures
must test whether the model's proposed topics collectively address the original
question, because deterministic validation can verify the structure but cannot
prove that the plan is complete.

#### 2. Search and acquire evidence

For each accepted topic, the agent may request the bounded web-search capability
assigned to the task. The platform applies the operator's source limit, reuses
known sources and evidence where applicable, and records newly discovered
candidates.

The platform retrieves candidates through the existing acquisition and preflight
path. Cheap checks over a bounded opening excerpt may record signals such as a
suspected public cookie-preference page, advertising shell, login page, or
otherwise inadequate content. These signals explain why content may be unusable
or require another approved capability. A text match by itself does not establish
trust, relevance, or permission to use the evidence.

The existing local trust policy evaluates each acquired evidence version before
it can enter model context. Blocked evidence remains excluded. Evidence marked
`review_required` remains excluded until a human acceptance for that exact
evidence version is recorded through the existing review workflow.

#### 3. Decide topic relevance

The relevance model receives the original research question, the plain-language
topic, and a bounded excerpt from one eligible evidence version. It does not
receive only the `topic_id`, because that identifier may not contain enough
meaning to judge relevance.

The model must return exactly `YES` or `NO`. Platform code accepts only those two
values. Any explanation, punctuation, empty response, or other value is recorded
as a model failure and does not approve the evidence for that topic.

Relevance is recorded for the combination of research task, topic, and evidence
version. A source that is irrelevant to one topic may still support another
topic or another research task.

#### 4. Summarize and track coverage

Eligible and relevant evidence is processed by the existing summary and keyword
workflow governed by ADR 0014. The research agent does not write documents,
summaries, keywords, or coverage records directly.

The unified graph starts the summary stage only after relevance is recorded.
Candidate preflight records retrieval and trust outcomes, then returns control
to that graph; it never starts a summary itself. The summary service may divide
more than five relevant sources into internal jobs, but it records one summary
work set for the research task and waits for every job to finish. A partial
success continues to coverage and reporting from the usable summaries; the
research task fails only when the completed work set has no usable summary or
its saved state conflicts.

Evidence counts toward a topic only when the platform has:

1. acquired usable evidence;
2. allowed that evidence through the trust workflow;
3. recorded an accepted relevance decision for that topic; and
4. stored a completed summary and keywords for that evidence version.

Topic coverage is stored separately from free-form keywords. Keywords describe
the contents of a source; they are not used as the official proof that a planned
topic has research coverage.

#### 5. Search for missing evidence

Platform code determines which planned topics have no qualifying evidence. When
a gap exists, the model may propose exactly one targeted search query for a
missing topic. The platform validates the query, associates it with that topic,
and performs the same search, acquisition, trust, relevance, and summary steps.

The platform permits no more than two additional gap-search rounds for the whole
research task. The loop counter, duplicate-query check, source limits, and stop
condition are deterministic platform state. The model cannot reset or increase
them.

#### 6. Prepare the research report

The platform loads bounded stored source summaries, their source references, the
planned topics, and the recorded topic-coverage status. For each planned topic,
the platform sends the model one bounded group of summaries at a time. The
model drafts finding text with supplied citation labels only. Platform code
merges validated findings, renders one Markdown research report, cites stored
summary links, and identifies any topic or bounded group that still lacks
sufficient evidence or safe model output.

Raw webpages, credentials, internal policy, and unrestricted database content
are not included in these report prompts. Platform code validates each bounded
group response, source references, final report structure, and report quality
before storing the report package.

### Capability and execution boundary

The agent receives descriptions and schemas only for the capabilities assigned
to the current research task. Initially, those capabilities are bounded search
and evidence acquisition through the existing governed runtime and MCP host.
The model may request a capability but cannot invoke it directly.

For every request, platform code verifies the task, workspace, capability grant,
arguments, source scope, policy outcome, deadline, source and retry budgets, and
current workflow state. Only an accepted request reaches the existing MCP host
or internal platform service.

The model has no direct browser session, MCP connection, database connection,
filesystem, shell, credentials, service identity, Temporal client, or arbitrary
network access. It cannot invoke website-provided WebMCP, OpenAPI, MCP, or other
action interfaces.

The platform executes short, bounded work directly and automatically uses its
mandatory Temporal infrastructure when workload, retry, or recovery thresholds
require durable execution. The model and operator do not select the execution
path.

### Human decisions

Human evidence review remains separate from agent reasoning and execution. An
authorized operator may accept or reject one `review_required` evidence version
through the existing review workflow. The platform records the operator
identity, decision outcome, evidence-version scope, optional rejection note,
acceptance reason, and optional acceptance expiry, and enforces that decision
whenever the evidence is considered for model context.

The agent cannot request or manufacture a human review decision. Login, paywall,
credential, purchase, upload, download, external-write, and ambiguous browser
interactions remain outside the initial research capability set.

A future public cookie-preference capability may be added through a separate
approved design. Its earlier offline evaluation is not an implementation or a
live capability grant.

### Evaluation gate

No local model may request live research capabilities until it passes a
versioned offline evaluation of this complete workflow. The evaluation uses mock
capabilities and fixed research cases. It must cover:

- topic plans that do and do not cover the operator's question;
- valid and malformed planning responses;
- relevant, irrelevant, duplicate, blocked, and review-required sources;
- malformed relevance responses;
- hostile instructions embedded in webpage excerpts;
- missing-topic searches and the two-round limit;
- source and query reuse;
- final reports with complete, incomplete, and unsupported coverage; and
- compliance with task, source, retry, and capability limits.

Each case runs repeatedly with fixed model settings. The report records the
model artifact, prompt version, contract version, fixture version, expected
result, actual result, validation outcome, and resource use.

The completed cookie-preference evaluation remains a preliminary result for one
future capability. It cannot be used as the model-selection decision for this
workflow. Enabling live research capabilities requires a separate, recorded
decision based on the complete evaluation.

### Recorded model selection

The platform selects `qwen3:1.7b` as the initial reasoning model for this
bounded research workflow. This is a fit-for-purpose decision for the workflow
defined by this ADR, not a claim that the model is suitable for unrestricted
agent work or is the strongest available model.

The decision is based on
`agentic-research-workflow-evaluation-v4`, using
`agentic-research-workflow-fixtures-v3`, fixed model settings, and the installed
model artifact with digest
`8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7`.
All 20 cases passed in each of five attempts. Across three different planning
questions, 14 of 15 topic plans passed on the first response. One response
omitted the website perspective from the operator's question. The platform
identified `website` as the missing concept, permitted one correction, and the
replacement plan passed.

The first-response omission is a known limitation. The selected operating
boundary therefore includes the versioned prompt, native JSON schema, platform
validation, at most one targeted correction, and fail-closed handling when the
corrected response still fails. Both responses and the concepts identified as
missing must remain visible in evaluation and runtime records. The model cannot
approve its own response or continue after the platform rejects it.

Local operation is an explicit product requirement. Selecting a small local
model keeps the workflow available to people who cannot justify paid research
subscriptions, recurring cloud inference charges, or high-end local hardware.
The platform accepts the bounded correction cost rather than making a larger
model or cloud account a requirement.

This decision and the completed integration evaluation clear the model for the
bounded research workflow described here. Capability descriptions do not grant
authority: every live request still requires a stored RuntimeService allow
decision before the governed MCP host may execute it. Re-run the complete evaluation before
adopting a different model artifact, changing a model-owned prompt or contract,
expanding the workflow's capabilities, or retaining a model after a meaningful
pattern of production failures.

### Consolidated implementation amendment

The production implementation has one operator trigger and one application
workflow. `POST /v1/research/runs` authenticates and validates the request,
finds or creates its research record, and starts or resumes the unified
LangGraph. The route does not perform the research sequence itself.

`research_runs.status` is the operator-facing workflow status. The unified
graph is its only writer through `ResearchStore`; the UI and RuntimeService read
that stored value. RuntimeService owns authorization decisions and their audit
records through `RuntimeStore`, but it does not own research progress.
`AgenticResearchStore` owns topics, relevance, coverage, and reports.
`WebTrustStore` owns evidence-policy evaluations and human acceptances.
`EvidenceSummaryStore` owns summary work and artifacts.

The unified graph's final-report node remains the sole report caller. It
creates an append-only report package from qualified stored summaries grouped
under the planned topics already stored for the research run. Platform code
renders the final sections, source lists, citation links, and quality grade;
the model may draft bounded findings for one supplied topic group at a time.
Large topics are split by summary count and prompt size before any report
prompt is sent to the local model. A report quality grade of `FAIL` identifies
an incomplete, partially degraded, or fallback report, not an authority, trust,
relevance, or workflow failure. The graph transitions the research record to
`completed` after that package is stored; it transitions to `failed` during
reporting only if the package cannot be created or persisted.

LangGraph's PostgreSQL checkpoint is an execution bookmark, not a business
record. Temporal history is durable execution tracking, not workflow status.
When deterministic thresholds select durable preflight or summary work, the
corresponding Temporal workflow persists its result through the owning service.
Preflight resumes the graph after its retrieval and trust result. Each durable
summary job instead updates its stored summary work set; only the terminal
aggregate result resumes the same graph thread, exactly once. The model,
operator, and API route cannot select Temporal directly.

RuntimeService evaluates a request from stored assignment, role, capability,
resource, workflow-stage, workspace, and budget facts. Both allows and denials
are recorded with an authority-policy version. An allowed request is correlated
with the subsequent governed MCP invocation; the MCP host rejects an invocation
that lacks that stored authorization. Evidence trust and human review remain
independent decisions and cannot be manufactured by the graph or model.

## Consequences

The platform gains an agent that can make useful research decisions across
several steps while existing services continue to protect evidence, state, and
external actions. Topic records make coverage visible and let deterministic
code identify missing evidence without guessing from keywords.

The design adds model calls for planning, relevance, gap-query generation, and
final reporting. Small local models may fail these contracts or produce weak
research plans even at temperature zero. The offline evaluation and recorded
model-selection decision are therefore required before live rollout.
