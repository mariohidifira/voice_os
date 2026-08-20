from uuid import uuid4

import httpx
import pytest
from voiceos_voice.api_client import MemoryRuntimeCache, WorkerAPI


@pytest.mark.asyncio
async def test_runtime_is_cached_and_internal_calls_are_persisted() -> None:
    requests: list[str] = []
    agent_id, call_id = uuid4(), uuid4()

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        assert request.headers["X-Internal-Token"] == "internal"
        if request.url.path.endswith("/runtime"):
            return httpx.Response(200, json={"agent_id": str(agent_id), "version_id": str(uuid4()), "tools": []})
        if request.url.path == "/internal/calls":
            return httpx.Response(201, json={"id": str(call_id)})
        if request.url.path.endswith(("/events", "/turns")):
            return httpx.Response(200, json={"accepted": 1})
        return httpx.Response(200, json={"status": "completed"})

    api = WorkerAPI("http://api:8000", "internal", MemoryRuntimeCache(), httpx.MockTransport(handler))
    first = await api.runtime(agent_id)
    second = await api.runtime(agent_id)
    assert first == second
    assert requests.count(f"/internal/agents/{agent_id}/runtime") == 1
    assert (await api.create_call({"tenant_id": str(uuid4()), "agent_id": str(agent_id)}))["id"] == str(call_id)
    assert await api.append_events(call_id, [{"type": "call.started", "payload": {}, "at": "2026-08-20T00:00:00Z"}]) == 1
    assert await api.append_turns(call_id, [{"ordinal": 0, "role": "user", "text": "oi"}]) == 1
    assert (await api.update_call(call_id, {"status": "completed"}))["status"] == "completed"


@pytest.mark.asyncio
async def test_api_retries_three_times_then_fails() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503)

    api = WorkerAPI("http://api:8000", "internal", MemoryRuntimeCache(), httpx.MockTransport(handler))
    with pytest.raises(RuntimeError, match="3 attempts"):
        await api.runtime(uuid4())
    assert attempts == 3
