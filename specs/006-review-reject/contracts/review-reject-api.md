# Contract: Human Evidence Review Actions

## Existing Acceptance Endpoint

`POST /v1/research/runs/{run_id}/evidence-trust/accept`

Records that an authenticated human operator allows one exact
`review_required` evidence version into automated model context.

### Request

```json
{
  "source_url": "https://example.com/article",
  "content_hash": "sha256-or-platform-content-hash",
  "reason": "Operator reviewed the captured text and approved this version.",
  "expires_at": "2026-12-31T23:59:59Z"
}
```

`expires_at` is optional.

### Response

Returns the effective `EvidenceTrustEvaluation` read model. Accepted
review-required evidence is returned with effective disposition `eligible`,
base disposition `review_required`, and the active human review decision.

### Errors

- `403`: caller is not an authenticated human operator with `research.write`.
- `404`: research run or evidence trust evaluation was not found.
- `409`: evidence is not review-required, a conflicting decision already
  exists, or the research workflow is not waiting for review.
- `503`: web-trust persistence or the governed workflow is unavailable.

## New Rejection Endpoint

`POST /v1/research/runs/{run_id}/evidence-trust/reject`

Records that an authenticated human operator reviewed one exact
`review_required` evidence version and does not allow it into automated model
context. The evidence and trust evaluation remain stored and visible.

### Request

```json
{
  "source_url": "https://example.com/article",
  "content_hash": "sha256-or-platform-content-hash"
}
```

An optional `reason` field may be included as an operator note, but it is not
required for rejection in this first version.

### Response

Returns the effective `EvidenceTrustEvaluation` read model. Rejected
review-required evidence keeps base disposition `review_required`, includes the
active human rejection decision and optional note when supplied, and remains
excluded from summaries, keywords, topic coverage, and final reports.

### Errors

- `400` or `422`: request is malformed.
- `403`: caller is not an authenticated human operator with `research.write`.
- `404`: research run or evidence trust evaluation was not found.
- `409`: evidence is not review-required, a conflicting decision already
  exists, or the research workflow is not waiting for review.
- `503`: web-trust persistence or the governed workflow is unavailable.

## Workflow Continuation Contract

After either endpoint records the human decision:

1. The API records the graph continuation request against the same human review
   decision.
2. The API resumes the existing LangGraph thread for the same `run_id`.
3. The graph reloads canonical trust decisions from `WebTrustStore`.
4. Accepted evidence may proceed to relevance/summarization.
5. Rejected evidence remains excluded and the workflow continues with other
   usable evidence.

The resume payload is execution context only. The stored human review decision
is the business record.

## UI Contract

The human review panel must show both actions:

- **Accept evidence and start summary**: tells the operator the exact captured
  version will be allowed into automated use.
- **Reject evidence**: tells the operator the exact captured version will stay
  stored for audit but will not be used by automated model steps.

Acceptance keeps its existing reason behavior. Reject can be completed without
entering a reason and does not require an expiry field.
