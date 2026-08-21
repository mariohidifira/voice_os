import asyncio
import json
from typing import Any, Protocol
from uuid import UUID

import httpx
from redis.asyncio import Redis


class RuntimeCache(Protocol):
    async def get(self, key: str) -> dict[str, Any] | None: ...

    async def set(self, key: str, value: dict[str, Any], ttl_s: int) -> None: ...

    async def delete(self, key: str) -> None: ...


class RedisRuntimeCache:
    def __init__(self, url: str) -> None:
        self.client = Redis.from_url(url, decode_responses=True)

    async def get(self, key: str) -> dict[str, Any] | None:
        value = await self.client.get(key)
        return json.loads(value) if value else None

    async def set(self, key: str, value: dict[str, Any], ttl_s: int) -> None:
        await self.client.set(key, json.dumps(value, default=str), ex=ttl_s)

    async def delete(self, key: str) -> None:
        await self.client.delete(key)


class MemoryRuntimeCache:
    def __init__(self) -> None:
        self.values: dict[str, dict[str, Any]] = {}

    async def get(self, key: str) -> dict[str, Any] | None:
        return self.values.get(key)

    async def set(self, key: str, value: dict[str, Any], ttl_s: int) -> None:
        self.values[key] = value

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)


class WorkerAPI:
    def __init__(self, base_url: str, internal_token: str, cache: RuntimeCache, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-Internal-Token": internal_token}
        self.cache, self.transport = cache, transport

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        error: Exception | None = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(transport=self.transport, timeout=8) as client:
                    response = await client.request(method, f"{self.base_url}{path}", headers=self.headers, **kwargs)
                    response.raise_for_status()
                    return dict(response.json()) if response.content else {}
            except (httpx.HTTPError, ValueError) as exc:
                error = exc
                if attempt < 2:
                    await asyncio.sleep(0.1 * (attempt + 1))
        raise RuntimeError(f"VoiceOS API unavailable after 3 attempts: {error}") from error

    async def runtime(self, agent_id: UUID, version: str = "current") -> dict[str, Any]:
        key = f"runtime:{agent_id}:{version}"
        cached = await self.cache.get(key)
        if cached:
            return cached
        runtime = await self._request("GET", f"/internal/agents/{agent_id}/runtime", params={"version": version})
        await self.cache.set(key, runtime, 60)
        return runtime

    async def create_call(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/internal/calls", json=payload)

    async def update_call(self, call_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PATCH", f"/internal/calls/{call_id}", json=payload)

    async def append_events(self, call_id: UUID, events: list[dict[str, Any]]) -> int:
        result = await self._request("POST", f"/internal/calls/{call_id}/events", json={"events": events})
        return int(result["accepted"])

    async def append_turns(self, call_id: UUID, turns: list[dict[str, Any]]) -> int:
        result = await self._request("POST", f"/internal/calls/{call_id}/turns", json={"turns": turns})
        return int(result["accepted"])

    async def execute_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/internal/tools/execute", json=payload)

    async def postprocess_call(self, call_id: UUID) -> bool:
        result = await self._request("POST", f"/internal/calls/{call_id}/postprocess")
        return bool(result.get("queued"))

    async def query_knowledge(
        self, knowledge_base_id: UUID, query: str, *, top_k: int, min_score: float
    ) -> list[dict[str, Any]]:
        result = await self._request(
            "POST",
            "/internal/rag/query",
            json={
                "knowledge_base_id": str(knowledge_base_id),
                "query": query,
                "top_k": top_k,
                "min_score": min_score,
            },
        )
        data = result.get("data", [])
        return [dict(item) for item in data] if isinstance(data, list) else []
