import json
from uuid import UUID

import pytest
from voiceos_api.live import channel_name, encode_sse


@pytest.mark.asyncio
async def test_redis_event_bus_publish_and_subscribe(monkeypatch: pytest.MonkeyPatch) -> None:
    from voiceos_api import live

    class FakePubSub:
        def __init__(self) -> None:
            self.messages = [None, {"data": '{"type":"call.ended"}'}]

        async def subscribe(self, channel: str) -> None:
            self.channel = channel

        async def get_message(self, **_: object) -> dict[str, str] | None:
            return self.messages.pop(0)

        async def unsubscribe(self, channel: str) -> None:
            return None

        async def aclose(self) -> None:
            return None

    class FakeRedis:
        def __init__(self) -> None:
            self.pubsub_instance = FakePubSub()
            self.published: list[tuple[str, str]] = []

        def pubsub(self) -> FakePubSub:
            return self.pubsub_instance

        async def publish(self, channel: str, value: str) -> None:
            self.published.append((channel, value))

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(live.Redis, "from_url", lambda *_args, **_kwargs: FakeRedis())
    tenant_id, call_id = UUID(int=3), UUID(int=4)
    bus = live.RedisEventBus("redis://test")
    await bus.publish(tenant_id, call_id, {"type": "call.started"})
    stream = bus.subscribe(tenant_id, call_id)
    assert await anext(stream) == {"type": "heartbeat"}
    assert await anext(stream) == {"type": "call.ended"}
    await stream.aclose()


def test_tenant_scoped_channel_and_sse_encoding() -> None:
    tenant_id = UUID(int=1)
    call_id = UUID(int=2)
    assert channel_name(tenant_id, call_id) == f"tenant:{tenant_id}:call:{call_id}"
    encoded = encode_sse({"type": "turn.user", "text": "Olá"})
    assert encoded.startswith("event: turn.user\ndata: ")
    assert json.loads(encoded.split("data: ", 1)[1]) == {"type": "turn.user", "text": "Olá"}
