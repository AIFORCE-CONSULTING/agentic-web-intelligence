# Data Model: Topic-Scoped Report Sections

## Existing authoritative records

| Record | Purpose | Owner |
| --- | --- | --- |
| `research_runs` | Official research workflow progress and failure state | `ResearchStore` through unified LangGraph wrapper |
| `agentic_research_topics` | Planned topic identity, plain-language topic, search query, and display order | `AgenticResearchStore` |
| `agentic_topic_coverage_evidence` | Qualified source-to-topic evidence associations | Existing coverage workflow |
| `evidence_summary_artifacts` | Evidence-sufficient summaries and keywords | Evidence-summary store |
| `web_evidence_trust_evaluations` and overrides | Eligibility and human acceptance facts | Web-trust and review stores |
| `agentic_research_reports` | Append-only operator-facing report package | `AgenticResearchStore` |
| `agentic_research_report_inputs` | Frozen source-summary input snapshot for a stored report | `AgenticResearchStore` |
| `agentic_research_report_attempts` | Diagnostic model-attempt records | `AgenticResearchStore` |
| `agentic_research_report_contributions` | Mapping from accepted findings or section source lists to report inputs | `AgenticResearchStore` |

## Planned Topic

Represents one report section the platform must render.

| Field | Meaning |
| --- | --- |
| `topic_record_id` | Stable stored topic record identity |
| `topic_id` | Stored topic identifier from topic planning |
| `topic` | Operator-readable section heading text |
| `position` | Planned order for report rendering |

Validation rules:

- A report renders exactly the planned topics loaded for the run.
- The model cannot create, rename, reorder, or omit topic sections.
- A topic with no qualified inputs is rendered with insufficient-evidence wording.

## Topic Report Input

Represents one qualified source summary available to one planned topic during
report generation.

| Field | Meaning |
| --- | --- |
| `source_ref` | Report-local citation label, formatted as `S01`, `S02`, etc. |
| `topic_record_id`, `topic_id`, `topic` | Topic scope for this input |
| `summary_artifact_id` | Stored source-summary artifact used by the report |
| `source_url`, `source_title` | Trusted source identity shown to the operator |
| `summary_text`, `summary_digest` | Exact summary supplied to model and digest snapshot |
| `content_hash`, `position` | Evidence identity and stable report-input order |

Validation rules:

- Labels are unique within one report package.
- Labels are stored in the frozen report package and may differ across report packages.
- The model receives only labels and summaries for the current topic.
- Trusted platform code renders labels as links to stored source summaries.

## Topic Finding Draft

Represents one model-proposed finding for a single supplied topic.

| Field | Meaning |
| --- | --- |
| `text` | Finding narrative for the current topic |
| `source_refs` | Labels selected from the current topic's supplied source list |

Validation rules:

- Finding text must be non-empty.
- Each `source_ref` must resolve to exactly one supplied input for the current topic.
- Harmless label formatting may be normalized only when unambiguous.
- Unknown labels, cross-topic labels, URLs, invented source names, and any
  legacy or unexpected model-authored topic identifiers are rejected. The model
  is not asked to produce topic IDs; planned topics come only from stored
  platform records.

## Topic Draft Attempt

Represents the model's response for one bounded topic-level drafting attempt.

| Field | Meaning |
| --- | --- |
| `attempt_number` | First attempt or one permitted correction attempt |
| `topic_id` | Topic scope being drafted |
| `status` | `pass`, `fail`, or `unusable` |
| `raw_response` | Untrusted model response |
| `validation_errors` | Deterministic reasons the draft failed or needed fallback |
| `duration_ms`, `input_characters`, `failure_code` | Diagnostic telemetry |
| `model_name`, `prompt_version`, `contract_version` | Version provenance |

Storage approach:

- Reuse `agentic_research_report_attempts`.
- Add an explicit nullable `topic_id` column for topic-scoped attempts. Whole
  report attempts from older packages may keep this field empty, but every new
  topic-section attempt MUST populate it.
- Enforce uniqueness for topic attempts by `report_id`, `topic_id`, and
  `attempt_number` so each planned topic can have its own first attempt and one
  bounded correction attempt without colliding with other topics.
- Preserve `topic_id` in API/report diagnostics so operator-facing failure
  reasons can identify the affected planned topic without parsing raw model
  output.
- Attempt diagnostics are audit data; they are not report-quality authority by
  themselves.

## Rendered Report Package

Represents the final operator-facing report or fallback evidence briefing.

| Field | Meaning |
| --- | --- |
| `markdown` | Platform-rendered Markdown |
| `quality_grade` | `PASS` or `FAIL` |
| `quality_reasons` | Concise platform-generated reasons |
| `report_origin` | `model_pass`, `model_fail`, or `fallback` |
| child input rows | Frozen source basis |
| child contribution rows | Accepted finding-to-source mappings |
| child exclusion rows | Sources not used and why |

Validation rules:

- The platform renders the section headings and topic-level source lists.
- Citation links use stored `source_ref` mappings, not model-authored links.
- If all topic drafts are unusable, the platform renders a fallback evidence
  briefing from the fixed input snapshot.
- If some topic drafts are usable and others are fallback/insufficient, the
  package is stored with `FAIL` and clear topic-specific reasons.

## State Transitions

Report package state remains append-only:

1. Load current planned topics and qualified inputs.
2. Create topic-scoped model attempts.
3. Validate and select usable topic findings or topic fallback content.
4. Render one report package.
5. Save report, inputs, contributions, exclusions, and attempts transactionally.
6. Let the existing graph transition `reporting -> completed`.

Research status transitions remain owned by `ResearchStore`, not this data model.
