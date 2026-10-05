# Quickstart: Bounded Final Report Batching

## Goal

Verify that a topic with many qualified summaries produces a useful final
report through bounded report groups instead of sending one oversized topic
payload to the local model.

## Preconditions

- Docker Compose stack is running.
- Local Ollama provider is configured for the workspace.
- The API and durable worker are using the current branch.

## Suggested Manual Scenario

1. Start with a clean test database or a known research run.
2. Run a research question likely to produce one large topic, such as:
   `examples of search engines and platforms that offer semantic search capabilities`.
3. Choose a source count high enough to create more than seven qualified
   summaries for the topic.
4. Wait for the workflow to complete.
5. Open the Final report panel.

## Expected Results

- The report contains one section for the planned topic.
- The topic section contains validated findings rather than only the fallback
  message caused by empty `{}` model output.
- Citations link to stored source summaries.
- The topic source list includes all qualified summaries for the topic, even if
  not every source is cited in a finding.
- If one bounded group failed, report quality explains the group-level report
  drafting issue while still showing findings from successful groups.

## Regression Checks

- A topic with fewer than seven summaries and below the prompt character budget
  still uses one group.
- A topic with exactly seven summaries and below the prompt character budget is
  not split unnecessarily.
- A topic with 15 qualified summaries is split into multiple groups.
- A topic with one very long summary is isolated into its own group if it
  exceeds the prompt character budget by itself.
- A model response of `{}` is rejected as empty findings and recorded with a
  clear validation reason and response character count.
- A group that cites a source outside its bounded group is rejected.
- A failed group does not erase successful findings from another group.

## Optional Runtime Observation

During testing, record whether Ollama has a model loaded before and after the
run with:

```powershell
Invoke-RestMethod -Uri http://localhost:11434/api/ps | ConvertTo-Json -Depth 10
```

This observation informs later runtime tuning for `keep_alive`, context size,
loaded-model count, and parallelism. It is not required for the correctness of
bounded report batching.
