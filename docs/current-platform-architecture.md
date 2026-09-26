# Current Platform Architecture

This diagram is the current-state architecture reference for design reviews. It
shows active production paths, implemented but disconnected components,
overlapping authority, older runtime infrastructure, and missing durable
continuation links. Update it whenever one of these relationships changes.

See the [Architecture Diagram Glossary](architecture-glossary.md) for the
purpose, inputs, outputs, and connections of every entity shown below.

```mermaid
flowchart TB
    USER["Operator"]

    subgraph UI["User Interfaces"]
        RESEARCH_UI["Research UI<br/>Question + source limit + Discover Sources"]
        ADMIN_UI["Admin UI<br/>Durable Work inspection and controls"]
    end

    subgraph API["FastAPI Application"]
        RESEARCH_ROUTE["POST /v1/research/runs<br/>Currently owns the active research sequence"]
        RESEARCH_READ["Research status and evidence APIs"]
        RUNTIME_API["Runtime inspection and control APIs<br/>No runtime creation endpoint"]

        subgraph ACTIVE_RESEARCH["Active Research Path"]
            INLINE["Inline orchestration in main.py<br/>Search → save → preflight → summarize"]
            RESEARCH_STORE["ResearchStore<br/>Research runs, sources, evidence, audit"]
        end

        subgraph NEW_AGENTIC["New Agentic Research Path"]
            UNIFIED_GRAPH["Unified LangGraph<br/>Topics → search → trust → relevance<br/>→ summaries → coverage → report"]
            AGENT_CONTROL["AgenticResearchControlService<br/>Capability checks, query reservations,<br/>attempt limits, gap-search limits"]
            AGENT_STORE["AgenticResearchStore<br/>Topics, relevance, coverage,<br/>capability audits, reports"]
        end

        subgraph OLD_RUNTIME["Earlier Governed Runtime"]
            RUNTIME_SERVICE["RuntimeService<br/>Roles, capability grants, transitions,<br/>human gates, runtime audit"]
            RUNTIME_STORE["RuntimeStore<br/>Runtime runs, steps, memory, events"]
            OLD_GRAPH["Old LangGraph executor<br/>Search full goal and extract first result"]
        end

        subgraph WEB_SERVICES["Governed Web and Evidence Services"]
            MCP["Governed MCP Host<br/>web.search + web.extract"]
            SEARCH["SearXNG search provider"]
            EXTRACT["Governed web extractor"]
            PREFLIGHT["CandidatePreflightService"]
            TRUST["EvidenceTrustService<br/>Local trust-policy authority"]
            TRUST_STORE["WebTrustStore<br/>Evaluations, policy version, overrides"]
            RELEVANCE["TopicRelevanceService"]
            SUMMARY["EvidenceSummaryService"]
            SUMMARY_STORE["EvidenceSummaryStore"]
            REPORT["ResearchReportingService"]
            OLLAMA["Local Ollama model<br/>qwen3:1.7b"]
        end
    end

    subgraph TEMPORAL["Temporal Durable Execution"]
        WORKER["Temporal worker"]
        PREFLIGHT_WF["CandidatePreflightWorkflow"]
        SUMMARY_WF["EvidenceSummaryWorkflow"]
        OLD_RUNTIME_WF["GovernedRuntimeWorkflow"]
    end

    DB[("PostgreSQL<br/>Canonical persisted state")]

    USER --> RESEARCH_UI
    USER --> ADMIN_UI

    RESEARCH_UI -->|"Discover Sources"| RESEARCH_ROUTE
    RESEARCH_UI -->|"Poll and review"| RESEARCH_READ
    ADMIN_UI --> RUNTIME_API

    RESEARCH_ROUTE --> INLINE
    INLINE --> RESEARCH_STORE
    INLINE --> SEARCH
    INLINE --> PREFLIGHT
    INLINE --> SUMMARY

    RESEARCH_ROUTE -. "NOT CONNECTED" .-> UNIFIED_GRAPH

    UNIFIED_GRAPH --> AGENT_CONTROL
    UNIFIED_GRAPH --> AGENT_STORE
    UNIFIED_GRAPH --> SEARCH
    UNIFIED_GRAPH --> PREFLIGHT
    UNIFIED_GRAPH --> RELEVANCE
    UNIFIED_GRAPH --> SUMMARY
    UNIFIED_GRAPH --> REPORT

    AGENT_CONTROL -. "DUPLICATED AGENT AUTHORITY" .-> RUNTIME_SERVICE

    RUNTIME_API --> RUNTIME_SERVICE
    RUNTIME_SERVICE --> RUNTIME_STORE
    OLD_RUNTIME_WF --> OLD_GRAPH
    OLD_GRAPH --> RUNTIME_SERVICE
    OLD_GRAPH --> MCP

    RUNTIME_SERVICE -. "NO ACTIVE CREATION OR SCHEDULING CALLER" .-> OLD_RUNTIME_WF

    MCP --> SEARCH
    MCP --> EXTRACT
    PREFLIGHT --> EXTRACT
    PREFLIGHT --> TRUST
    RELEVANCE --> TRUST
    RELEVANCE --> OLLAMA
    SUMMARY --> TRUST
    SUMMARY --> OLLAMA
    REPORT --> OLLAMA

    PREFLIGHT -->|"More than 2 sources"| PREFLIGHT_WF
    SUMMARY -->|"Durable summary threshold"| SUMMARY_WF
    PREFLIGHT_WF --> WORKER
    SUMMARY_WF --> WORKER
    OLD_RUNTIME_WF --> WORKER

    PREFLIGHT_WF -. "COMPLETION DOES NOT RESUME<br/>UNIFIED LANGGRAPH" .-> UNIFIED_GRAPH
    SUMMARY_WF -. "COMPLETION DOES NOT RESUME<br/>UNIFIED LANGGRAPH" .-> UNIFIED_GRAPH

    RESEARCH_STORE --> DB
    AGENT_STORE --> DB
    RUNTIME_STORE --> DB
    TRUST_STORE --> DB
    SUMMARY_STORE --> DB
    TRUST --> TRUST_STORE
    SUMMARY --> SUMMARY_STORE

    classDef active fill:#dcfce7,stroke:#15803d,color:#14532d;
    classDef ui fill:#dbeafe,stroke:#2563eb,color:#1e3a8a;
    classDef duplicate fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
    classDef disconnected fill:#fef3c7,stroke:#d97706,color:#78350f;
    classDef durable fill:#ede9fe,stroke:#7c3aed,color:#4c1d95;
    classDef legacy fill:#e5e7eb,stroke:#6b7280,color:#1f2937;
    classDef data fill:#cffafe,stroke:#0891b2,color:#164e63;

    class USER,RESEARCH_UI,ADMIN_UI ui;
    class RESEARCH_ROUTE,RESEARCH_READ,INLINE,RESEARCH_STORE,MCP,SEARCH,EXTRACT,PREFLIGHT,TRUST,TRUST_STORE,RELEVANCE,SUMMARY,SUMMARY_STORE,REPORT,OLLAMA active;
    class UNIFIED_GRAPH,AGENT_STORE disconnected;
    class AGENT_CONTROL,RUNTIME_SERVICE duplicate;
    class RUNTIME_API,RUNTIME_STORE,OLD_GRAPH,OLD_RUNTIME_WF legacy;
    class TEMPORAL,WORKER,PREFLIGHT_WF,SUMMARY_WF durable;
    class DB data;
```

## Legend

- **Green:** active production path or established service.
- **Yellow:** implemented but not connected to the operator workflow.
- **Red:** overlapping agent-authority responsibilities requiring consolidation.
- **Gray:** earlier runtime infrastructure without an active creation path.
- **Purple:** Temporal durable execution.
- **Dotted lines:** missing connection, inactive path, or architectural conflict.

## Reconciliation points

1. **Discover Sources still uses inline orchestration**, not the unified
   LangGraph.
2. **`AgenticResearchControlService` and `RuntimeService` overlap** in capability
   and workflow authority.
3. **Temporal completion cannot resume the unified graph**, while the current
   preflight worker can still start summaries outside the new relevance stage.

The Local Trust Policy is not duplicated. `EvidenceTrustService` remains its
independent authority and is used by both the active and proposed research
paths.
