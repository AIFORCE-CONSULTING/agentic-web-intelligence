# Architecture decisions

Architecture Decision Records (ADRs) preserve the context, decision, and
consequences of choices that materially shape the platform. They are reference
material for contributors and reviewers; start with the [Quickstart](quickstart.md)
and [project vision](foundation/project.md) if you are new to the project.

| Decision | Status | Date | Plain-language summary |
| --- | --- | --- | --- |
| [ADR 0001 — Monorepo](adr/0001-monorepo.md) | Accepted | 2026-08-09 | Keep the related applications, shared packages, infrastructure, and documentation in one repository. |
| [ADR 0002 — React and FastAPI](adr/0002-react-fastapi.md) | Accepted | 2026-08-09 | Use React for the operator experience and FastAPI for the Python-based platform services. |
| [ADR 0003 — Web intelligence via MCP](adr/0003-web-intelligence-mcp.md) | Accepted | 2026-08-09 | Put web search and extraction behind governed MCP tools instead of letting agents call providers directly. |
| [ADR 0004 — Governed web-research MVP](adr/0004-governed-web-research-mvp.md) | Accepted | 2026-08-21 | Start with a narrow, read-only public-web research capability that excludes unsafe browser actions. |
| [ADR 0005 — Governed agent-runtime contract](adr/0005-governed-agent-runtime-contract.md) | Accepted | 2026-08-31 | Keep authority, roles, tool permissions, and workflow decisions in platform code rather than model output. |
| [ADR 0006 — Local-first identity](adr/0006-local-first-enterprise-ready-identity.md) | Accepted | 2026-09-03 | Make local use straightforward today while leaving a safe path for enterprise sign-in later. |
| [ADR 0007 — Provider-neutral OIDC](adr/0007-provider-neutral-oidc-configuration-boundary.md) | Accepted | 2026-09-03 | Separate generic enterprise sign-in configuration from any single identity-provider product. |
| [ADR 0008 — Service identities](adr/0008-service-identities-are-revocable-and-least-privilege.md) | Accepted | 2026-09-04 | Give workers and integrations their own revocable, least-privilege identities. |
| [ADR 0009 — Deployment secrets](adr/0009-centralized-deployment-secrets.md) | Accepted | 2026-09-04 | Keep deployment credentials in an allowlisted server-side secret boundary, never in prompts or browser responses. |
| [ADR 0010 — Tool-registry governance](adr/0010-code-owned-tool-registry-governance.md) | Accepted | 2026-09-04 | Make the approved tool catalog code-owned so new integrations cannot silently gain authority. |
| [ADR 0011 — Operational security posture](adr/0011-operational-security-posture.md) | Accepted | 2026-09-04 | Fail safely for unsafe configuration and show administrators a safe, read-only security posture. |
| [ADR 0012 — GitHub Projects connector](adr/0012-human-operated-github-projects-connector.md) | Accepted | 2026-09-04 | Keep GitHub Project management human-operated rather than exposing broad GitHub authority to agents. |
| [ADR 0013 — Durable execution](adr/0013-governed-durable-execution-contract.md) | Accepted | 2026-09-08 | Use Temporal for long-running work while keeping platform policy in charge of what may run. |
| [ADR 0014 — Local-model provider](adr/0014-governed-local-model-provider.md) | Accepted, amended | 2026-09-11 | Keep local model inference behind a governed provider and distinguish summarization from research planning. |
| [ADR 0015 — Local web trust](adr/0015-local-policy-controlled-web-trust.md) | Accepted | 2026-09-16 | Evaluate captured web content with a local, explainable trust policy before automated use. |
| [ADR 0016 — Local agentic research](adr/0016-governed-local-agent-capability-requests.md) | Accepted | 2026-09-22 | Let the local model propose bounded research actions while the platform retains authority and enforcement. |
| [ADR 0017 — Research Topics as notebooks](adr/0017-topic-centered-research-notebook.md) | Accepted | 2026-10-22 | Organize repeated research questions, sources, and findings into one evolving topic-centered notebook. |
