import json

import httpx
import pytest
from voiceos_api.config import Settings
from voiceos_api.tool_execution import ToolExecutor


@pytest.mark.asyncio
async def test_webhook_render_mapping_and_error_contracts() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/orders/42"
        assert request.headers["X-VoiceOS-Call-Id"] == "call-1"
        assert json.loads(request.content) == {"customer": "Mario", "source": "web"}
        return httpx.Response(200, json={"data": {"status": "sent"}})

    tool = {
        "type": "webhook",
        "parameters_schema": {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
        "webhook": {
            "url": "https://example.test/orders/{{id}}",
            "method": "POST",
            "body_template": {"customer": "{{end_user.name}}", "source": "{{var.source}}"},
            "response_mapping": {"status": "$.data.status"},
        },
    }
    executor = ToolExecutor(httpx.MockTransport(handler))
    result = await executor.execute(
        tool,
        {"id": "42"},
        {
            "tenant_id": "tenant-1",
            "session_variables": {"source": "web"},
            "end_user": {"name": "Mario"},
            "call": {"id": "call-1", "agent_id": "agent-1"},
        },
    )
    assert result["result"] == {"status": "sent"}
    invalid = await executor.execute(tool, {}, {})
    assert invalid["error"] == "invalid_arguments"


@pytest.mark.asyncio
async def test_webhook_http_error_is_safe() -> None:
    executor = ToolExecutor(
        httpx.MockTransport(lambda request: httpx.Response(503, text="unavailable details"))
    )
    tool = {
        "type": "webhook",
        "parameters_schema": {"type": "object"},
        "webhook": {"url": "https://example.test", "auth": {"type": "none"}},
    }
    result = await executor.execute(tool, {}, {"call": {}})
    assert result["result"] == {"error": "http_503", "message": "unavailable details"}


@pytest.mark.asyncio
async def test_webhook_bearer_secret_is_applied() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer decrypted-token"
        return httpx.Response(200, json={"ok": True})

    executor = ToolExecutor(httpx.MockTransport(handler))
    tool = {
        "type": "webhook",
        "parameters_schema": {"type": "object"},
        "webhook": {
            "url": "https://example.test",
            "auth": {"type": "bearer", "secret_id": "ignored"},
        },
    }
    result = await executor.execute(tool, {}, {"call": {}, "secret": "decrypted-token"})
    assert result["result"] == {"ok": True}


@pytest.mark.asyncio
async def test_webhook_connection_error_is_recoverable() -> None:
    async def fail_connection(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    executor = ToolExecutor(httpx.MockTransport(fail_connection))
    tool = {
        "type": "webhook",
        "parameters_schema": {"type": "object"},
        "webhook": {"url": "https://example.test", "auth": {"type": "none"}},
    }
    result = await executor.execute(tool, {}, {"call": {}})
    assert result == {
        "error": "connection_error",
        "message": "Webhook connection failed",
        "details": "ConnectError",
    }


@pytest.mark.asyncio
async def test_mcp_discovery_and_call_require_approval() -> None:
    seen: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen.append(payload)
        if payload["method"] == "tools/list":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": "voiceos", "result": {"tools": [{"name": "lookup_order", "description": "Lookup", "inputSchema": {"type": "object"}}]}})
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": "voiceos", "result": {"content": [{"type": "text", "text": "Order found"}]}})

    executor = ToolExecutor(
        httpx.MockTransport(handler), Settings(app_env="test", mcp_enabled=True)
    )
    config = {"endpoint": "https://mcp.example.test", "transport": "streamable_http"}
    discovered = await executor.discover_mcp(config)
    assert discovered["tools"][0]["name"] == "lookup_order"
    tool = {
        "type": "mcp",
        "parameters_schema": {"type": "object"},
        "mcp": {**config, "operation": "lookup_order", "enabled": True, "approved": True},
    }
    result = await executor.execute(tool, {"id": "42"}, {})
    assert result["result"] == {"content": ["Order found"], "is_error": False}
    assert seen[-1]["method"] == "tools/call"


@pytest.mark.asyncio
async def test_mcp_is_blocked_until_approved() -> None:
    executor = ToolExecutor(settings=Settings(app_env="test", mcp_enabled=True))
    result = await executor.execute(
        {"type": "mcp", "parameters_schema": {"type": "object"}, "mcp": {"enabled": True}}, {}, {}
    )
    assert result["error"] == "mcp_not_approved"
