# Summary-Recovery Requirements Checklist

**Purpose:** Review the requirements and design for recovering from malformed
local-model summary responses before implementation tasks are created.

**Created:** 2026-09-29  
**Feature:** [Reliable Summary Recovery](../spec.md)

## Requirement Completeness

- [x] CHK001 Are the required response shapes for chunk, consolidation, and final-source summaries fully defined, including the fields that are no longer permitted? [Completeness, Spec FR-007--FR-009]
- [x] CHK002 Is a "summary unit" defined consistently enough to identify exactly what receives one initial attempt and one corrective attempt? [Clarity, Spec Key Entities; Plan Design Decision 4]
- [x] CHK003 Are invalid JSON, missing required fields, unexpected fields, duplicate keywords, and an empty keyword list each assigned a clear validation outcome? [Coverage, Spec FR-001, FR-008, Edge Cases]
- [x] CHK004 Are model-response failures, source-summary failures, and whole-execution failures clearly distinguished so a reader can tell which level failed? [Completeness, Spec FR-011, FR-018; Plan State and Decision Ownership Matrix]
- [x] CHK005 Are the conditions for a final report clear when no source succeeds, when some sources succeed, and when all sources fail? [Completeness, Spec FR-013--FR-015; Plan Design Decision 6]
- [x] CHK006 Is the treatment of historical `keyword_coverage` data and the prohibition on writing it for new summaries unambiguous? [Completeness, Spec Assumptions; Plan Constitution Alignment]

## Recovery Boundaries

- [x] CHK007 Does "two total model attempts" clearly exclude provider or dependency failures that do not produce a usable model response? [Clarity, Spec FR-002; Plan Design Decision 4]
- [x] CHK008 Does the corrective-request requirement make clear that it uses the same trusted evidence and does not feed untrusted failed output back to the model? [Security, Spec FR-003--FR-004]
- [x] CHK009 Is the deterministic keyword-presence rule precise enough about case, whitespace, phrases, punctuation, and repeated keywords to prevent inconsistent implementation? [Clarity, Spec FR-001; Plan Design Decision 1]
- [x] CHK010 Are the validation categories detailed enough for operators to understand the failure without exposing raw model output or sensitive evidence? [Clarity, Spec FR-006, FR-019; Plan Design Decision 3]
- [x] CHK011 Is it explicit which validation problem is eligible for a corrective attempt and which problem immediately becomes a source or dependency failure? [Completeness, Spec FR-001--FR-005; Plan Design Decisions 2 and 4]

## State, Authority, And Data

- [x] CHK012 Is the research record still the single operator-facing status, with the unified workflow as its only writer, after a partial summary failure? [Consistency, Plan State and Decision Ownership Matrix]
- [x] CHK013 Is the evidence-summary execution status defined for partial success without implying that every source was summarized? [Consistency, Spec FR-012--FR-014; Plan Design Decision 5]
- [x] CHK014 Is the source-level terminal failure durable and clearly limited to an explicit future regeneration rather than automatic repeated retries? [Completeness, Spec FR-010--FR-012; Plan Design Decision 4]
- [x] CHK015 Does each attempt record contain enough identity and version information to explain the outcome without storing raw model output? [Completeness, Spec FR-005--FR-006; Data Model]
- [x] CHK016 Is the one authorized writer and the set of readers clear for attempt diagnostics, source outcomes, execution outcomes, research status, and the final report? [Ownership, Plan State and Decision Ownership Matrix]
- [x] CHK017 Are duplicate invocation, concurrent execution, stale workflow checkpoint, and retry-conflict outcomes specified well enough to avoid duplicate attempts or conflicting source results? [Coverage, Plan Conflict and Continuation Rules; Quickstart Scenario 6]

## Trust And Reporting Safety

- [x] CHK018 Do the requirements preserve the existing rule that blocked and review-required evidence never enters summary prompts or report prompts? [Security, Spec FR-016; Plan Reused Unchanged]
- [x] CHK019 Is the relationship between a source that passed trust checks, a source that failed summarization, and a source eligible for reporting clear and non-contradictory? [Consistency, Spec FR-011--FR-016]
- [x] CHK020 Does the report disclosure distinguish omitted sources caused by summary failure from sources that were never eligible for automated use? [Clarity, Spec FR-014--FR-015; Plan Design Decision 6]
- [x] CHK021 Is the report generation input explicitly limited to valid, stored summaries and keywords rather than raw evidence, failed responses, or workflow diagnostics? [Security, Spec FR-015--FR-016; Plan Design Decision 6]

## Operator Experience And Documentation

- [x] CHK022 Is the operator-facing source status clear enough to distinguish an exhausted summary failure from a trust-policy decision, extraction problem, or general system outage? [Clarity, Spec FR-019; Quickstart Scenarios 2 and 3]
- [x] CHK023 Is the proposed final-report display read-only and integrated into the existing research workspace without adding a second workflow trigger or agent interface? [Consistency, Plan UI and API Boundary]
- [x] CHK024 Are the report read endpoint's unavailable and partial-result responses defined so the UI can explain them without guessing from Temporal or worker logs? [Completeness, Contract `GET /v1/research/runs/{run_id}/report`]
- [x] CHK025 Do the required ADR and Local Evidence Intelligence documentation updates remove the retired coverage contract and explain the new recovery behavior accurately? [Documentation, Plan Implementation Sequence]

## Notes

- This is a requirements-review checklist for specification and plan quality. It
  is intentionally not an implementation test plan.
- Address each item in the feature artifacts before implementation tasks are
  treated as ready. Add new items here rather than weakening the original
  requirements when new ambiguities are found.
