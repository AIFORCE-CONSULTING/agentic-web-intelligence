# Data Model: Reliable Summary Recovery

## Existing Canonical Records Extended

### Evidence summary execution

`evidence_summary_executions` remains the official record for one operator-authorized summary operation. An execution may be `completed` only when at least one eligible, relevant source has a valid final summary marked `evidence_sufficient: true`; other sources may have failed recovery or completed with insufficient evidence. It is `failed` when no eligible, relevant source has an evidence-sufficient final summary, or an execution-level dependency fails before usable work can be produced.

### Evidence summary execution source

`evidence_summary_execution_sources` remains the official per-source outcome. It adds:

| Field | Meaning | Rule |
| --- | --- | --- |
| `summary_attempt_count` | Completed model responses evaluated for the source's current summary work | Derived from recorded attempts; never exceeds two per summary unit. |
| `failure_category` | Safe category explaining a source or execution failure | One of the shared category vocabulary below. Empty for a completed source, including an insufficient final summary. |
| `failure_reason` | Plain-language operator explanation | The fixed message for its category; never includes raw model output, hidden prompts, credentials, or evidence beyond source identity. |

The existing nullable `keyword_coverage` fields remain readable for historical v1 artifacts. New v2 summaries do not write coverage data.

### Shared failure categories and operator messages

| Category | Owning existing service | Operator-facing explanation |
| --- | --- | --- |
| `summary_contract_exhausted` | Evidence-summary service | The local model could not create a valid summary after two attempts. |
| `model_dependency_unavailable` | Evidence-summary service | The local model service was unavailable before a summary could be completed. |
| `evidence_trust_blocked` | Web-trust service | This evidence is blocked by the local trust policy. |
| `evidence_review_required` | Web-trust and evidence-review services | This evidence requires human review before it can be summarized. |
| `evidence_extraction_unavailable` | Web-research acquisition service | The webpage could not be retrieved as usable evidence. |
| `workflow_infrastructure_failed` | Durable-execution boundary | The research workflow could not continue because a required platform service was unavailable. |
| `state_conflict` | Owning store | The research workflow stopped safely because its saved state conflicted. |

The named owner writes its category through the existing record it already
owns. The summary-recovery feature maps only its own two categories; it does
not take ownership of trust, extraction, or workflow-infrastructure decisions.

### Summary attempt

`evidence_summary_attempts` is a new append-only diagnostic record. It answers: "What happened when the platform evaluated this model response for this exact piece of source-summary work?"

| Field | Meaning |
| --- | --- |
| `id` | Stable attempt identity |
| `execution_id` | Parent summary execution |
| `source_url`, `content_hash` | Exact source version being summarized |
| `unit_kind` | `chunk`, `consolidation`, or `source_final` |
| `unit_key` | Deterministic unit identity, such as a chunk index or reduction group |
| `regeneration_attempt` | The operator-authorized summary cycle within this execution; ordinary worker retries do not change it |
| `attempt_number` | `1` or `2` for that exact unit |
| `state` | `reserved`, `accepted`, `rejected`, or `dependency_failed` |
| `outcome` | `accepted` or `rejected` for a completed model response; empty while reserved or dependency-failed |
| `validation_category` | Safe typed category for a rejected output; empty for accepted output |
| `validation_explanation` | Safe diagnostic explanation, not raw output |
| `model_name`, `prompt_version` | Model and prompt/contract identities used for the attempt |
| `reserved_at`, `request_deadline_at` | When the platform claimed the model-call slot and when it becomes stale |
| `completed_at` | When validation completed, if a completed response was received |

The uniqueness rule is `(execution_id, regeneration_attempt, source_url, content_hash,
unit_kind, unit_key, attempt_number)`. It prevents duplicate delivery or a
restarted worker from claiming a third model-call slot for the same unit. An
explicit operator-authorized regeneration increments `regeneration_attempt` and
begins a distinct two-attempt cycle; direct retries, Temporal retries, and
restarts do not.

### Research report

`agentic_research_reports` remains the canonical stored report. When source summaries were omitted, trusted platform code includes a deterministic omission notice in the stored markdown. No failed source or completed source with `evidence_sufficient: false` becomes a qualified report source.

## Relationships

```text
research_runs
  └─ evidence_summary_executions
       ├─ evidence_summary_execution_sources
       │    └─ evidence_summary_attempts
       ├─ evidence_summary_execution_chunks
       ├─ evidence_summary_execution_groups
       └─ evidence_summary_artifacts (accepted final summaries only)

agentic_research_reports
  └─ uses qualified evidence_summary_artifacts only
```

## Lifecycle Rules

| Item | Allowed outcome |
| --- | --- |
| Summary unit | No attempt -> `reserved` attempt 1 -> `accepted` or `rejected`; only a rejected first response may reserve attempt 2 -> `accepted` or `rejected`. A reservation that reaches its request deadline becomes `dependency_failed`; it is never silently reclaimed. |
| Source | `extracted` -> `summarizing` -> `completed` after an accepted final unit. A completed source with `evidence_sufficient: false` remains stored and operator-visible but does not qualify for coverage or reporting. `summarizing` -> `failed` after a rejected final permitted response or a dependency failure; the failure category distinguishes those outcomes. A failed source returns to work only through existing operator-authorized regeneration. `retrying` is an operator-facing view derived from a rejected first attempt, not a second stored source status. |
| Execution | `awaiting_execution` -> `summarizing` -> `completed` when at least one source completes with `evidence_sufficient: true`, or `failed` when none does or a dependency fails. Only the summary service requests the store transition; Temporal and LangGraph read the stored result. |
| Research task | The existing unified LangGraph state remains authoritative. A completed partial summary execution advances the task; a failed execution follows the existing durable-failure path. |

## Transaction And Conflict Rules

1. Before each model request, the summary store locks the exact
   execution-source row and atomically creates the next permitted reservation.
   The reservation deadline is the configured model request timeout plus 30
   seconds.
2. A duplicate delivery finds the existing reservation or completed attempt and
   returns it without calling the model. A second worker therefore cannot claim
   the same attempt number.
3. A response can change only its own `reserved` row to `accepted` or
   `rejected`. Accepting a final source response creates the accepted artifact
   and marks the source completed in the same transaction. No later response
   may overwrite that accepted artifact for the same source version and cycle.
4. A rejected first response is the only state that permits a second
   reservation. A rejected second response marks that source failed with a
   summary-contract category. No attempt three exists.
5. A stale reservation or provider failure is a dependency failure, not a
   malformed model response. The store marks the affected source failed with
   `model_dependency_unavailable`, fails the execution under the existing
   dependency path, and does not automatically start another model call.
6. An accepted final response with `evidence_sufficient: false` completes its
   source and may remain visible and reusable, but it creates no qualifying
   topic-coverage association and is not report input. It is not a source
   failure and consumes no corrective response.
7. If stored attempt history conflicts with a completed artifact or source
   state, the store preserves the accepted artifact, rejects the new write, and
   reports a safe conflict outcome. The unified research record's existing
   `status_version` remains the rule for stale LangGraph continuation.

## Retention and Privacy

Attempt records retain safe diagnostic metadata only. Historical coverage maps remain attached to existing artifacts for backward readability, but new work does not create or depend on them. No raw malformed response is retained.
