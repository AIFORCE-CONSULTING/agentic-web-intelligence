# Quickstart: Chunk-Aware Summary Batching

## Goal

Verify that summary work is grouped by source size, not by source count alone,
and that a failed internal summary execution does not erase successful summary
results from the same research run.

## Suggested Verification Flow

1. Start from branch `007-chunk-aware-summary-batching`.
2. Run the API tests after implementation:

   ```powershell
   docker run --rm -v "${PWD}:/workspace" -w /workspace/apps/api python:3.12-slim sh -lc "pip install --require-hashes --only-binary=:all: -r requirements-dev.lock >/dev/null && ruff check . && PYTHONPATH=/workspace/apps/api pytest -q"
   ```

3. Confirm unit tests cover these batch shapes:

   - several small sources sharing one group;
   - a medium source causing the next source to start a new group;
   - one oversized source assigned alone;
   - deterministic grouping for the same ordered input.

4. Confirm workflow tests cover these outcomes:

   - one internal summary execution fails but another completes;
   - the summary work set completes when usable summaries exist;
   - the research run continues to coverage/reporting when usable summaries
     exist;
   - failed sources are not included in coverage/report inputs.

5. Optional local smoke test:

   - Run the local Docker platform.
   - Start a research run with enough sources to include small and large pages.
   - Review summary status after completion.
   - Confirm completed summaries and failed sources are shown separately.

## Expected Result

Summary processing should no longer depend only on "up to five sources per
execution." Large pages should produce smaller durable work units, while small
pages can still be grouped efficiently. If one work unit fails, completed
summaries from other work units should remain usable.
