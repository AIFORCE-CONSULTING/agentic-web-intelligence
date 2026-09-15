# ADR 0014: Keep local-model inference behind a governed provider boundary

- Status: Accepted
- Date: 2026-09-11

## Context

The platform's first live language-model capability will generate a summary and
page-level keywords from web content that has already passed through the
governed research boundary. The platform must remain practical for local,
open-source deployment on modest hardware while preserving the authority,
workspace, provenance, and execution boundaries established in Phases 3–5.

An inference model can produce useful derivative content, but it cannot be
trusted with authority. In particular, a model response, retrieved web page,
or prompt-injection attempt must not be able to select tools, access secrets,
start runtime work, alter durable state, or broaden the evidence available to
the request.

## Decision

The platform will use a server-owned, provider-neutral inference adapter. The
initial local provider is a native Ollama service operated outside Docker. The
initial recommended model is Qwen3 1.7B, subject to explicit operator
installation and local validation. The adapter may support future hosted
providers without changing the authority or evidence contracts below.

The reusable chunking, output-schema, consolidation, coverage, and deterministic
routing logic lives in an internal `evidence_intelligence` package. It exposes
plain typed input and output only, and must not import platform API, identity,
database, provider, MCP, Temporal, filesystem, or credential code. Platform
adapters own every side effect around that package. This is intentionally shaped
so it can be extracted and independently versioned later without untangling
authority-bearing platform code.

### Operator configuration and availability

The platform does not install Ollama, download a model, start a model service,
or enable a provider automatically. An operator deliberately configures a
supported provider endpoint and model artifact. The platform validates the
configured provider, reports its non-secret readiness and model identity, and
fails closed when the provider is unavailable or incompatible.

Provider configuration and any optional future credentials are platform-owned
deployment configuration. They are validated and redacted under the existing
secret-handling policy. They are never returned through APIs, durable records,
audit events, model prompts, or model output.

### Authority and evidence boundary

An authenticated operator may request generated content only for selected,
workspace-owned evidence that the governed research path already extracted and
persisted. The API/runtime service verifies the operator, workspace access,
evidence ownership, and request limits before it constructs a model request.

PostgreSQL is the canonical record for the request, its selected evidence
references, status, provenance metadata, and any resulting derivative content.
The original extracted evidence remains the source of truth. Generated content
is explicitly marked as derivative and keeps references to its source URLs,
content hashes, and processed chunks.

The inference provider receives only bounded text and fixed, server-owned
instructions needed to return the requested structured result. It receives no
MCP client, web-search or extraction capability, browser session, filesystem,
database connection, shell, credential, service identity, runtime client, or
Temporal client. A model response is untrusted data and cannot create a run,
change a goal, assign a role, select a tool, grant a capability, alter policy,
or initiate a handoff.

### Complete-page processing and output validation

The platform preserves whole-page coverage without sending an entire page in a
single inference request. Trusted server code divides selected extracted content
into bounded, overlapping chunks; processes those chunks with a fixed schema;
then performs a bounded consolidation step. The final result records coverage
and source-chunk references so an operator can distinguish derived claims from
the supporting evidence.

The provider adapter requests a strict structured response for a summary and
keywords. The platform validates size, schema, provenance references, and
workspace ownership before it persists or returns an output. Invalid,
incomplete, provider-authored instructions, or unavailable-model responses are
treated as typed failures, never as authority-bearing commands.

### Direct and durable execution

A short summary for one page executes directly inside the API request path. A
trusted routing rule may use the existing server-only durable-execution path
for multi-page, long-running, or restart-sensitive chunk processing. Temporal
only makes an already-authorized server job durable; it does not provide human
approval, model authority, scheduling authority, or a new caller path.

The operator's request is recorded independently of the execution mechanism.
The provider cannot choose whether work is direct or durable, schedule itself,
or resume a cancelled or terminal request.

## Implementation status

The platform now records per-source content length, chunk count, and chunking
policy version alongside bounded chunk summaries and their character-offset
coverage. When chunk summaries exceed the fixed consolidation input budget,
the platform persists bounded intermediate reduction groups and repeats that
reduction until the final source-level consolidation fits the same budget.
Final summaries
must state whether the available evidence is sufficient; otherwise the operator
sees the limitation instead of a fabricated complete answer. The provider sees
only one chunk at a time during extraction and only the derived chunk summaries
during consolidation.

## Consequences

Phase 6 can add useful local inference without treating the model as an agent
or expanding the capabilities of existing agents. The platform gains a stable
adapter boundary for local and future hosted providers, at the cost of explicit
configuration, health checks, strict schema validation, provenance storage,
and resource-aware processing.

Future work must not add automatic model installation, automatic model download,
generic model tools, unauthenticated inference endpoints, or a model-controlled
runtime path.
