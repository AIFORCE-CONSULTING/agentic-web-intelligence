# ADR 0003: Govern web intelligence through MCP

- Status: Accepted
- Date: 2026-08-09

## Context

Web search and content extraction are the first platform capability, but web providers differ in tool contracts, cost, reliability, and security posture.

## Decision

Expose web search, fetch, extract, and crawl capabilities through an MCP host and a normalized platform contract. Agents do not invoke vendor tools directly.

## Consequences

The platform can adopt open MCP servers and change providers without exposing vendor-specific interfaces to every agent. The host becomes the enforcement point for provenance, egress policy, rate limiting, and prompt-injection defenses.
