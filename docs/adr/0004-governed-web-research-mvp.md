# ADR 0004: Deliver governed web research as a narrow MCP capability

- Status: Accepted
- Date: 2026-08-21

## Context

Phase 2 introduces the platform's first agent workflow: research on approved
public web pages. Open-source discovery, extraction, and browser automation
tools provide useful capabilities, but their native tool surfaces can permit
unbounded crawling, file downloads, authentication use, form submission, or
arbitrary browser interaction.

The platform needs a useful local-first MVP without granting an agent direct
control of those implementation tools.

## Decision

Expose only these read-only, platform-owned MCP capabilities to the agent:

- `web.search(query, max_results)`
- `web.extract(url)`

The MCP host is the agent's sole web-tool endpoint. It validates requests,
evaluates policy, selects an internal implementation, normalizes evidence, and
records an audit event. Agents never receive direct Crawl4AI, Playwright, or
provider-specific MCP tool definitions.

The initial implementations are self-hosted SearXNG for discovery and a
static-HTML extractor based on Trafilatura. Browser-backed extraction is an
internal fallback capability; it is not exposed as browser automation.

Phase 2 permits public `text/html` and `text/plain` responses only. It rejects
downloads, attachments, redirects to unsafe destinations, non-public network
addresses, authentication, form interaction, and unbounded crawling. Each
request is subject to URL validation, content-type checks, response-size and
timeout limits, and execution quotas.

## Consequences

The first workflow can produce sourced web-research results without coupling
agents to a vendor or granting them arbitrary browser control. The MCP host
becomes the stable contract for future provider substitutions.

PDF extraction, authenticated enterprise systems, interactive browser actions,
large-scale crawling, payments, and write operations are deferred. Each needs
its own explicit capability contract, policy model, and approval path.
