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
    dial_outbound,
    dynamic_tools,
    room_metadata,
    send_dtmf,
    transfer_phone_call,
)


@pytest.mark.asyncio
async def test_dial_outbound_maps_sip_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    call_id = uuid4()
    patches: list[dict[str, Any]] = []
    sip_requests: list[Any] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = __import__("json").loads(request.content or b"{}")
        patches.append(body)
        return httpx.Response(200, json={"id": str(call_id), **body})

    class Sip:
        async def create_sip_participant(self, request: Any) -> Any:
            sip_requests.append(request)
            return type("Participant", (), {"sip_call_id": "SIP_CALL_1"})()

    class Client:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            self.sip = Sip()

        async def aclose(self) -> None:
            return None

    monkeypatch.setenv("LIVEKIT_URL", "wss://livekit.test")
    monkeypatch.setenv("LIVEKIT_API_KEY", "key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "secret")
    monkeypatch.setenv("LIVEKIT_SIP_TRUNK_ID_OUTBOUND", "ST_OUT")
    monkeypatch.setattr("voiceos_voice.livekit_worker.livekit_api.LiveKitAPI", Client)
    api = WorkerAPI("http://api", "internal", MemoryRuntimeCache(), httpx.MockTransport(handler))

    await dial_outbound(
        api,
        call_id,
        "voiceos_room",
        {"to": "+5511999990001", "from": "+551140008888"},
    )

    assert [patch["status"] for patch in patches] == ["ringing", "in_progress"]
    assert patches[-1]["provider_call_sid"] == "SIP_CALL_1"
    assert sip_requests[0].sip_trunk_id == "ST_OUT"
    assert sip_requests[0].sip_call_to == "+5511999990001"
    assert sip_requests[0].wait_until_answered is True
    assert sip_requests[0].ringing_timeout.seconds == 30


@pytest.mark.asyncio
async def test_dial_outbound_records_provider_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    call_id = uuid4()
    patches: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = __import__("json").loads(request.content or b"{}")
        patches.append(body)
        return httpx.Response(200, json={"id": str(call_id), **body})

    class Sip:
        async def create_sip_participant(self, request: Any) -> Any:
            raise RuntimeError("provider unavailable")

    class Client:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            self.sip = Sip()

        async def aclose(self) -> None:
            return None

    monkeypatch.setenv("LIVEKIT_URL", "wss://livekit.test")
    monkeypatch.setenv("LIVEKIT_API_KEY", "key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "secret")
    monkeypatch.setenv("LIVEKIT_SIP_TRUNK_ID_OUTBOUND", "ST_OUT")
    monkeypatch.setattr("voiceos_voice.livekit_worker.livekit_api.LiveKitAPI", Client)
    api = WorkerAPI("http://api", "internal", MemoryRuntimeCache(), httpx.MockTransport(handler))

    with pytest.raises(RuntimeError, match="provider unavailable"):
        await dial_outbound(
            api,
            call_id,
            "voiceos_room",
            {"to": "+5511999990001", "from": "+551140008888"},
        )

    assert [patch["status"] for patch in patches] == ["ringing", "failed"]
    assert patches[-1]["end_reason"] == "error"


@pytest.mark.asyncio
async def test_dtmf_native_tool_uses_rtc_codes_and_persists_event() -> None:
    call_id, tool_id = uuid4(), uuid4()
    requests: list[tuple[str, dict[str, Any]]] = []
    published: list[tuple[int, str]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = __import__("json").loads(request.content or b"{}")
        requests.append((request.url.path, body))
        return httpx.Response(200, json={"accepted": 1})

    class Participant:
        async def publish_dtmf(self, *, code: int, digit: str) -> None:
            published.append((code, digit))

    api = WorkerAPI("http://api", "internal", MemoryRuntimeCache(), httpx.MockTransport(handler))
    bridge = LiveKitCallBridge(api, call_id, {})
    tools = dynamic_tools(
        api,
        call_id,
        [
            {
                "id": str(tool_id),
                "name": "navegar_ura",
                "native_kind": "dtmf",
                "parameters_schema": {"type": "object"},
            }
        ],
        {},
        {},
        {},
        bridge,
        lambda digits: send_dtmf(Participant(), digits),
    )
    dtmf_tool = cast(RawFunctionTool[..., Any], tools[0])

    result = await dtmf_tool(raw_arguments={"digits": "12#A"})
    invalid = await dtmf_tool(raw_arguments={"digits": "12X"})

    assert result == {"status": "sent", "digits": "12#A"}
    assert invalid["error"] == "invalid_digits"
    assert published == [(1, "1"), (2, "2"), (11, "#"), (12, "A")]
    assert any(body["events"][0]["type"] == "dtmf" for _, body in requests)


@pytest.mark.asyncio
async def test_transfer_phone_call_supports_cold_and_warm(monkeypatch: pytest.MonkeyPatch) -> None:
    transferred: list[Any] = []
    created: list[Any] = []

    class Sip:
        async def transfer_sip_participant(self, request: Any) -> Any:
            transferred.append(request)
            return type("Participant", (), {"participant_identity": "caller"})()

        async def create_sip_participant(self, request: Any) -> Any:
            created.append(request)
            return type("Participant", (), {"participant_identity": "operator"})()

    class Client:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            self.sip = Sip()

        async def aclose(self) -> None:
            return None

    caller = type("Remote", (), {"identity": "caller", "kind": 3})()
    room = type(
        "Room",
        (),
        {"name": "voiceos_room", "remote_participants": {"caller": caller}},
    )()
    monkeypatch.setenv("LIVEKIT_URL", "wss://livekit.test")
    monkeypatch.setenv("LIVEKIT_API_KEY", "key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "secret")
    monkeypatch.setenv("LIVEKIT_SIP_TRUNK_ID_OUTBOUND", "ST_OUT")
    monkeypatch.setattr("voiceos_voice.livekit_worker.livekit_api.LiveKitAPI", Client)

    cold = await transfer_phone_call(
        room,
        {"to": "+551140008888"},
        {"transfer_number": "+551130003000"},
        {"reason": "human", "mode": "cold"},
    )
    warm = await transfer_phone_call(
        room,
        {"to": "+551140008888"},
        {"transfer_number": "+551130003000"},
        {"reason": "human", "mode": "warm"},
    )

    assert cold["status"] == warm["status"] == "transferred"
    assert transferred[0].transfer_to == "tel:+551130003000"
    assert transferred[0].participant_identity == "caller"
    assert created[0].sip_trunk_id == "ST_OUT"
    assert created[0].sip_call_to == "+551130003000"
    assert created[0].sip_number == "+551140008888"


@pytest.mark.asyncio
async def test_transfer_native_tool_summarizes_and_closes() -> None:
    call_id, tool_id = uuid4(), uuid4()
    events: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = __import__("json").loads(request.content or b"{}")
        if request.url.path.endswith("/events"):
            events.append(body["events"][0]["type"])
        return httpx.Response(200, json={"accepted": 1})

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

    async def transfer(arguments: dict[str, Any]) -> dict[str, Any]:
        return {"status": "transferred", "mode": arguments["mode"]}

    api = WorkerAPI("http://api", "internal", MemoryRuntimeCache(), httpx.MockTransport(handler))
    bridge = LiveKitCallBridge(api, call_id, {})
    session = Session()
    tools = dynamic_tools(
        api,
        call_id,
        [
            {
                "id": str(tool_id),
                "name": "encaminhar_humano",
                "native_kind": "transfer_call",
                "parameters_schema": {"type": "object"},
            }
        ],
        {},
        {},
        {"session": cast(AgentSession[Any], session)},
        bridge,
        transfer_handler=transfer,
    )
    transfer_tool = cast(RawFunctionTool[..., Any], tools[0])

    result = await transfer_tool(
        raw_arguments={"reason": "cliente irritado", "mode": "warm", "summary": "Resumo."}
    )

    assert result["status"] == "transferred"
    assert events == ["transfer.requested", "transfer.completed"]
    assert session.spoken == ["Resumo."]
    assert session.closed is True
    assert bridge.end_reason == "transferred"


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
