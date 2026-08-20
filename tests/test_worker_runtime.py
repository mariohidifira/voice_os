from uuid import uuid4

import httpx
import pytest
from voiceos_voice.api_client import MemoryRuntimeCache, WorkerAPI
from voiceos_voice.contracts import LLMResponse
from voiceos_voice.providers import MockLLM, MockTTS
from voiceos_voice.runtime import RuntimeSession


@pytest.mark.asyncio
async def test_runtime_session_loads_versioned_config_persists_turns_and_finishes() -> None:
    tenant_id, agent_id, version_id, tool_id, call_id = (uuid4() for _ in range(5))
    requests: list[tuple[str, dict[str, object]]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = __import__("json").loads(request.content or b"{}")
        requests.append((request.url.path, body))
        if request.url.path.endswith("/runtime"):
            return httpx.Response(
                200,
                json={
                    "tenant_id": str(tenant_id),
                    "agent_id": str(agent_id),
                    "version_id": str(version_id),
                    "system_prompt": "Atenda bem.",
                    "variables": {"origin": "runtime"},
                    "tools": [
                        {
                            "id": str(tool_id),
                            "name": "lookup",
                            "parameters_schema": {"type": "object", "properties": {}},
                        }
                    ],
                    "knowledge_base_id": None,
                },
            )
        if request.url.path == "/internal/calls":
            assert body["agent_version_id"] == str(version_id)
            return httpx.Response(201, json={"id": str(call_id)})
        if request.url.path.endswith("/turns"):
            return httpx.Response(200, json={"accepted": len(body["turns"])})
        if request.url.path.endswith("/events"):
            return httpx.Response(200, json={"accepted": len(body["events"])})
        if request.url.path.endswith(str(call_id)):
            return httpx.Response(200, json={"id": str(call_id), **body})
        return httpx.Response(404)

    api = WorkerAPI("http://api:8000", "internal", MemoryRuntimeCache(), httpx.MockTransport(handler))
    runtime = await RuntimeSession.create(
        api,
        agent_id,
        MockLLM([LLMResponse(text="Resposta")]),
        MockLLM(),
        MockTTS(),
        MockTTS(),
        variables={"request": "value"},
    )
    text, audio = await runtime.turn("Pergunta")
    finished = await runtime.finish("resolved")

    assert text == "Resposta" and audio
    assert runtime.voice.variables == {"origin": "runtime", "request": "value"}
    assert finished["status"] == "completed"
    assert [path for path, _ in requests].count(f"/internal/calls/{call_id}/turns") == 1
    patches = [body for path, body in requests if path == f"/internal/calls/{call_id}"]
    assert patches[0]["status"] == "in_progress"
    assert patches[-1]["end_reason"] == "resolved"
