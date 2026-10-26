# Topic Research API Contract

All requests use the existing authenticated workspace. Topic IDs and nested
records are always scoped to it.

## Topic lifecycle

- `POST /v1/research/topics` with `{ "name": "Agentic web" }` creates a topic
  or returns its normalized-name match.
- `GET /v1/research/topics` returns topic cards with current revision metadata
  and latest associated canonical run status.
- `GET /v1/research/topics/{topic_id}` returns durable workspace metadata and a
  derived `attention_required` list when existing exact-version evidence review
  decisions are pending. Each attention item includes the existing review API
  inputs: `run_id`, `source_url`, and `content_hash`, plus the source title and
  review reason. This is not a stored topic status.

## Wiki reads

- `GET /v1/research/topics/{topic_id}/wiki` returns the current revision and
  latest update, or an explicit no-qualified-evidence state.
- `GET /v1/research/topics/{topic_id}/wiki/revisions` returns bounded history.
- `GET /v1/research/topics/{topic_id}/wiki/revisions/{revision_id}` returns one
  immutable snapshot with citations, sources, and exclusions.

## Ask a question

`POST /v1/research/topics/{topic_id}/questions`

```json
{ "question": "How are WebMCP tools being adopted?", "max_results": 30 }
```

The route validates topic ownership, finds or creates a topic-scoped run, and
calls the existing `UnifiedResearchWorkflowEntry`. It never performs research
itself. A repeated normalized question in the same topic returns the existing
run; the same words may be researched in another topic.

Before creating or reusing a question, the route derives the topic attention
queue from the existing run and evidence-review records. If the queue is not
empty, it returns `409 Conflict` with the pending evidence title, URL, review
reason, `run_id`, `source_url`, and `content_hash`. The UI uses those values
with the existing `POST /v1/research/runs/{run_id}/evidence-trust/accept` or
`POST /v1/research/runs/{run_id}/evidence-trust/reject` endpoint. It creates no
question. Once the operator records a decision for every item, the same request
can proceed.

## Research and sources

- `GET /v1/research/topics/{topic_id}/research` returns question/run history
  using canonical run status and contribution/no-change outcome.
- `GET /v1/research/topics/{topic_id}/sources` returns source library entries,
  summaries, keywords, trust disposition, URLs, introduction provenance, and
  exclusion reasons.

## Revision comparison

The current wiki response includes its immediate previous revision identifier,
when one exists, and the stored concise change summary from the current
revision's latest-update record. The UI presents this as **What changed since
the previous revision** and links to that prior immutable revision. It does not
generate a separate model comparison.

## Retired primary read

`GET /v1/research/runs/{run_id}/report` is retired as the primary operator
experience after cutover. Any temporary diagnostic compatibility route is
read-only and may not create a second report.
