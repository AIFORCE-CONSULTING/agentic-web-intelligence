# Quickstart: Human Evidence Review Rejection

## Manual Review Scenario

1. Start the local platform stack with API, worker, web, database, Temporal,
   SearXNG, and Ollama.
2. Start a research run that produces at least one source with
   `review_required` trust disposition.
3. Open the candidate preflight section in the UI.
4. Select **Review evidence** for the review-required source.
5. Confirm the panel shows the requested URL, final evidence URL, content hash,
   captured text, policy rules, and both human actions.
6. Choose **Reject evidence** and confirm. A reviewer note may be entered if
   the UI offers one, but it is optional in this first version.
7. Verify the run leaves `awaiting_review` and continues with other usable
   evidence.
8. Verify the rejected source remains visible in the candidate list and trust
   review details.
9. Verify the rejected source does not appear in summaries, keyword cards,
   topic coverage, or the final report.

## Acceptance Regression

1. Repeat the same review-required setup.
2. Choose **Accept evidence and start summary** with a reason.
3. Verify existing acceptance behavior remains unchanged: the exact accepted
   evidence version becomes eligible and the workflow resumes.

## Relevance-Stage Pause Regression

1. Use a run where a review-required source is encountered while the workflow is
   evaluating relevance.
2. Verify the operator-visible run status becomes `awaiting_review`.
3. Reject or accept the exact evidence version.
4. Verify the same run resumes without creating a second research run.

## Invalid Decision Checks

- Reject evidence without a reason: request succeeds and records the reviewer,
  timestamp, evidence version, and rejection outcome.
- Reject evidence that is already eligible or blocked: request is refused.
- Reject evidence after it was already accepted or rejected: request returns a
  clear conflict and does not silently replace the decision.
- Attempt review from a non-human or unauthenticated caller: request is refused.

## Verification Commands

```powershell
docker compose up -d --build api worker web
docker compose exec api pytest -q apps/api/tests/test_web_trust.py
docker compose exec api pytest -q apps/api/tests/test_web_research.py
docker compose exec api pytest -q apps/api/tests/test_unified_research_workflow.py
```

Use the repository's current test command if container paths differ in the
active environment.
