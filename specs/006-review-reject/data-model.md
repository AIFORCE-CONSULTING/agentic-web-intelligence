# Data Model: Human Evidence Review Rejection

## Evidence Trust Evaluation

**Canonical owner**: `EvidenceTrustService` writes through `WebTrustStore`.

**Purpose**: Records the deterministic local trust-policy result for one
captured evidence version.

| Field | Meaning |
| --- | --- |
| `id` | Stable trust evaluation identity. |
| `workspace_id` | Workspace that owns the research run. |
| `run_id` | Research run where the evidence was captured. |
| `source_url` | Final evidence URL evaluated by the policy. |
| `content_hash` | Exact captured evidence version. |
| `policy_version` | Versioned local trust policy used for the decision. |
| `disposition` | Base policy outcome: `eligible`, `eligible_with_notice`, `review_required`, or `blocked`. |
| `rule_outcomes` | Rule-level explanation retained for audit. |
| `component_version` | Web-trust service version that produced the evaluation. |
| `created_at` | Evaluation timestamp. |

**State rule**: Immutable after insert. Human review decisions do not rewrite
this record; they layer an explicit operator decision over it.

## Human Evidence Review Decision

**Canonical owner**: `EvidenceTrustService` writes through `WebTrustStore`.

**Purpose**: Records the authenticated human decision for one exact
review-required evidence version.

| Field | Meaning |
| --- | --- |
| `id` | Stable human review decision identity. |
| `evaluation_id` | Trust evaluation being reviewed. |
| `workspace_id` | Workspace where the decision applies. |
| `actor_user_id` | Human operator who made the decision. |
| `outcome` | `accepted` or `rejected`. Existing rows without this field are treated as `accepted`. |
| `reason` | Optional human note. Acceptance may continue using the existing required reason behavior; rejection does not require a reason in this first version. |
| `expires_at` | Optional expiry. Accepted decisions may expire; rejected decisions should normally be non-expiring unless a future feature deliberately adds expiry semantics. |
| `workflow_thread_id` | LangGraph thread resumed after the decision. |
| `workflow_status_version` | Research status version used when resume was requested. |
| `workflow_resume_requested_at` | Time the graph continuation was requested. |
| `created_at` | Decision timestamp. |

**Validation rules**:

- The reviewed base trust disposition must be `review_required`.
- Only authenticated human operators with research write authority may create a
  decision.
- A decision must target the exact `source_url` and `content_hash` reviewed.
- A rejection reason is optional in this first version. If supplied, it is stored
  with the decision.
- Only one active effective decision may exist for the exact active evidence
  version. A conflicting second decision returns a conflict instead of silently
  replacing the first.

**Effective eligibility rules**:

- `review_required` + active `accepted` decision -> effective disposition
  becomes `eligible`.
- `review_required` + active `rejected` decision -> evidence remains excluded
  from automated model context and generated artifacts.
- `blocked`, `eligible`, and `eligible_with_notice` base dispositions cannot
  be accepted or rejected through the human review action.

## Research Run Status

**Canonical owner**: Unified LangGraph wrapper writes through `ResearchStore`.

**Purpose**: Operator-facing workflow progress for one research task.

| Field | Meaning |
| --- | --- |
| `research_runs.status` | Current official stage or terminal outcome. |
| `status_version` | Optimistic concurrency guard for status transitions. |
| `failed_stage`, `failure_code`, `failure_explanation`, `retryable` | Failure details when status is `failed`. |

**Transition update**:

- Add `evaluating_relevance -> awaiting_review`.
- Keep existing review continuation transitions:
  `awaiting_review -> evaluating_relevance`,
  `awaiting_review -> assessing_coverage`, or
  `awaiting_review -> failed`.

**Conflict rule**: Stored `research_runs.status` wins over LangGraph checkpoint
state or Temporal history. A stale checkpoint must reload official status and
either continue through a legal transition or fail safely.

## Review API Read Model

**Canonical owner**: Derived response from `WebTrustStore.latest_evaluation`
and `list_latest_evaluations`.

**Purpose**: Shows the operator the base trust evaluation and any human review
decision for each captured evidence version.

**Required fields**:

- Existing trust evaluation fields.
- Active human decision identity, outcome, optional note, expiry, and timestamp
  when present.
- Effective disposition used by the platform.

**Rule**: The read model is not authoritative by itself. It repeats the
canonical trust evaluation and human decision records so the UI can explain
what happened.
