"""Async OpenMetadata MCP client (JSON-RPC 2.0 over HTTP)."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import count
from typing import Any

import httpx


class MCPError(Exception):
    """Base error for MCP operations."""


class MCPConnectionError(MCPError):
    """Raised when the MCP endpoint cannot be reached."""


class MCPToolNotFoundError(MCPError):
    """Raised when an MCP tool does not exist."""


class MCPAuthError(MCPError):
    """Raised when MCP authentication fails."""


@dataclass
class _RPCPayload:
    method: str
    params: dict[str, Any]


class OpenMetadataMCPClient:
    """Async client for OpenMetadata MCP tool discovery and invocation."""

    def __init__(self, base_url: str, token: str):
        """Initialize the MCP client.

        Args:
            base_url: MCP endpoint URL, for example ``http://localhost:8585/mcp``.
            token: OpenMetadata Personal Access Token.
        """
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._rpc_ids = count(start=1)

    @property
    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def list_tools(self) -> list[dict]:
        """List available MCP tools.

        Returns:
            A list of tool descriptors.

        Raises:
            MCPConnectionError: Network or service errors.
            MCPAuthError: Authentication failures.
        """
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(self.base_url, headers=self._headers)
            self._raise_for_status(response)
            payload = response.json()
        except httpx.HTTPError as exc:
            raise MCPConnectionError(f"MCP connection failed: {exc}") from exc
        except ValueError as exc:
            raise MCPConnectionError("Invalid MCP list_tools response (non-JSON)") from exc

        if isinstance(payload, dict) and "tools" in payload and isinstance(payload["tools"], list):
            return payload["tools"]
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]

        # Some servers expose tool listing only through JSON-RPC.
        rpc_result = await self._rpc_call_with_fallbacks(
            [
                _RPCPayload(method="tools/list", params={}),
                _RPCPayload(method="list_tools", params={}),
            ]
        )
        tools = rpc_result.get("tools", rpc_result if isinstance(rpc_result, list) else [])
        if isinstance(tools, list):
            return [x for x in tools if isinstance(x, dict)]
        return []

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a tool on the MCP endpoint.

        Args:
            tool_name: Tool identifier exposed by MCP.
            arguments: Tool arguments.

        Returns:
            Tool result as a dict.

        Raises:
            MCPConnectionError: Network or service errors.
            MCPToolNotFoundError: Unknown tool name.
            MCPAuthError: Authentication failures.
        """
        result = await self._rpc_call_with_fallbacks(
            [
                _RPCPayload(
                    method="tools/call",
                    params={"name": tool_name, "arguments": arguments},
                ),
                _RPCPayload(
                    method="call_tool",
                    params={"tool": tool_name, "arguments": arguments},
                ),
            ],
            tool_name=tool_name,
        )

        if isinstance(result, dict):
            return result
        return {"result": result}

    async def get_table_metadata(self, fqn: str) -> dict:
        """Fetch table metadata for a fully qualified table name."""
        return await self.call_tool("get_table", {"fullyQualifiedName": fqn})

    async def get_column_profile(self, fqn: str) -> dict:
        """Fetch column profile information for a fully qualified column name."""
        return await self.call_tool("get_column_profile", {"fullyQualifiedName": fqn})

    async def get_lineage(self, fqn: str, entity_type: str = "table") -> dict:
        """Fetch lineage graph for an entity."""
        return await self.call_tool("get_lineage", {"fqn": fqn, "entityType": entity_type})

    async def list_tables_with_drift(self, days: int = 7) -> list[dict]:
        """Search metadata entries related to drift in a rolling time window."""
        result = await self.call_tool(
            "search_metadata",
            {"query": "drift", "filters": {"days": days}},
        )
        if isinstance(result, dict):
            candidates = result.get("data") or result.get("hits") or result.get("results") or []
            if isinstance(candidates, list):
                return [x for x in candidates if isinstance(x, dict)]
        return []

    async def push_observation(self, fqn: str, observation: dict) -> dict:
        """Push a MetaVerdax observation into OpenMetadata test/quality artifacts."""
        payload = {"fullyQualifiedName": fqn, "observation": observation}
        try:
            return await self.call_tool("create_test_result", payload)
        except MCPToolNotFoundError:
            return await self.call_tool("add_observation", payload)

    async def create_task(
        self,
        fqn: str,
        title: str,
        description: str,
        assignee: str | None = None,
    ) -> dict:
        """Create an OpenMetadata task for high-risk scans."""
        args: dict[str, Any] = {
            "fullyQualifiedName": fqn,
            "title": title,
            "description": description,
        }
        if assignee:
            args["assignee"] = assignee
        return await self.call_tool("create_task", args)

    async def tag_entity(self, fqn: str, tags: list[str]) -> dict:
        """Tag an entity with MetaVerdax risk labels."""
        return await self.call_tool("add_tags", {"fullyQualifiedName": fqn, "tags": tags})

    async def _rpc_call_with_fallbacks(
        self,
        attempts: list[_RPCPayload],
        tool_name: str | None = None,
    ) -> Any:
        last_tool_error: MCPToolNotFoundError | None = None
        for payload in attempts:
            try:
                return await self._rpc_call(payload.method, payload.params)
            except MCPToolNotFoundError as exc:
                last_tool_error = exc
                continue
        if last_tool_error is not None:
            if tool_name:
                raise MCPToolNotFoundError(f"MCP tool not found: {tool_name}") from last_tool_error
            raise last_tool_error
        raise MCPConnectionError("MCP call failed across all method variants")

    async def _rpc_call(self, method: str, params: dict[str, Any]) -> Any:
        request_body = {
            "jsonrpc": "2.0",
            "id": next(self._rpc_ids),
            "method": method,
            "params": params,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.base_url, headers=self._headers, json=request_body)
            self._raise_for_status(response)
            payload = response.json()
        except httpx.HTTPError as exc:
            raise MCPConnectionError(f"MCP request failed: {exc}") from exc
        except ValueError as exc:
            raise MCPConnectionError("MCP response is not valid JSON") from exc

        if not isinstance(payload, dict):
            raise MCPConnectionError("Unexpected MCP response type")

        if "error" in payload:
            error = payload.get("error") or {}
            message = str(error.get("message", "Unknown MCP error"))
            code = error.get("code")
            lowered = message.lower()
            if code in (-32601, 404) or "tool" in lowered and "not found" in lowered:
                raise MCPToolNotFoundError(message)
            if code in (401, 403) or "auth" in lowered or "unauthorized" in lowered:
                raise MCPAuthError(message)
            raise MCPConnectionError(f"MCP RPC error: {message}")

        return payload.get("result", {})

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code in (401, 403):
            raise MCPAuthError(f"MCP auth failed ({response.status_code})")
        if response.status_code >= 400:
            raise MCPConnectionError(
                f"MCP HTTP error {response.status_code}: {response.text[:400]}"
            )
