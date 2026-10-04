# Quickstart: Correct Report Exclusion Labels

## Goal

Verify that report exclusions explain why a source was not used without
mislabeling extraction/access failures as topic relevance failures.

## Manual Verification

1. Start the local platform.
2. Run a research query that returns at least one source that is blocked by the
   local trust workflow or rejected by the publisher before extraction.
3. Wait for the research run to complete and open the final report.
4. Review **Sources not used for report findings**.
5. Confirm:
   - trust-policy blocks say they were blocked by local trust policy;
   - publisher access denials say usable evidence could not be captured because
     access was rejected;
   - unreachable sources say usable evidence was not captured;
   - summary failures say summary processing failed;
   - evidence-insufficient sources say the captured content was insufficient;
   - only summarized sources that failed topic qualification say they were not
     relevant to the planned topics.

## Automated Verification

Run the focused API tests for report exclusion reason derivation:

```powershell
docker run --rm -v "${PWD}:/workspace" -w /workspace/apps/api python:3.12-slim sh -lc "pip install --require-hashes --only-binary=:all: -r requirements-dev.lock >/dev/null && PYTHONPATH=/workspace/apps/api pytest -q tests/test_agentic_research.py tests/test_agentic_research_reporting.py tests/test_research_report.py"
```

Run the full API and web checks before opening a pull request if the UI changes:

```powershell
docker run --rm -v "${PWD}:/workspace" -w /workspace/apps/api python:3.12-slim sh -lc "pip install --require-hashes --only-binary=:all: -r requirements-dev.lock >/dev/null && ruff check . && PYTHONPATH=/workspace/apps/api pytest -q"
npm run build --prefix apps/web
```
