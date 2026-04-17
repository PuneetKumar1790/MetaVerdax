from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.mcp_client import (
    MCPAuthError,
    MCPToolNotFoundError,
    OpenMetadataMCPClient,
)


def test_list_tools_http_get_success() -> None:
    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            assert request.url.path == "/mcp"
            return httpx.Response(200, json={"tools": [{"name": "get_table"}]})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://mock"):
            pass

        client = OpenMetadataMCPClient("http://mock/mcp", token="tkn")

        original_async_client = httpx.AsyncClient

        class PatchedClient(httpx.AsyncClient):
            def __init__(self, *args, **kwargs):
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        httpx.AsyncClient = PatchedClient
        try:
            tools = await client.list_tools()
        finally:
            httpx.AsyncClient = original_async_client

        assert tools == [{"name": "get_table"}]

    asyncio.run(_run())


def test_call_tool_json_rpc_success() -> None:
    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content.decode("utf-8"))
            assert body["method"] in {"tools/call", "call_tool"}
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"ok": True}})

        transport = httpx.MockTransport(handler)
        client = OpenMetadataMCPClient("http://mock/mcp", token="tkn")

        original_async_client = httpx.AsyncClient

        class PatchedClient(httpx.AsyncClient):
            def __init__(self, *args, **kwargs):
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        httpx.AsyncClient = PatchedClient
        try:
            result = await client.call_tool("get_table", {"fullyQualifiedName": "a.b.c"})
        finally:
            httpx.AsyncClient = original_async_client

        assert result["ok"] is True

    asyncio.run(_run())


def test_call_tool_not_found_error() -> None:
    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "error": {"code": -32601, "message": "Tool not found"},
                },
            )

        transport = httpx.MockTransport(handler)
        client = OpenMetadataMCPClient("http://mock/mcp", token="tkn")

        original_async_client = httpx.AsyncClient

        class PatchedClient(httpx.AsyncClient):
            def __init__(self, *args, **kwargs):
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        httpx.AsyncClient = PatchedClient
        try:
            with pytest.raises(MCPToolNotFoundError):
                await client.call_tool("missing", {})
        finally:
            httpx.AsyncClient = original_async_client

    asyncio.run(_run())


def test_list_tools_auth_error() -> None:
    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="unauthorized")

        transport = httpx.MockTransport(handler)
        client = OpenMetadataMCPClient("http://mock/mcp", token="bad")

        original_async_client = httpx.AsyncClient

        class PatchedClient(httpx.AsyncClient):
            def __init__(self, *args, **kwargs):
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        httpx.AsyncClient = PatchedClient
        try:
            with pytest.raises(MCPAuthError):
                await client.list_tools()
        finally:
            httpx.AsyncClient = original_async_client

    asyncio.run(_run())
