# Data Model: Topic Research Wiki

## Naming

- **Research Topic**: operator-owned durable notebook.
- **Planned Topic**: existing model-proposed search focus in
  `agentic_research_topics`, attached to one run.

## New Canonical Records

### `research_topics`

| Field | Rule |
| --- | --- |
| `id`, `workspace_id` | Immutable identity and owning workspace. |
| `name`, `normalized_name` | Operator display name; unique per workspace. |
| `current_revision_id` | Nullable pointer to the one current wiki revision. |
| `created_at`, `updated_at` | Audit timestamps. |

It deliberately has no workflow-status field.

### `research_topic_runs`

| Field | Rule |
| --- | --- |
| `topic_id`, `run_id` | A run belongs to exactly one topic. |
| `input_kind` | `question`; records the operator-initiated entry type for this release. |
| `normalized_question` | Unique with `topic_id` for idempotent question reuse. |
| `created_at` | Immutable association time. |

Question text and all execution state remain in `research_runs`.

### Derived Topic Attention Queue

The topic workspace does not store an `attention_status` or a second topic
workflow state. It derives a **Needs your decision** queue by joining
`research_topic_runs` with the associated canonical `research_runs` and the
existing exact-version trust evaluation and human review records.

An item appears only when evidence for a question in that topic is awaiting an
operator accept/reject decision. It disappears as soon as the existing review
owner records either outcome. Publisher denials, blocked evidence, unreachable
sources, and other exclusions remain source information; they are not attention
items and do not stop a later question.

### `research_topic_sources` and `research_topic_source_introductions`

`research_topic_sources` contains one `(topic_id, evidence_id)` library entry
and its first introducing run. The append-only introductions table records every
later encounter or reuse, preserving the question that brought it in.

### `research_topic_wiki_revisions`

An immutable snapshot with `id`, `topic_id`, sequential `revision_number`,
`triggering_run_id`, nullable `previous_revision_id`, validated Markdown,
input fingerprint, model/prompt/contract versions, quality grade/reasons,
origin, and `created_at`.

### `research_topic_wiki_revision_inputs`, contributions, exclusions, updates

Revision inputs freeze qualified summary artifact, evidence hash, source label,
title, URL, Planned Topic context, and position. Contributions map claims to
allowed labels; exclusions preserve accurate reasons. One update record stores
the triggering question, source additions/exclusions, changed sections/findings,
and remaining gaps.

## Existing Records Reused

| Record | Continued authority |
| --- | --- |
| `research_runs`, transitions | One question's official lifecycle. |
| research source/evidence records | Candidate and retrieval facts. |
| trust evaluations/overrides | Model-context eligibility and human review. |
| Planned Topic, relevance, coverage records | Proof that evidence qualifies for a planned focus. |
| summary artifact/execution records | Validated summaries and keywords. |
| RuntimeStore | Capability grants and authorizations. |

## Transition Rules

1. A topic is created once. Archive/delete/rename are future features.
2. Topic-to-run membership is created atomically with run creation, or reuses an
   existing topic-scoped question.
3. Only the unified graph changes a run's existing lifecycle.
4. Before a new topic question is created or reused, `TopicWorkspaceService`
   derives the attention queue from canonical records in the same transaction.
   A non-empty queue returns the current pending decisions and creates no run.
5. An attention item clears when its existing exact-version accept/reject
   decision is recorded. The current question may then continue through its
   existing graph continuation while the operator is free to ask a later
   question in that topic.
6. The final-report node reads all qualified topic evidence. An unchanged
   fingerprint yields a visible no-change history outcome and no revision.
7. A changed fingerprint writes inputs, contributions, exclusions, update,
   revision, and current pointer in one transaction.
8. Revisions are never edited.
9. A concurrent report locks/reloads the topic; stale work becomes no-change or
   creates the next revision, never overwriting newer knowledge.

## Retired Model

The per-run `agentic_research_reports` package is retired as the operator-facing
artifact after cutover. Clean-start migration may remove test-era rows. Topic
revision records retain equivalent input, citation, exclusion, attempt, and
quality provenance.
