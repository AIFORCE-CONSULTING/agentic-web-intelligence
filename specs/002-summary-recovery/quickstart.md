# Quickstart: Verify Reliable Summary Recovery

1. Configure the existing local model provider and start the local Compose platform.
2. Start a research task with at least two eligible, relevant sources.
3. Use a deterministic provider fixture to return invalid JSON or an invalid keyword list for a single summary unit, followed by a valid response. Confirm that exactly two completed responses are recorded for that unit and that only the valid result becomes a source summary.
4. Use a fixture that returns invalid responses for both permitted attempts for one source and valid responses for another. Confirm that:
   - the failed source has a safe reason, category, and two recorded attempts;
   - the successful source retains its summary and keywords;
   - the execution completes rather than failing wholesale;
   - topic coverage and reporting use only the successful source; and
   - the report includes the platform-generated omitted-source notice.
5. Use a fixture that exhausts recovery for every eligible, relevant source. Confirm that the execution and research task fail and no report exists.
6. Stop and restart the API or durable worker between the first rejected response and the corrective response. Confirm that the same attempt identity resumes and never exceeds two completed responses for its summary unit.
7. Simulate model-provider unavailability. Confirm that it is recorded as a dependency failure, not a keyword-contract failure, and does not create an accepted summary or report.
8. Open the Research workspace. Confirm that the summary-status area identifies failed sources without displaying raw model output, and that the read-only Final report section displays the stored report and its omitted-source notice.
9. Confirm existing v1 summaries remain visible and their historical nullable coverage data does not prevent source reuse.
