# Feature Specification: Topic Research Wiki

**Feature Branch**: `011-topic-research-wiki`  
**Created**: 2026-10-21  
**Status**: Draft  
**Input**: User description: "Create a local, source-grounded research notebook with a durable topic wiki, cumulative research questions, visible update history, traceable claims, source library, and future studio outputs."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Build Knowledge Under One Topic (Priority: P1)

An operator creates or opens a named research topic, asks a question within that
topic, and starts research. The completed work contributes its qualified
evidence and findings to the topic rather than creating an isolated report.

**Why this priority**: The central product value is cumulative learning. A
topic must remain useful after many related questions have been researched.

**Independent Test**: Create a topic, complete two different research questions
under it, and confirm that both appear in the topic history and that their
qualified evidence is associated with the topic.

**Acceptance Scenarios**:

1. **Given** an operator has no topic selected, **When** they create a topic
   and ask a first question, **Then** the system starts research under that
   topic and presents a topic workspace rather than a standalone report.
2. **Given** a topic already has completed research, **When** the operator asks
   a related follow-up question in the same topic, **Then** the new work is
   recorded as another research question for that topic and does not replace
   its prior research history.
3. **Given** the same question is submitted again within one topic, **When** it
   is already represented by an active or completed research question,
   **Then** the operator sees the existing work rather than an unnecessary
   duplicate research question.
4. **Given** evidence from an earlier question in a topic requires human review,
   **When** the operator tries to ask another question in that same topic,
   **Then** the workspace shows the exact pending review decision and does not
   create the new question until the operator accepts or rejects that evidence.

---

### User Story 2 - Read the Current Wiki and Its Latest Update (Priority: P1)

An operator opens a topic and reads its current source-grounded wiki. The wiki
shows the current understanding, important themes, disagreements or caveats,
and open questions. A clearly visible latest-update summary explains what the
most recent completed research question added, changed, excluded, or left
unresolved.

**Why this priority**: A growing body of research becomes useful only when a
person can quickly understand its present state and what changed since the last
time they visited.

**Independent Test**: Complete research for a topic twice with different
questions. Open the topic and confirm that its current wiki is readable, the
latest update identifies the second question, and a prior wiki revision remains
available for comparison.

**Acceptance Scenarios**:

1. **Given** a topic has enough qualifying evidence, **When** an operator opens
   its wiki, **Then** they see a current source-grounded synthesis with
   traceable citations.
2. **Given** a later research question changes the wiki, **When** that work
   completes, **Then** the topic records a dated revision and a concise update
   summary that identifies additions, changed findings, exclusions, and
   remaining gaps when applicable.
3. **Given** an operator opens a citation or listed source from a wiki revision,
   **When** they select it, **Then** they can reach the stored source summary
   and its original source URL.
4. **Given** a topic does not yet have enough qualifying evidence for a useful
   synthesis, **When** an operator opens its wiki, **Then** the workspace says
   what is still needed without presenting unsupported findings as a wiki.

---

### User Story 3 - Inspect the Topic's Research and Source Library (Priority: P2)

An operator can inspect the questions asked within a topic and the topic's
retained evidence library. They can distinguish sources that informed the wiki
from sources that were excluded or could not be used, and can see why.

**Why this priority**: Trust in the wiki depends on transparent provenance and
on making failed or excluded retrievals understandable rather than invisible.

**Independent Test**: Complete a topic research question that produces at least
one usable source and one excluded source. Confirm that the Research and Sources
views expose both records and their respective outcomes.

**Acceptance Scenarios**:

1. **Given** a topic contains multiple research questions, **When** an operator
   opens its Research view, **Then** they can see each question, its status,
   completion time, and whether it produced a wiki update.
2. **Given** a topic has retained sources, **When** an operator opens its
   Sources view, **Then** they can browse source summaries, keywords, trust
   status, source links, and the research question that introduced each source.
3. **Given** a source could not inform the wiki, **When** an operator views it,
   **Then** the workspace provides a concise, accurate reason such as publisher
   access denial, trust-policy block, insufficient evidence, summary failure,
   or lack of relevance to the topic's planned research.

---

### User Story 4 - Preserve a Clear Future Studio Boundary (Priority: P3)

An operator can recognize that the topic workspace is the source-grounded basis
for future outputs such as briefings, slide decks, mind maps, tables,
infographics, flashcards, and video outlines. The first release does not
generate these outputs or imply that they are already available.

**Why this priority**: It keeps the product direction visible without mixing
unbuilt generation capabilities into the initial wiki workflow.

**Independent Test**: Open a topic workspace and confirm that the Studio area
accurately describes its future purpose without offering unavailable generation
actions.

**Acceptance Scenarios**:

1. **Given** an operator opens a topic workspace, **When** they navigate to the
   Studio area, **Then** they can understand that later outputs will be derived
   from the topic's grounded wiki and sources.
2. **Given** Studio output generation has not been implemented, **When** an
   operator uses the workspace, **Then** no action suggests an unavailable
   output can be generated.

### Edge Cases

- A topic exists but none of its research questions has completed with enough
  qualifying evidence to create a wiki revision.
- A new research question completes but contributes no qualifying evidence; the
  question remains in history and its outcome is visible without changing the
  current wiki.
- A later research question revises or contradicts an earlier finding; the new
  wiki revision must make the change visible without overwriting the history of
  prior versions.
- A source supports more than one question in the same topic; it is retained
  once in the topic library while preserving every question that used it.
- A source belongs to a research question but is blocked, review-required,
  unavailable, insufficient, or otherwise excluded; it must not enter the wiki
  merely because it is visible in the topic's source library.
- A topic title is reused in the same workspace; the system must prevent
  ambiguous duplicate topic containers or let the operator deliberately select
  the existing topic.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST let an operator create a named research topic and
  return to it for later research.
- **FR-002**: The system MUST associate each research question with exactly one
  topic and preserve the question's status, timing, and outcome in that topic's
  history.
- **FR-003**: The normal research entry point within a topic MUST be a
  plain-language question. The system MUST discover, evaluate, and retain
  eligible sources through the existing governed research workflow without
  requiring the operator to select separate extraction or summarization steps.
- **FR-004**: The system MUST present one current wiki for each topic. The wiki
  MUST be grounded only in qualified stored evidence associated with that topic.
- **FR-005**: The system MUST create an immutable, dated wiki revision whenever
  a completed research question changes the current topic wiki. A revision MUST
  identify the question that caused it and the evidence snapshot used.
- **FR-006**: The system MUST show a concise latest-update summary at the top
  of a topic wiki. When applicable, it MUST identify the researched question,
  sources added or excluded, sections created or revised, new or changed
  findings, and remaining gaps or suggested next questions.
- **FR-007**: The system MUST let an operator view earlier wiki revisions and
  determine what changed between the current revision and its immediate
  predecessor in understandable language.
- **FR-008**: Every wiki claim and source list MUST provide a path to the
  supporting stored source summary and the original source URL. The system MUST
  not display a citation as supported when it cannot be resolved to retained
  evidence.
- **FR-009**: The system MUST provide a Research view that lists research
  questions within the topic, including their status, date, contribution to a
  wiki revision, and any visible failure or waiting reason.
- **FR-010**: The system MUST provide a Sources view that lists topic-associated
  source summaries, keywords, trust status, source links, and the question or
  questions that introduced each source.
- **FR-011**: The system MUST distinguish sources used in a wiki revision from
  sources that were excluded. An excluded source MUST retain a concise,
  accurate reason and MUST remain outside model-generated wiki findings unless
  it later qualifies through the established trust and evidence process.
- **FR-012**: The system MUST preserve the existing evidence, trust, relevance,
  summary, keyword, and report provenance necessary to explain why a source
  was or was not used in a topic wiki.
- **FR-013**: The system MUST show Studio as a future, read-only product area in
  this release. It MUST not generate a briefing, slide deck, mind map, table,
  infographic, flashcards, video, or any other new artifact.
- **FR-014**: The system MUST keep topics, their research questions, wiki
  revisions, sources, and update summaries isolated to the operator's
  workspace.
- **FR-015**: The system MUST not treat a search result, untrusted capture,
  blocked evidence, review-required evidence, failed summary, or malformed model
  response as support for a wiki claim.
- **FR-016**: The system MUST derive a topic-level attention queue from the
  existing unresolved evidence-review records. Before it creates a new question
  in that topic, it MUST require the operator to accept or reject each pending
  exact evidence version. Blocked, unreachable, irrelevant, and other
  non-review exclusions remain visible information and do not create this gate.

### Authority and Safety Boundaries

- **Authorized actors**: An authenticated operator creates topics, chooses an
  existing topic for a question, starts research, and reviews topic results.
  The governed research workflow may contribute validated evidence and propose
  source-grounded wiki content only within the operator's selected topic.
- **Human-only decisions**: An operator remains responsible for any existing
  human evidence-review decision. The system does not treat topic membership or
  a wiki revision as human acceptance of evidence requiring review.
- **Agent limitations**: A model cannot create arbitrary topics, move a research
  question between topics, broaden source access, start research without an
  operator question, change trust policy, approve evidence, or write a wiki
  revision without platform validation.
- **Canonical record**: Topic identity, research-question membership, current
  wiki pointer, wiki revision history, source association, and update summaries
  must survive retries and execution restarts. Existing evidence, trust,
  relevance, summary, keyword, and report records remain their own canonical
  records and are referenced rather than copied as competing facts.
- **Operator-visible states**: A topic has no separately stored workflow status.
  Its workspace derives an activity summary from its associated research runs
  and a **Needs your decision** queue from unresolved exact-version evidence
  reviews. That queue blocks a new question in the same topic only until the
  operator records accept or reject. Individual research questions retain their
  existing lifecycle status and any clear failure or waiting explanation.
- **Decision authority**: Platform validation decides whether evidence may enter
  model context and whether a wiki revision is grounded. The local model may
  draft bounded source-grounded content but cannot decide its own support,
  completeness, or publication.
- **Conflict outcome**: If an incoming research result conflicts with current
  topic membership or a newer wiki revision, the system must preserve the
  existing revision, record the conflict or stale result, and require a
  controlled retry or operator-visible resolution rather than silently replacing
  newer knowledge.
- **Excluded behavior**: This feature does not add external publishing,
  collaboration, unrestricted document editing, agent-selected browser actions,
  automatic trust-policy overrides, or Studio artifact generation.

### Key Entities

- **Research Topic**: A workspace-scoped, durable subject of investigation that
  groups related research questions, retained sources, wiki revisions, and
  updates.
- **Topic Research Question**: One operator-requested investigation belonging
  to one research topic. It retains the outcome of the governed research
  workflow without becoming the topic itself.
- **Topic Wiki Revision**: An immutable, dated, source-grounded representation
  of the topic's current understanding after a qualifying research question.
- **Wiki Update Summary**: A concise explanation of how one wiki revision
  differs from its predecessor, including contributions, exclusions, changed
  findings, and remaining gaps.
- **Topic Source Association**: A traceable relationship between a retained
  source and the research question or questions through which it entered the
  topic library, including its use or exclusion in each wiki revision.
- **Studio Area**: A visible but read-only placeholder for future grounded
  artifacts derived from a topic wiki and its qualified sources.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can create a topic, submit a first question, and find
  that question in the topic's research history without navigating to a separate
  report workspace.
- **SC-002**: After two completed qualifying questions under one topic, an
  operator can identify the latest question, its resulting wiki update, and the
  prior wiki revision in no more than three selections from the topic home.
- **SC-003**: For every citation shown in a wiki revision, an operator can open
  the corresponding stored source summary and original URL without leaving the
  topic context unexpectedly.
- **SC-004**: Every source displayed as excluded from a wiki revision has one
  visible, accurate exclusion reason; no excluded source appears as support for
  a wiki claim.
- **SC-005**: A topic with no qualifying evidence never displays an unsupported
  synthesis. It instead tells the operator that more qualifying evidence is
  needed.
- **SC-006**: A later research question does not erase prior topic questions or
  wiki revisions; operators can inspect the current and immediately preceding
  revision for every changed topic.

## Assumptions

- The first release creates topic workspaces for new research. Existing
  test-era standalone research records do not need to be retroactively grouped
  unless a later design explicitly adds that migration.
- A topic has one workspace-scoped name and is chosen explicitly before a new
  question begins. The platform may use a normalized name to prevent accidental
  duplicate topics in that workspace.
- Each qualifying research question produces at most one resulting wiki
  revision. A question that yields no supported change remains visible in topic
  history but does not create a revision merely to duplicate the current wiki.
- The current final-report capability can be adapted as a bounded source-grounded
  input to a topic wiki, but this specification does not select the implementation
  design for that adaptation.
- Existing human evidence-review and local trust-policy behavior remain in
  force. Topic organization does not weaken those controls.
- Studio is intentionally a future product area. Its artifacts, generation
  contracts, persistence, cost limits, and review workflow require separate
  specifications.
