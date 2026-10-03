# Quickstart: Completed Checkpoint Cleanup

## Goal

Verify that completed-run checkpoint cleanup no longer blocks unrelated new
research and that cleanup remains safe, audited, and retryable.

## Local Verification Flow

1. Start the local stack.

   ```powershell
   docker compose up -d api durable-worker web postgres temporal
   ```

2. Run the focused workflow tests after implementation.

   ```powershell
   docker compose exec -T api python -m pytest -q apps/api/tests/test_unified_research_workflow.py
   ```

3. Run the API tests that cover research start behavior.

   ```powershell
   docker compose exec -T api python -m pytest -q apps/api/tests/test_web_research.py
   ```

4. Manual smoke test:

   - Start one research run from the UI.
   - Wait until it reaches completed.
   - Confirm completed research outputs remain visible.
   - Check `/health/services`; completed-run cleanup backlog may appear as
     degraded maintenance, but not as an unavailable workflow dependency.
   - Start a different research question.
   - Confirm the second run starts without the checkpoint-cleanup pending
     blocker.

5. Maintenance retry remains available:

   ```powershell
   docker compose exec -T api python -m app.agent_runtime.research_workflow retry-terminal-cleanup --limit 100
   ```

## Expected Results

- Completed research results remain visible after cleanup.
- Cleanup attempts are audited.
- Cleanup failure does not change a completed run back to active or failed.
- Pending completed-run cleanup is reported as maintenance health, not as a
  blocker for unrelated new research.
- The operator-facing cleanup message explains that cleanup affects only
  execution bookmarks and does not delete completed research outputs.
