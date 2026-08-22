from typing import Any, cast
from uuid import uuid4

import httpx
import pytest
from livekit.agents import (
    AgentSession,
    ConversationItemAddedEvent,
    UserInputTranscribedEvent,
    UserStateChangedEvent,
)
from livekit.agents.llm import ChatMessage, RawFunctionTool
from voiceos_voice.api_client import MemoryRuntimeCache, WorkerAPI
from voiceos_voice.livekit_worker import (
    LiveKitCallBridge,
    SessionGuards,
    dynamic_tools,
    room_metadata,
)


def test_room_metadata_parses_dispatch_contract() -> None:
    assert room_metadata('{"agent_id":"abc","channel":"web","variables":{"lead":"42"}}') == {
        "agent_id": "abc",
        "channel": "web",
        "variables": {"lead": "42"},
    }


@pytest.mark.parametrize("raw", ["[]", "not-json"])
def test_room_metadata_rejects_invalid_dispatch_contract(raw: str) -> None:
    with pytest.raises(ValueError, match="metadata"):
        room_metadata(raw)


@pytest.mark.asyncio
async def test_call_bridge_persists_final_transcript_and_closes_call() -> None:
    call_id = uuid4()
    requests: list[tuple[str, dict[str, Any]]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = __import__("json").loads(request.content or b"{}")
        requests.append((request.url.path, body))
        if request.url.path.endswith(("/events", "/turns")):
            key = "events" if request.url.path.endswith("/events") else "turns"
            return httpx.Response(200, json={"accepted": len(body[key])})
        return httpx.Response(200, json={"id": str(call_id), **body})

    api = WorkerAPI("http://api", "internal", MemoryRuntimeCache(), httpx.MockTransport(handler))
    bridge = LiveKitCallBridge(api, call_id, {"lead": "42"})
    await bridge.user_transcript(UserInputTranscribedEvent(transcript="Olá", is_final=True))
    await bridge.close()

    turn_payload = next(body for path, body in requests if path.endswith("/turns"))
    patch_payload = next(body for path, body in requests if path == f"/internal/calls/{call_id}")
    assert turn_payload["turns"][0]["text"] == "Olá"
    assert patch_payload["status"] == "completed"
    assert patch_payload["variables"] == {"lead": "42"}


@pytest.mark.asyncio
async def test_call_bridge_uses_livekit_end_to_end_voice_latency() -> None:
    call_id = uuid4()
    requests: list[tuple[str, dict[str, Any]]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = __import__("json").loads(request.content or b"{}")
        requests.append((request.url.path, body))
        if request.url.path.endswith("/turns"):
            return httpx.Response(200, json={"accepted": 1})
        return httpx.Response(200, json={"id": str(call_id), **body})

    api = WorkerAPI(
        "http://api", "internal", MemoryRuntimeCache(), httpx.MockTransport(handler)
    )
    bridge = LiveKitCallBridge(api, call_id, {})
    item = ChatMessage(
        role="assistant", content=["Resposta"], metrics={"e2e_latency": 0.875}
    )
    await bridge.conversation_item(ConversationItemAddedEvent(item=item))
    await bridge.close()

    patch_payload = next(
        body for path, body in requests if path == f"/internal/calls/{call_id}"
    )
    assert patch_payload["latency"]["ttfb_samples_ms"] == [875]
    assert patch_payload["latency"]["ttfb_p50_ms"] == 875


@pytest.mark.asyncio
async def test_dynamic_tools_mutate_variables_and_proxy_remote_execution() -> None:
    call_id, local_id, remote_id = uuid4(), uuid4(), uuid4()
    executed: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = __import__("json").loads(request.content or b"{}")
        if request.url.path.endswith("/events"):
            return httpx.Response(200, json={"accepted": 1})
        executed.append(body)
        return httpx.Response(200, json={"result": "ok"})

    api = WorkerAPI("http://api", "internal", MemoryRuntimeCache(), httpx.MockTransport(handler))
    variables: dict[str, Any] = {}
    bridge = LiveKitCallBridge(api, call_id, variables)
    tools = dynamic_tools(
        api,
        call_id,
        [
            {"id": str(local_id), "name": "set_variable", "parameters_schema": {"type": "object"}},
            {"id": str(remote_id), "name": "lookup", "parameters_schema": {"type": "object"}},
        ],
        variables,
        {},
        {},
        bridge,
    )
    local = cast(RawFunctionTool[..., Any], tools[0])
    remote = cast(RawFunctionTool[..., Any], tools[1])
    assert (await local(raw_arguments={"name": "cpf", "value": "123"}))["status"] == "ok"
    assert await remote(raw_arguments={"query": "42"}) == {"result": "ok"}
    assert variables == {"cpf": "123"}
    assert executed[0]["tool_id"] == str(remote_id)
    assert executed[0]["session_variables"] == variables


@pytest.mark.asyncio
async def test_session_guards_prompt_once_then_end_after_second_silence() -> None:
    class Speech:
        async def wait_for_playout(self) -> None:
            return None

    class Session:
        def __init__(self) -> None:
            self.spoken: list[str] = []
            self.closed = False

        def say(self, text: str, **kwargs: Any) -> Speech:
            self.spoken.append(text)
            return Speech()

        def shutdown(self, *, drain: bool = True) -> None:
            self.closed = True

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"accepted": 1})

    api = WorkerAPI("http://api", "internal", MemoryRuntimeCache(), httpx.MockTransport(handler))
    bridge = LiveKitCallBridge(api, uuid4(), {})
    raw_session = Session()
    session = cast(AgentSession[Any], raw_session)
    guards = SessionGuards(session, bridge, "Você ainda está aí?", 900)
    away = UserStateChangedEvent(old_state="listening", new_state="away")

    await guards.user_state(away)
    assert raw_session.spoken == ["Você ainda está aí?"] and raw_session.closed is False
    await guards.user_state(away)
    assert raw_session.closed is True
    assert bridge.end_reason == "silence"
