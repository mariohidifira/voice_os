import json
from uuid import uuid4

import jwt
import pytest
from voiceos_api.config import Settings
from voiceos_api.livekit_sessions import LiveKitSessions


@pytest.mark.asyncio
async def test_dev_session_token_contains_room_and_publish_grants() -> None:
    settings = Settings(livekit_url="wss://example.invalid", livekit_api_key="dev-key", livekit_api_secret="dev-secret")
    call_id, agent_id = uuid4(), uuid4()
    result = await LiveKitSessions(settings).provision(
        call_id=call_id,
        agent_id=agent_id,
        version="draft",
        variables={"customer": "42"},
        end_user={"name": "Mario"},
    )
    claims = jwt.decode(result["token"], "dev-secret", algorithms=["HS256"], audience=None, options={"verify_aud": False})
    assert result["room_name"] == f"voiceos_{call_id}"
    assert claims["video"]["room"] == result["room_name"]
    assert claims["video"]["roomJoin"] is True
    assert claims["video"]["canPublish"] is True
    assert claims["video"]["canSubscribe"] is True
    assert json.loads(claims["metadata"])["call_id"] == str(call_id)


@pytest.mark.asyncio
async def test_production_session_creates_room_and_closes_client(monkeypatch: pytest.MonkeyPatch) -> None:
    class Rooms:
        async def create_room(self, request: object) -> None:
            self.request = request

    class Client:
        def __init__(self, **_: object) -> None:
            self.room = Rooms()
            self.closed = False

        async def aclose(self) -> None:
            self.closed = True

    clients: list[Client] = []

    def make_client(**kwargs: object) -> Client:
        client = Client(**kwargs)
        clients.append(client)
        return client

    from voiceos_api import livekit_sessions

    monkeypatch.setattr(livekit_sessions.livekit_api, "LiveKitAPI", make_client)
    settings = Settings(livekit_url="wss://voiceos.livekit.cloud", livekit_api_key="dev-key", livekit_api_secret="dev-secret")
    result = await LiveKitSessions(settings).provision(
        call_id=uuid4(), agent_id=uuid4(), version="current", variables={}, end_user=None
    )
    assert result["room_name"].startswith("voiceos_")
    assert clients[0].closed is True
