# Feature Specification: Chunk-Aware Summary Batching

**Feature Branch**: `007-chunk-aware-summary-batching`  
**Created**: 2026-10-03  
**Status**: Draft  
**Input**: User description: "Improve evidence summary batching before durable execution by using source chunk counts, avoiding oversized durable executions, and allowing completed partial summary work to continue research."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reliable Summary Progress for Mixed-Size Sources (Priority: P1)

As an operator running local evidence research, I want the platform to divide summary work according to how much content each source contains, so one large group of sources does not time out and fail the entire research run.

**Why this priority**: This directly addresses the observed bottleneck where the platform grouped sources by count only, even though some sources contained far more chunks than others. Operators need research runs to make reliable progress when source sizes vary widely.

**Independent Test**: Can be tested by preparing a research run with small, medium, and very large sources, starting summary processing, and verifying that large sources are separated from smaller ones while small sources are still grouped efficiently.

**Acceptance Scenarios**:

1. **Given** a research run has several eligible sources with low chunk counts, **When** summary processing starts, **Then** those sources may be grouped together efficiently.
2. **Given** a research run has eligible sources with 6 to 15 chunks, **When** summary processing starts, **Then** those sources are assigned to smaller work groups that do not exceed 15 total chunks.
3. **Given** a research run has a single very large eligible source, **When** summary processing starts, **Then** that source is assigned to its own work group rather than bundled with other sources.
4. **Given** a proposed work group would exceed 15 total chunks, **When** the platform prepares summary work, **Then** the platform splits the work before durable processing begins unless the group contains one oversized source by itself.

---

### User Story 2 - Continue Research When Some Summary Work Succeeds (Priority: P2)

As an operator, I want a research run to continue using successful summaries when one background summary group fails, so useful evidence is not discarded because a separate source timed out or failed.

**Why this priority**: Operators care about the final research result. A single failed summary group should be visible and auditable, but it should not automatically erase successful summary work from the rest of the run.

**Independent Test**: Can be tested by causing one summary work group to fail while another completes, then verifying that completed summaries remain available for topic coverage and report generation.

**Acceptance Scenarios**:

1. **Given** multiple summary work groups are running for one research run, **When** at least one group completes and another group fails, **Then** the completed summaries remain stored and available for later research stages.
2. **Given** one summary work group fails, **When** enough successful summaries exist to continue the research run, **Then** the run continues instead of being marked failed solely because of the failed group.
3. **Given** a source could not be summarized, **When** the operator reviews the run status, **Then** the failed source is shown separately from completed summaries with a clear reason.

---

### User Story 3 - Clear Operator Visibility Into Summary Work Outcomes (Priority: P3)

As an operator, I want the research UI and status records to distinguish completed summaries from failed sources, so I can understand whether the run is blocked, partially successful, or ready for report generation.

**Why this priority**: The platform is still in active testing, and operators need plain explanations when background work fails. This also helps diagnose future local model or source-size issues without confusing them with trust-policy failures.

**Independent Test**: Can be tested by completing a run with both successful and failed summary sources and verifying that operator-visible status explains what succeeded, what failed, and whether the run continued.

**Acceptance Scenarios**:

1. **Given** a source fails during summary processing, **When** the operator views the run, **Then** the source is labeled as failed and excluded from automated report inputs.
2. **Given** other sources completed successfully, **When** report generation starts, **Then** only completed, eligible, relevant summaries are used.
3. **Given** all summary work fails, **When** the operator views the run, **Then** the run clearly explains that there were no usable summaries to continue from.

### Edge Cases

- A single source has 16 or more chunks and must be isolated without being blocked.
- All sources are small and can be grouped efficiently.
- All sources are large and must be split into smaller groups.
- One summary work group times out while another completes.
- A failed source was already excluded from automated model context.
- A research run has completed summaries but not enough qualifying summaries to produce a useful report.
- Existing summary records from prior runs are reused and should not be reprocessed unnecessarily.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The platform MUST size summary work groups using the amount of source content, not source count alone.
- **FR-002**: The platform MUST preserve a maximum source count for efficient processing of small sources.
- **FR-003**: The platform MUST enforce an initial maximum of 15 total chunks per summary work group.
- **FR-004**: The platform MUST treat sources with 6 to 15 chunks as above-normal sources and group them conservatively without exceeding 15 total chunks.
- **FR-005**: The platform MUST treat sources with 16 or more chunks as oversized and assign each oversized source to its own work group.
- **FR-006**: The platform MUST avoid creating a summary work group that exceeds 15 total chunks unless the group contains exactly one oversized source.
- **FR-007**: The platform MUST record the planned work groups in a way that explains how many sources and chunks each group contains.
- **FR-008**: The platform MUST keep completed summaries available when a separate summary work group fails or times out.
- **FR-009**: The platform MUST record failed summary work without deleting successful summaries, source records, trust records, or report inputs from other completed sources.
- **FR-010**: The platform MUST exclude failed summary sources from topic coverage and final report inputs.
- **FR-011**: The platform MUST continue to topic coverage and report generation when enough eligible, relevant, completed summaries exist.
- **FR-012**: The platform MUST mark the research run as unable to continue when no usable completed summaries exist after summary processing.
- **FR-013**: The platform MUST show operator-facing status that separates completed summary counts from failed source counts.
- **FR-014**: The platform MUST provide a clear operator-facing reason when a source fails summary processing because its assigned work did not complete.
- **FR-015**: The platform MUST keep batching decisions deterministic for the same set of sources and chunk counts.

### Authority and Safety Boundaries *(include for agent, workflow, or external-action features)*

- **Authorized actors**: The operator may start or retry a research run. The platform may prepare and execute summary work only for evidence that has already passed the existing eligibility and relevance workflow.
- **Human-only decisions**: This feature does not add any new human trust override, source approval, or rejection decision.
- **Agent limitations**: The local model does not decide how summary work is grouped, which sources are trusted, which failed sources are usable, or whether failed evidence may enter report context.
- **Canonical record**: Summary work records, source summary statuses, summary artifacts, and research run status remain the durable business records for summary progress and operator-facing workflow state.
- **Operator-visible states**: Operators may see summary processing as in progress, completed with all sources summarized, completed with some sources failed, failed because no usable summaries exist, or waiting for retry when background processing could not continue.
- **Decision authority**: Platform rules decide batching, source inclusion, failed-source exclusion, and whether enough completed summaries exist to continue. The model only produces summary content for assigned source content.
- **Conflict outcome**: If background execution records disagree with stored source summary records, stored completed source summaries remain usable, failed sources remain excluded, and the run status must explain the conflict instead of silently failing.
- **Excluded behavior**: This feature does not change source discovery, trust evaluation, human review decisions, relevance decisions, chunk size, summary prompt wording, report quality grading, or the operator's Discover Sources workflow.

### Key Entities *(include if feature involves data)*

- **Summary Work Group**: A bounded unit of summary work containing one or more sources and their known chunk counts.
- **Source Summary Status**: The stored status for one source as it moves through extraction, summarization, completion, failure, or exclusion from report inputs.
- **Summary Work Set**: The collection of summary work groups belonging to one research run.
- **Completed Summary Artifact**: A stored summary and keyword set produced for one eligible, relevant source.
- **Failed Summary Source**: A source that could not produce a valid completed summary and must remain outside automated topic coverage and report inputs.
- **Research Run Status**: The operator-facing status showing whether the research run is processing, waiting, completed, partially completed, or unable to continue.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a test set containing small and large sources, no planned summary work group exceeds 15 total chunks unless a single source exceeds that limit by itself.
- **SC-002**: In a test set of small sources, at least two sources can still share one work group when their combined chunk count stays at or below 15 total chunks.
- **SC-003**: In a test set containing a very large source, that source is assigned to its own work group.
- **SC-004**: When one summary work group fails and another completes, completed summaries remain available for topic coverage and report generation in 100% of tested cases where enough completed summaries exist.
- **SC-005**: Failed summary sources are excluded from automated report inputs in 100% of tested cases.
- **SC-006**: Operator-visible status identifies completed summary counts and failed source counts separately in tested mixed-outcome runs.
- **SC-007**: Re-running the same source list with the same chunk counts produces the same work grouping in 100% of deterministic batching tests.

## Assumptions

- Existing source chunk counts are available before summary work groups are planned.
- The current chunking policy remains unchanged for this feature.
- The normal observed source size is approximately 5.56 chunks, based on recent local test data.
- The first batching policy rounds that observed average to 6 chunks: 1 to 5 chunks is small, 6 to 15 chunks is above-normal, and 16 or more chunks is oversized.
- The initial maximum total chunk count per work group is 15.
- An oversized source is isolated in its own durable work group, not blocked.
- Completed summaries from successful work groups are useful even when other work groups fail.
- A failed source can be retried later through existing retry behavior or a future targeted retry feature.
