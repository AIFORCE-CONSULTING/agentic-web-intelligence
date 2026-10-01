# Quickstart: Verify Reliable Summary Recovery

1. Configure the existing local model provider and start the local Compose platform.
2. Start a research task with at least two eligible, relevant sources.
3. Use a deterministic provider fixture to return invalid JSON, a blank keyword, a duplicate keyword, or an out-of-range keyword list for a single summary unit, followed by a valid response. Confirm that exactly two completed responses are recorded for that unit and that only the valid result becomes a source summary. Confirm that a valid keyword phrased differently from the summary prose is accepted.
4. Use a fixture that returns invalid responses for both permitted attempts for one source and valid responses for another. Confirm that:
   - the failed source has a safe reason, category, and two recorded attempts;
   - the successful source retains its summary and keywords;
   - the execution completes rather than failing wholesale;
   - topic coverage and reporting use only the successful source; and
   - the report includes the platform-generated omitted-source notice.
5. Use more than five eligible, relevant sources so the platform creates more than one internal summary execution. Make one internal job exhaust recovery and another produce a valid summary. Confirm that the combined summary work set completes, the research task continues, and the report uses only the valid summary with an omission notice.
6. Use a fixture that exhausts recovery for every eligible, relevant source. Confirm that the completed summary work set and research task fail and no report exists.
7. Stop and restart the API or durable worker between the first rejected response and the corrective response. Confirm that the same attempt identity resumes and never exceeds two completed responses for its summary unit.
8. Simulate model-provider unavailability. Confirm that it is recorded as a dependency failure, not a keyword-contract failure, and does not create an accepted summary or report when every source fails.
9. Open the Research workspace. Confirm that the summary-status area combines every internal job for the research task, identifies failed sources without displaying raw model output, and that the read-only Final report section displays the stored report and its omitted-source notice.
10. Confirm existing v1 summaries remain visible and their historical nullable coverage data does not prevent source reuse.
