# Research: Consolidated Research Architecture

## Decisions

### Use the existing topic-driven LangGraph as the only coordinator

**Decision**: Keep `agent_runtime/research_workflow.py` as the canonical graph,
finish its typed nodes, transfer useful cases from the plain-Python router and
old graphs, and retire those paths.

**Rationale**: The desired workflow already exists. The constitution selects
LangGraph and prohibits a competing Python state machine.

**Alternatives considered**: Keeping inline route orchestration, keeping the
plain-Python router beside LangGraph, or creating another graph package were
rejected because each preserves or adds duplicate orchestration.

### Extend RuntimeService instead of replacing it

**Decision**: Move all model-action authorization and limits under
`RuntimeService` and its PostgreSQL records. Retire
`AgenticResearchControlService` after migration.

**Rationale**: ADRs 0005, 0013, and 0016 and the constitution already name
RuntimeService as the authority owner. Combining its stored roles and grants
with the newer query, source, attempt, and gap checks produces one default-deny
boundary.

**Alternatives considered**: Replacing RuntimeService, adding Cerbos now, or
letting graph nodes carry grants were rejected because they would lose accepted
authority behavior or create another authority source.

### Use the official LangGraph PostgreSQL checkpointer

**Decision**: Add the official async PostgreSQL checkpointer, compile the graph
with it, and use the research task UUID as the thread ID.

**Rationale**: LangGraph defines checkpointers as its mechanism for thread
state, fault tolerance, interrupts, and resume. Its production guidance uses
`AsyncPostgresSaver`. Application stores remain the business record.

**Sources**: [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence),
[PostgreSQL checkpointer guidance](https://docs.langchain.com/oss/python/langgraph/add-memory#use-in-production),
the [PostgreSQL checkpointer reference](https://reference.langchain.com/python/langgraph.checkpoint.postgres),
and the [`AsyncPostgresSaver` API](https://reference.langchain.com/python/langgraph.checkpoint.postgres/aio/AsyncPostgresSaver).

**Lifecycle decision**: Call the official async saver `setup()` before research
readiness, use a versioned namespace, retain resumable threads, and use the
official list and `adelete_thread()` APIs for terminal and one-time cleanup.
Normal application code does not edit framework tables directly.

**Alternatives considered**: A custom resume store, in-memory checkpoints, and
a LangGraph business store were rejected because the official checkpointer and
existing application stores already own those responsibilities.

### Keep Temporal subordinate and resume through activities

**Decision**: Preserve the specific preflight and summary Temporal workflows.
After their existing activity stores a result, a typed continuation activity
resumes the same LangGraph thread.

**Rationale**: Temporal workflow definitions must remain deterministic;
database, model, MCP, and graph operations belong in activities.

**Sources**: [Temporal workflow definition](https://docs.temporal.io/workflow-definition)
and [Temporal Python SDK](https://python.temporal.io/).

**Alternatives considered**: Making Temporal the complete orchestrator, making
the UI interpret workflow completion, or adding another background worker were
rejected because they conflict with established owners.

### Invoke web capabilities through the existing MCP boundary

**Decision**: Authorized graph nodes invoke `web.search` and `web.extract`
through the existing governed MCP host and code-owned registry using an
in-process typed adapter.

**Rationale**: ADRs 0004 and 0010 make the MCP host the sole agent-facing web
tool boundary. The adapter avoids HTTP loopback without bypassing tool policy,
schema validation, provider selection, normalization, or audit.

**Alternatives considered**: Direct provider calls, giving the model an MCP
client, or adding another MCP server were rejected as policy bypasses or
duplicate tool boundaries.

### Treat Discover Sources as the operator start decision

**Decision**: The authenticated button action records human intent to start the
fixed read-only research plan. RuntimeService creates or reuses the server-owned
assignment without another approval screen.

**Rationale**: The specification requires the existing operator workflow and no
new start interface. Server policy, not the click, defines the available tools.

**Alternatives considered**: A second approval button and removing human
attribution were rejected because the former changes the approved workflow and
the latter weakens auditability.

### Use a selective clean start

**Decision**: Retain active evidence-domain records. Permit a documented reset
of obsolete runtime/control records, old graph checkpoints, and obsolete
Temporal runtime history. Keep representative fixtures when useful.

**Rationale**: Historical local retention is not a product requirement.
Evidence and trust records remain useful, while obsolete execution records
would force unnecessary compatibility code.
