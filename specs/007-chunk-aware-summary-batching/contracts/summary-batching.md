# Contract: Chunk-Aware Summary Batching

This feature does not add a public API endpoint. It changes the internal
contract between the unified research workflow, the evidence-summary service,
the durable summary workflow, and stored summary records.

## Start Summary Stage

**Caller**: Unified LangGraph summary node  
**Owner**: Evidence-summary automation service  
**Input**:

- workspace id
- research run id
- ordered list of relevant source URLs
- workflow continuation context

**Required behavior**:

1. Remove duplicate URLs while preserving first-seen order.
2. Reuse an existing active or completed work set for the run when present.
3. Determine each source's chunk count before assigning final work groups.
4. Create work groups using both maximum source count and maximum total chunks.
5. Attach all created executions to one work set.
6. Route each execution through the existing direct/durable routing policy.
7. Return the stored work set.

## Batch Planner

**Input per source**:

- source URL
- content hash
- content character count
- chunk count
- chunking policy version

**Output per work group**:

- ordered source URLs
- total source count
- total chunk count
- oversized-source flag when one source alone has 16 or more chunks

**Rules**:

- Sources with 1 to 5 chunks are small and may share a group up to the maximum
  source count.
- Sources with 6 to 15 chunks are above-normal and may share a group only when
  the whole group stays at or below 15 total chunks.
- A source that would make the group exceed 15 total chunks starts a new group.
- A single source with 16 or more chunks is oversized and is allowed only as a
  one-source group; it is isolated, not blocked.
- Given the same ordered source list and chunk counts, the planner must produce
  the same groups.

## Durable Completion

**Caller**: Evidence summary Temporal workflow  
**Owner**: Evidence summary workflow/store  
**Input**:

- summary execution id
- workflow continuation envelope

**Required behavior**:

1. Execute the stored summary execution.
2. Mark that execution completed or failed.
3. Refresh the aggregate work set.
4. If the work set is still waiting, do not resume the graph yet.
5. If the work set completed with usable summaries, resume the graph with a
   successful summary outcome.
6. If the work set failed with no usable summaries, resume the graph with a
   failed summary outcome.

## Coverage and Reporting

**Caller**: Unified LangGraph continuation after summary stage  
**Owner**: Agentic research coverage/reporting stores  
**Required behavior**:

- Completed source summaries may be considered for topic coverage only when
  evidence, trust, relevance, and summary records all qualify.
- Failed summary sources remain excluded from coverage and final report input.
- Operator status must make mixed outcomes visible without treating failed
  sources as report evidence.
