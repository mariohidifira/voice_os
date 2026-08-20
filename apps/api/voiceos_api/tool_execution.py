import json
import re
import time
from typing import Any

import httpx
from jsonschema import ValidationError, validate


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
    return re.sub(r"{{\s*([^}]+)\s*}}", lambda match: str(_lookup(match.group(1).strip(), context) or ""), value)


def _json_path(data: Any, path: str) -> Any:
    if not path.startswith("$."):
        return None
    return _lookup(path[2:], data)


class ToolExecutor:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.transport = transport

    async def execute(self, tool: dict[str, Any], arguments: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        try:
            validate(arguments, tool["parameters_schema"])
        except ValidationError as exc:
            return {"error": "invalid_arguments", "details": exc.message}
        if tool["type"] != "webhook" or not tool.get("webhook"):
            return {"error": "unsupported_tool", "message": "Native tool executes in agent-worker"}
        webhook = tool["webhook"]
        auth = webhook.get("auth") or {"type": "none"}
        if auth.get("type", "none") != "none":
            return {"error": "secret_unavailable", "message": "Configured authentication secret could not be resolved"}
        render_context = {**arguments, "var": context.get("session_variables", {}), "end_user": context.get("end_user", {}), "call": context.get("call", {})}
        url = _render(webhook["url"], render_context)
        headers = _render(webhook.get("headers", {}), render_context)
        headers.update({"X-VoiceOS-Call-Id": str(context.get("call", {}).get("id", "")), "X-VoiceOS-Tenant-Id": str(context.get("tenant_id", "")), "X-VoiceOS-Agent-Id": str(context.get("call", {}).get("agent_id", ""))})
        body = _render(webhook.get("body_template"), render_context)
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=webhook.get("timeout_ms", 8000) / 1000) as client:
                response = await client.request(webhook.get("method", "POST"), url, headers=headers, json=body if body is not None else None)
        except httpx.TimeoutException:
            return {"error": "timeout", "message": "Webhook timed out"}
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
            llm_result = {key: _json_path(parsed, path) for key, path in mapping.items()} if mapping and isinstance(parsed, dict) else parsed
            if isinstance(llm_result, str):
                llm_result = llm_result[:2000]
        return {"request": {"method": webhook.get("method", "POST"), "url": url, "headers": headers, "body": body}, "status": response.status_code, "latency_ms": latency_ms, "raw_body": raw, "mapped_body": llm_result, "result": llm_result, "truncated": len(response.text) > 20_000}


def get_tool_executor() -> ToolExecutor:
    return ToolExecutor()
