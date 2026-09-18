# ADR 0015: Govern captured web evidence with a local policy-controlled trust layer

- Status: Accepted
- Date: 2026-09-16

## Context

The platform can acquire web content, preserve extracted evidence, and generate
local derivative summaries and keywords. Browser vendors already protect a
person's browsing session through rendering sandboxing, phishing and malware
detection, download protection, and privacy controls. Those protections are
important but do not provide a platform-owned, browser-independent decision
about whether a specific captured evidence version may enter an AI workflow.

The platform needs a narrow control point that applies consistently when an
operator starts research, when stored evidence is refreshed, and when a future
server-owned capability requests evidence. The control point must preserve
provenance and local operator authority without pretending to establish factual
truth, global publisher reputation, or a replacement for browser security.

## Decision

The platform will add a local, policy-controlled trust layer between evidence
acquisition and automated evidence use. It evaluates the local eligibility of a
captured evidence version. It does not judge whether a source is true, safe for
all users, or trustworthy outside the configured local policy.

### Trigger and authority

Discovery is a platform-owned search-plus-candidate-preflight workflow. After
search returns candidate URLs, the server retrieves each candidate through the
same bounded public-web boundary used for extraction, records its retrieval
outcome, and evaluates every successfully captured evidence version before the
platform automatically creates summaries and keywords for candidates that are
eligible. This gives operators and future agents a visible shortlist of
reusable candidates without a second webpage retrieval or a manual extraction
or summary request.

The server evaluates a successful evidence capture immediately after
acquisition and before the evidence is eligible for summaries, keywords, or
future evidence-grounded capabilities. It re-evaluates an evidence version
after a refresh or when an applicable trust policy changes.

A server-owned trust-evaluation component owns state transitions and applies
the configured policy. PostgreSQL is the canonical record for evidence
versions, policy versions, evaluations, dispositions, and human overrides. A
model, retrieved content, MCP tool, browser extension, or external service
cannot set a disposition or override a policy.

### Policy inputs and evaluation record

The initial versioned local policy uses deterministic checks for approved or
blocked sources, HTTPS, redirects, response content type, response size,
extraction integrity, and freshness. The evaluator records source identity
metadata when observed and records provenance results when available.

Each evaluation is immutable and records the exact evidence version and
retrieval facts evaluated, policy and component versions, individual rule
outcomes, observed identity and provenance signals, final disposition, and
timestamps. Candidate records additionally retain search provenance, preflight
status, reason, timestamp, content type, content hash, and trust disposition
when available. Failed or blocked candidates remain queryable by later agents,
but a previous result is not a permanent domain-level verdict: future work must
recheck according to configured freshness policy. These records explain a
platform decision; they are not assertions that the underlying content is
factually correct.

### Dispositions and enforcement

The evaluator produces one of four dispositions:

- `eligible`: may be retrieved, displayed, summarized, and cited.
- `eligible_with_notice`: may be used with its configured limitation visible to
  the operator and attached to citations or derived output as appropriate.
- `review_required`: remains preserved and viewable, but is excluded from
  automated model context unless an authorized person accepts it.
- `blocked`: remains preserved for audit but cannot enter automated model
  context or derivative evidence generation.

An authorized human may accept or override an outcome only through a separate,
persisted authorization record. That record contains the actor, reason, scope,
and expiry when applicable. Eligibility enforcement consults this record
independently of UI state and independently of whether work ran directly or
durably. Acceptance of `review_required` evidence automatically initiates its
summary through the same server-owned route policy.

### Direct and durable execution

The platform runs a small candidate-preflight batch directly and automatically
uses the existing mandatory Temporal infrastructure for larger batches. The
operator and any agent caller cannot choose this route. Temporal makes
server-authorized work durable; it does not own policy authority, create human
approval, or open a new caller path.

### Rediscovery

The platform preserves completed research runs and their immutable evidence
history. When the operator requests the same completed question again, the UI
requires confirmation and the API verifies that confirmation against the latest
workspace-owned run. A confirmed rediscovery creates a new run and records the
prior run identifier in its audit trail. It never overwrites prior captures,
trust decisions, or summaries.

### Provenance and browser boundaries

For supported file assets, the platform may use C2PA validation as one observed
provenance signal. A valid C2PA manifest provides cryptographic provenance
information, not a declaration of truth. Ordinary HTML pages usually do not
carry an asset-level C2PA manifest and must be recorded as a distinct case,
rather than rejected for its absence.

The platform does not recreate browser phishing, malware, sandboxing, tracker
protection, or user-session security. Browser protections remain upstream
defenses for interactive browsing. The trust layer governs only the platform's
stored evidence-to-AI path and must operate without dependence on a browser.

### Excluded capabilities

This decision does not add autonomous web action, payments, external
publication, agent-to-agent protocol execution, publisher reputation scoring,
or a universal web truth score. It does not unpark Grounded Research Chat.

## Consequences

The platform gains a consistent, auditable local gate for evidence used by AI
workflows, with policy decisions that survive refreshes and do not depend on a
human browser tab. This adds persisted policy and evaluation data, enforcement
at every automated evidence-use boundary, and an explicit human-review path.

Future work may add narrowly scoped identity, reputation, and protocol adapters
without granting them authority to replace the local policy decision.
