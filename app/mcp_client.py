"""Async OpenMetadata MCP client (JSON-RPC 2.0 over HTTP)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import count
import json
import logging
from typing import Any
from urllib.parse import quote

import httpx


logger = logging.getLogger(__name__)


class MCPError(Exception):
    """Base error for MCP operations."""


class MCPConnectionError(MCPError):
    """Raised when the MCP endpoint cannot be reached."""


class MCPNetworkError(MCPConnectionError):
    """Raised for transport-level connectivity failures."""


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
        self._api_base_url = self._derive_api_base_url(base_url)
        self.token = token
        self._rpc_ids = count(start=1)

    @staticmethod
    def _derive_api_base_url(base_url: str) -> str:
        normalized = base_url.rstrip("/")
        if normalized.endswith("/mcp"):
            return normalized[: -len("/mcp")]
        return normalized

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
        """Push a MetaVerdax observation into OpenMetadata feed."""
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        feed_payload = {
            "from": "admin",
            "message": f"MetaVerdax observation for {fqn}: {json.dumps(observation, default=str)}",
            "about": self._entity_link_for_table(fqn),
            "type": "Task",
            "taskDetails": {
                "type": "RequestTag",
                "assignees": [],
                "oldValue": "",
                "suggestion": "MetaVerdax observation logged",
            },
        }
        try:
            result = await self._post_feed(feed_payload)
            return {
                "observation_id": result.get("id") or result.get("threadTs"),
                "status": "posted",
                "status_code": result.get("status_code"),
                "endpoint": result.get("endpoint"),
                "result": result.get("result"),
            }
        except MCPNetworkError as exc:
            logger.warning("REST observation write failed, falling back to MCP: %s", exc)
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
        feed_payload: dict[str, Any] = {
            "from": "admin",
            "message": f"{title}: {description}",
            "about": self._entity_link_for_table(fqn),
            "type": "Task",
            "taskDetails": {
                "assignees": [assignee] if assignee else [],
                "oldValue": "",
                "suggestion": title,
                "type": "RequestTag",
            },
        }

        try:
            result = await self._post_feed(feed_payload)
            task_info = result.get("result", {}).get("task", {}) if isinstance(result.get("result"), dict) else {}
            return {
                "id": task_info.get("id") or result.get("id"),
                "status": task_info.get("status", "Open"),
                "status_code": result.get("status_code"),
                "endpoint": result.get("endpoint"),
                "result": result.get("result"),
            }
        except MCPNetworkError as exc:
            logger.warning("REST task write failed, falling back to MCP: %s", exc)
        args: dict[str, Any] = {
            "fullyQualifiedName": fqn,
            "title": title,
            "description": description,
        }
        if assignee:
            args["assignee"] = assignee
        return await self.call_tool("create_task", args)

    async def tag_entity(self, fqn: str, tags: list[str]) -> dict:
        """Tag a table entity with MetaVerdax risk labels."""
        if not tags:
            return {"status": "skipped", "reason": "No tags provided"}

        try:
            table = await self._get_table_by_fqn(fqn)
            table_id = str(table.get("id", "")).strip()
            if not table_id:
                raise MCPConnectionError(f"Could not resolve table id for {fqn}")
            return await self._patch_table_tags(fqn=fqn, table_id=table_id, tags=tags)
        except MCPNetworkError as exc:
            logger.warning("REST tag write failed, falling back to MCP: %s", exc)
            return await self.call_tool("add_tags", {"fullyQualifiedName": fqn, "tags": tags})

    @staticmethod
    def _entity_link_for_table(fqn: str) -> str:
        return f"<#E::table::{fqn}>"

    async def _post_feed(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._api_base_url}/api/v1/feed"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=self._headers, json=payload)
            self._raise_for_status(response)
            body = response.json() if response.text else {}
            return {
                "status_code": response.status_code,
                "endpoint": url,
                "result": body,
                "id": body.get("id") if isinstance(body, dict) else None,
            }
        except httpx.RequestError as exc:
            raise MCPNetworkError(f"OpenMetadata feed request failed: {exc}") from exc
        except ValueError as exc:
            raise MCPConnectionError("OpenMetadata feed response is not valid JSON") from exc

    async def _get_table_by_fqn(self, fqn: str) -> dict[str, Any]:
        encoded = quote(fqn, safe="")
        url = f"{self._api_base_url}/api/v1/tables/name/{encoded}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self._headers)
            self._raise_for_status(response)
            body = response.json()
            if not isinstance(body, dict):
                raise MCPConnectionError("OpenMetadata get-table response type is invalid")
            return body
        except httpx.RequestError as exc:
            raise MCPNetworkError(f"OpenMetadata table lookup failed: {exc}") from exc
        except ValueError as exc:
            raise MCPConnectionError("OpenMetadata get-table response is not valid JSON") from exc

    async def _patch_table_tags(self, fqn: str, table_id: str, tags: list[str]) -> dict[str, Any]:
        encoded_fqn = quote(fqn, safe="")
        fqn_url = f"{self._api_base_url}/api/v1/tables/{encoded_fqn}"
        id_url = f"{self._api_base_url}/api/v1/tables/{table_id}"

        # Keep the direct FQN PATCH attempt requested in the migration brief.
        fqn_payload = {"tags": [{"tagFQN": tag} for tag in tags]}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.patch(fqn_url, headers=self._headers, json=fqn_payload)
            if response.status_code < 400:
                body = response.json() if response.text else {}
                return {
                    "status": "tagged",
                    "tags": tags,
                    "status_code": response.status_code,
                    "endpoint": fqn_url,
                    "result": body,
                }
        except httpx.RequestError as exc:
            raise MCPNetworkError(f"OpenMetadata tag patch failed: {exc}") from exc
        except ValueError as exc:
            raise MCPConnectionError("OpenMetadata tag patch response is not valid JSON") from exc

        json_patch = [
            {
                "op": "add",
                "path": "/tags",
                "value": [{"tagFQN": tag, "source": "Classification"} for tag in tags],
            }
        ]
        patch_headers = dict(self._headers)
        patch_headers["Content-Type"] = "application/json-patch+json"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.patch(id_url, headers=patch_headers, json=json_patch)
            self._raise_for_status(response)
            body = response.json() if response.text else {}
            return {
                "status": "tagged",
                "tags": tags,
                "status_code": response.status_code,
                "endpoint": id_url,
                "result": body,
            }
        except httpx.RequestError as exc:
            raise MCPNetworkError(f"OpenMetadata tag patch failed: {exc}") from exc
        except ValueError as exc:
            raise MCPConnectionError("OpenMetadata tag patch response is not valid JSON") from exc

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
