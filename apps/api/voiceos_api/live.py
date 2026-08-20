import json
from collections.abc import AsyncIterator
from typing import Any, Protocol
from uuid import UUID

from redis.asyncio import Redis

from .config import get_settings


class EventBus(Protocol):
    async def publish(self, tenant_id: UUID, call_id: UUID, event: dict[str, Any]) -> None: ...

    def subscribe(self, tenant_id: UUID, call_id: UUID) -> AsyncIterator[dict[str, Any]]: ...


def channel_name(tenant_id: UUID, call_id: UUID) -> str:
    return f"tenant:{tenant_id}:call:{call_id}"


def encode_sse(event: dict[str, Any]) -> str:
    event_type = str(event.get("type", "message"))
    return f"event: {event_type}\ndata: {json.dumps(event, default=str, ensure_ascii=False)}\n\n"


class RedisEventBus:
    def __init__(self, url: str) -> None:
        self.url = url

    async def publish(self, tenant_id: UUID, call_id: UUID, event: dict[str, Any]) -> None:
        client = Redis.from_url(self.url, decode_responses=True)
        try:
            await client.publish(channel_name(tenant_id, call_id), json.dumps(event, default=str, ensure_ascii=False))
        finally:
            await client.aclose()

    async def subscribe(self, tenant_id: UUID, call_id: UUID) -> AsyncIterator[dict[str, Any]]:
        client = Redis.from_url(self.url, decode_responses=True)
        pubsub = client.pubsub()
        try:
            await pubsub.subscribe(channel_name(tenant_id, call_id))
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15)
                if message is None:
                    yield {"type": "heartbeat"}
                    continue
                yield json.loads(message["data"])
        finally:
            await pubsub.unsubscribe(channel_name(tenant_id, call_id))
            await pubsub.aclose()
            await client.aclose()


def get_event_bus() -> EventBus:
    return RedisEventBus(get_settings().redis_url)
