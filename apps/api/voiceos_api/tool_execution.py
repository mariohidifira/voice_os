import asyncio
import base64
import hashlib
import hmac
import ipaddress
import json
import re
import socket
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from jsonschema import ValidationError, validate

from .config import Settings, get_settings


def _lookup(path: str, context: dict[str, Any]) -> Any:
    value: Any = context
    for part in path.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return value


def _render(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: _render(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [_render(item, context) for item in value]
    if not isinstance(value, str):
        return value
    exact = re.fullmatch(r"{{\s*([^}]+)\s*}}", value)
    if exact:
        return _lookup(exact.group(1).strip(), context)
    return re.sub(
        r"{{\s*([^}]+)\s*}}",
        lambda match: str(_lookup(match.group(1).strip(), context) or ""),
        value,
    )


def _json_path(data: Any, path: str) -> Any:
    if not path.startswith("$."):
        return None
    return _lookup(path[2:], data)


async def _safe_url(url: str, settings: Settings, *, mcp: bool = False) -> bool:
    parsed = urlparse(url)
    if (
        parsed.scheme
        not in ({"http", "https"} if settings.app_env in {"dev", "test"} else {"https"})
        or not parsed.hostname
    ):
        return False
    if settings.app_env in {"dev", "test"}:
        return True
    allowed_hosts = {host.strip().lower() for host in settings.mcp_allowed_hosts.split(",") if host.strip()}
    if mcp and allowed_hosts and parsed.hostname.lower() not in allowed_hosts:
        return False
    try:
        addresses = await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, parsed.port or 443)
    except OSError:
        return False
    return mcp and settings.mcp_allow_private_network or all(
        ipaddress.ip_address(item[4][0]).is_global for item in addresses
    )


class ToolExecutor:
    def __init__(
        self, transport: httpx.AsyncBaseTransport | None = None, settings: Settings | None = None
    ) -> None:
        self.transport, self.settings = transport, settings or get_settings()

    async def execute(
        self, tool: dict[str, Any], arguments: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            validate(arguments, tool["parameters_schema"])
        except ValidationError as exc:
            return {"error": "invalid_arguments", "details": exc.message}
        if tool["type"] == "mcp":
            return await self._execute_mcp(tool, arguments, context)
        if tool["type"] != "webhook" or not tool.get("webhook"):
            return {"error": "unsupported_tool", "message": "Native tool executes in agent-worker"}
        webhook = tool["webhook"]
        render_context = {
            **arguments,
            "var": context.get("session_variables", {}),
            "end_user": context.get("end_user", {}),
            "call": context.get("call", {}),
        }
        url = _render(webhook["url"], render_context)
        if not isinstance(url, str) or not await _safe_url(url, self.settings):
            return {"error": "invalid_url", "message": "Webhook URL must use HTTPS"}
        headers = _render(webhook.get("headers", {}), render_context)
        headers.update(
            {
                "X-VoiceOS-Call-Id": str(context.get("call", {}).get("id", "")),
                "X-VoiceOS-Tenant-Id": str(context.get("tenant_id", "")),
                "X-VoiceOS-Agent-Id": str(context.get("call", {}).get("agent_id", "")),
            }
        )
        body = _render(webhook.get("body_template"), render_context)
        auth = webhook.get("auth") or {"type": "none"}
        secret = context.get("secret")
        auth_type = auth.get("type", "none")
        if auth_type != "none" and not secret:
            return {
                "error": "secret_unavailable",
                "message": "Configured authentication secret could not be resolved",
            }
        if auth_type == "bearer":
            headers["Authorization"] = f"Bearer {secret}"
        elif auth_type == "basic":
            headers["Authorization"] = "Basic " + base64.b64encode(str(secret).encode()).decode()
        elif auth_type == "header":
            headers[auth.get("name", "X-API-Key")] = str(secret)
        elif auth_type == "hmac":
            payload = (
                json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()
                if body is not None
                else b""
            )
            algorithm = auth.get("algorithm", "sha256")
            if algorithm not in {"sha256", "sha512"}:
                return {"error": "invalid_auth", "message": "Unsupported HMAC algorithm"}
            headers[auth.get("header", "X-Signature")] = hmac.new(
                str(secret).encode(), payload, getattr(hashlib, algorithm)
            ).hexdigest()
        elif auth_type != "none":
            return {"error": "invalid_auth", "message": "Unsupported authentication type"}
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                transport=self.transport, timeout=webhook.get("timeout_ms", 8000) / 1000
            ) as client:
                response = await client.request(
                    webhook.get("method", "POST"),
                    url,
                    headers=headers,
                    json=body if body is not None else None,
                )
        except httpx.TimeoutException:
            return {"error": "timeout", "message": "Webhook timed out"}
        except httpx.RequestError as exc:
            return {
                "error": "connection_error",
                "message": "Webhook connection failed",
                "details": type(exc).__name__,
            }
        latency_ms = round((time.perf_counter() - started) * 1000)
        raw = response.text[:20_000]
        if not response.is_success:
            llm_result: Any = {"error": f"http_{response.status_code}", "message": raw[:200]}
        else:
            try:
                parsed = response.json()
            except json.JSONDecodeError:
                parsed = raw
            mapping = webhook.get("response_mapping")
            llm_result = (
                {key: _json_path(parsed, path) for key, path in mapping.items()}
                if mapping and isinstance(parsed, dict)
                else parsed
            )
            if isinstance(llm_result, str):
                llm_result = llm_result[:2000]
        return {
            "request": {
                "method": webhook.get("method", "POST"),
                "url": url,
                "headers": headers,
                "body": body,
            },
            "status": response.status_code,
            "latency_ms": latency_ms,
            "raw_body": raw,
            "mapped_body": llm_result,
            "result": llm_result,
            "truncated": len(response.text) > 20_000,
        }

    def _mcp_headers(self, config: dict[str, Any], secret: str | None) -> dict[str, str] | None:
        auth = config.get("auth") or {"type": "none"}
        auth_type = auth.get("type", "none")
        if auth_type != "none" and not secret:
            return None
        if auth_type == "none":
            return {}
        if auth_type == "bearer":
            return {"Authorization": f"Bearer {secret}"}
        if auth_type == "header":
            return {str(auth.get("name", "X-API-Key")): str(secret)}
        return None

    async def _mcp_request(
        self, config: dict[str, Any], method: str, params: dict[str, Any], secret: str | None
    ) -> dict[str, Any]:
        if not self.settings.mcp_enabled:
            return {"error": "mcp_disabled", "message": "MCP is disabled by deployment policy"}
        endpoint = config.get("endpoint")
        if not isinstance(endpoint, str) or not await _safe_url(endpoint, self.settings, mcp=True):
            return {"error": "invalid_url", "message": "MCP endpoint must use an allowed HTTPS host"}
        headers = self._mcp_headers(config, secret)
        if headers is None:
            return {"error": "secret_unavailable", "message": "MCP authentication secret could not be resolved"}
        headers.update({"Accept": "application/json, text/event-stream", "Content-Type": "application/json"})
        payload = {"jsonrpc": "2.0", "id": "voiceos", "method": method, "params": params}
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=config.get("timeout_ms", 8000) / 1000) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
        except httpx.TimeoutException:
            return {"error": "timeout", "message": "MCP server timed out"}
        except httpx.RequestError as exc:
            return {"error": "connection_error", "message": "MCP connection failed", "details": type(exc).__name__}
        latency_ms = round((time.perf_counter() - started) * 1000)
        raw = response.text[:20_000]
        if not response.is_success:
            return {"error": f"http_{response.status_code}", "message": raw[:200], "latency_ms": latency_ms}
        try:
            data = response.json()
        except json.JSONDecodeError:
            # Streamable HTTP servers may return one JSON-RPC event as SSE.
            event = next((line[5:].strip() for line in raw.splitlines() if line.startswith("data:")), None)
            try:
                data = json.loads(event) if event else None
            except json.JSONDecodeError:
                data = None
        if not isinstance(data, dict):
            return {"error": "invalid_mcp_response", "message": "MCP response was not JSON-RPC", "latency_ms": latency_ms}
        if data.get("error"):
            return {"error": "mcp_error", "message": str(data["error"].get("message", "MCP request failed")), "latency_ms": latency_ms}
        return {"result": data.get("result"), "status": response.status_code, "latency_ms": latency_ms, "raw_body": raw}

    async def discover_mcp(self, config: dict[str, Any], secret: str | None = None) -> dict[str, Any]:
        result = await self._mcp_request(config, "tools/list", {}, secret)
        tools = (result.get("result") or {}).get("tools") if isinstance(result.get("result"), dict) else None
        if tools is None and "error" not in result:
            return {"error": "invalid_mcp_response", "message": "MCP tools/list response has no tools"}
        if tools is not None:
            result["tools"] = [
                {"name": item.get("name"), "description": item.get("description", ""), "input_schema": item.get("inputSchema", {})}
                for item in tools if isinstance(item, dict) and item.get("name")
            ]
        return result

    async def _execute_mcp(self, tool: dict[str, Any], arguments: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        config = tool.get("mcp") or {}
        if not config.get("enabled") or not config.get("approved"):
            return {"error": "mcp_not_approved", "message": "MCP tool is not approved for runtime use"}
        operation = config.get("operation")
        if not operation:
            return {"error": "invalid_mcp_config", "message": "MCP operation is required"}
        result = await self._mcp_request(config, "tools/call", {"name": operation, "arguments": arguments}, context.get("secret"))
        raw_result = result.get("result")
        if isinstance(raw_result, dict) and isinstance(raw_result.get("content"), list):
            text_parts = [str(item.get("text", "")) for item in raw_result["content"] if isinstance(item, dict) and item.get("type") == "text"]
            result["result"] = {"content": text_parts, "is_error": bool(raw_result.get("isError"))}
        return result


def get_tool_executor() -> ToolExecutor:
    return ToolExecutor(settings=get_settings())
