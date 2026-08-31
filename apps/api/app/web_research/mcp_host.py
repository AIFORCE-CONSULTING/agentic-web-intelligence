"""A narrow, platform-owned MCP host for governed web research.

The host deliberately exposes platform capabilities rather than provider tools.
Agents can discover and invoke only ``web.search`` and ``web.extract``; SearXNG,
HTTP clients, and Trafilatura remain implementation details behind this boundary.
"""

import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.web_research.contracts import (
    Evidence,
    ExtractRequest,
    SearchRequest,
    SearchResponse,
    ToolPolicyError,
    ToolProviderError,
    ToolRetrievalError,
)
from app.web_research.workflow import run_extract_workflow, run_search_workflow

MCP_PROTOCOL_VERSION = "2025-03-26"


class McpToolCallError(ValueError):
    """A safe error returned to an MCP client for one tool invocation."""


AuditRecorder = Callable[[str | None, str, str, dict[str, object]], Awaitable[None]]


@dataclass(frozen=True)
class McpToolDefinition:
    """One agent-visible capability in the platform-owned tool registry."""

    name: str
    description: str
    input_schema: dict[str, Any]

    def as_mcp_tool(self) -> dict[str, Any]:
        """Render the standard MCP ``tools/list`` representation."""

        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "annotations": {"readOnlyHint": True, "destructiveHint": False},
        }


class GovernedWebToolPolicy:
    """Allow-list and dispatcher for every agent-initiated web operation."""

    _tools = (
        McpToolDefinition(
            name="web.search",
            description=(
                "Discover a bounded number of public source candidates through the "
                "platform's approved search provider."
            ),
            input_schema=SearchRequest.model_json_schema(),
        ),
        McpToolDefinition(
            name="web.extract",
            description=(
                "Retrieve bounded evidence from one approved public HTML or plain-text page."
            ),
            input_schema=ExtractRequest.model_json_schema(),
        ),
    )

    def list_tools(self) -> list[dict[str, Any]]:
        """Return only the approved, read-only agent-facing tools."""

        return [tool.as_mcp_tool() for tool in self._tools]

    async def call(self, name: str, arguments: Mapping[str, Any]) -> SearchResponse | Evidence:
        """Validate a named capability before it can reach an implementation."""

        if name == "web.search":
            try:
                request = SearchRequest.model_validate(arguments)
            except ValidationError as error:
                raise McpToolCallError(f"Invalid arguments for web.search: {error}") from error
            return await run_search_workflow(request.query, request.max_results)

        if name == "web.extract":
            try:
                request = ExtractRequest.model_validate(arguments)
            except ValidationError as error:
                raise McpToolCallError(f"Invalid arguments for web.extract: {error}") from error
            return await run_extract_workflow(request.url)

        raise McpToolCallError(f"MCP tool '{name}' is not permitted by the platform policy.")


class GovernedWebMcpHost:
    """Minimal JSON-RPC MCP transport for the governed web-tool policy."""

    def __init__(
        self,
        policy: GovernedWebToolPolicy | None = None,
        audit_recorder: AuditRecorder | None = None,
    ) -> None:
        self._policy = policy or GovernedWebToolPolicy()
        self._audit_recorder = audit_recorder

    def list_tools(self) -> list[dict[str, Any]]:
        """Expose the policy registry for the HTTP catalog and MCP clients."""

        return self._policy.list_tools()

    async def handle(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Handle the MCP methods needed by Phase 2's tool-only server."""

        request_id = payload.get("id")
        method = payload.get("method")
        params = payload.get("params", {})
        if payload.get("jsonrpc") != "2.0" or not isinstance(method, str):
            return self._error(request_id, -32600, "Invalid JSON-RPC request.")
        if not isinstance(params, Mapping):
            return self._error(request_id, -32602, "MCP parameters must be an object.")

        if method == "initialize":
            return self._result(
                request_id,
                {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "agentic-web-intelligence", "version": "0.1.0"},
                },
            )
        if method == "tools/list":
            return self._result(request_id, {"tools": self.list_tools()})
        if method == "tools/call":
            return await self._call_tool(request_id, params)
        return self._error(request_id, -32601, f"MCP method '{method}' is not supported.")

    async def _call_tool(self, request_id: object, params: Mapping[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or not isinstance(arguments, Mapping):
            return self._error(
                request_id, -32602, "tools/call requires a tool name and object arguments."
            )
        try:
            result = await self._policy.call(name, arguments)
        except (McpToolCallError, ToolPolicyError, ToolProviderError, ToolRetrievalError) as error:
            outcome = (
                "denied" if isinstance(error, (McpToolCallError, ToolPolicyError)) else "failed"
            )
            audit_recorded = await self._record_outcome(
                request_id,
                name,
                outcome,
                self._failure_details(arguments, error),
            )
            if not audit_recorded:
                return self._audit_unavailable_result(request_id)
            return self._result(
                request_id,
                {
                    "content": [{"type": "text", "text": str(error)}],
                    "isError": True,
                },
            )
        serialized = result.model_dump(mode="json")
        audit_recorded = await self._record_outcome(
            request_id,
            name,
            "succeeded",
            self._success_details(result),
        )
        if not audit_recorded:
            return self._audit_unavailable_result(request_id)
        return self._result(
            request_id,
            {
                "content": [{"type": "text", "text": json.dumps(serialized, sort_keys=True)}],
                "structuredContent": serialized,
            },
        )

    async def _record_outcome(
        self, request_id: object, tool_name: str, outcome: str, details: dict[str, object]
    ) -> bool:
        if self._audit_recorder is None:
            return True
        safe_request_id = str(request_id)[:128] if isinstance(request_id, (str, int)) else None
        try:
            await self._audit_recorder(safe_request_id, tool_name, outcome, details)
        except Exception:
            return False
        return True

    @staticmethod
    def _success_details(result: SearchResponse | Evidence) -> dict[str, object]:
        if isinstance(result, SearchResponse):
            return {"result_count": len(result.results)}
        return {"url": result.url, "content_hash": result.content_hash}

    @staticmethod
    def _failure_details(arguments: Mapping[str, Any], error: Exception) -> dict[str, object]:
        details: dict[str, object] = {"reason": str(error), "argument_names": sorted(arguments)}
        requested_url = arguments.get("url")
        if isinstance(requested_url, str):
            details["requested_url"] = requested_url
        return details

    @staticmethod
    def _audit_unavailable_result(request_id: object) -> dict[str, Any]:
        return GovernedWebMcpHost._result(
            request_id,
            {
                "content": [
                    {"type": "text", "text": "The MCP execution audit store is unavailable."}
                ],
                "isError": True,
            },
        )

    @staticmethod
    def _result(request_id: object, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error(request_id: object, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }
