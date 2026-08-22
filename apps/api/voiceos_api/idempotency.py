import json
from typing import Any, Protocol
from uuid import UUID

from redis.asyncio import Redis

from .config import get_settings


class IdempotencyStore(Protocol):
    async def reserve(
        self, tenant_id: UUID, operation: str, key: str, fingerprint: str
    ) -> dict[str, Any] | None: ...
    async def complete(
        self,
        tenant_id: UUID,
        operation: str,
        key: str,
        fingerprint: str,
        response: dict[str, Any],
    ) -> None: ...
    async def release(self, tenant_id: UUID, operation: str, key: str) -> None: ...


class RedisIdempotencyStore:
    def __init__(self, url: str) -> None:
        self.url = url

    @staticmethod
    def _key(tenant_id: UUID, operation: str, key: str) -> str:
        return f"idempotency:{tenant_id}:{operation}:{key}"

    async def reserve(
        self, tenant_id: UUID, operation: str, key: str, fingerprint: str
    ) -> dict[str, Any] | None:
        redis = Redis.from_url(self.url, decode_responses=True)
        cache_key = self._key(tenant_id, operation, key)
        pending = json.dumps({"fingerprint": fingerprint, "pending": True})
        try:
            if await redis.set(cache_key, pending, nx=True, ex=86400):
                return None
            value = await redis.get(cache_key)
        finally:
            await redis.aclose()
        if not value:
            return {"_pending": True}
        record = dict(json.loads(value))
        if record.get("fingerprint") != fingerprint:
            return {"_conflict": True}
        if record.get("pending"):
            return {"_pending": True}
        return dict(record["response"])

    async def complete(
        self,
        tenant_id: UUID,
        operation: str,
        key: str,
        fingerprint: str,
        response: dict[str, Any],
    ) -> None:
        redis = Redis.from_url(self.url, decode_responses=True)
        try:
            await redis.set(
                self._key(tenant_id, operation, key),
                json.dumps(
                    {"fingerprint": fingerprint, "response": response},
                    separators=(",", ":"),
                ),
                xx=True,
                ex=86400,
            )
        finally:
            await redis.aclose()

    async def release(self, tenant_id: UUID, operation: str, key: str) -> None:
        redis = Redis.from_url(self.url, decode_responses=True)
        try:
            await redis.delete(self._key(tenant_id, operation, key))
        finally:
            await redis.aclose()


class MemoryIdempotencyStore:
    def __init__(self) -> None:
        self.values: dict[tuple[UUID, str, str], dict[str, Any]] = {}

    async def reserve(
        self, tenant_id: UUID, operation: str, key: str, fingerprint: str
    ) -> dict[str, Any] | None:
        cache_key = (tenant_id, operation, key)
        if cache_key not in self.values:
            self.values[cache_key] = {"fingerprint": fingerprint, "pending": True}
            return None
        record = self.values[cache_key]
        if record["fingerprint"] != fingerprint:
            return {"_conflict": True}
        return {"_pending": True} if record.get("pending") else dict(record["response"])

    async def complete(
        self,
        tenant_id: UUID,
        operation: str,
        key: str,
        fingerprint: str,
        response: dict[str, Any],
    ) -> None:
        self.values[(tenant_id, operation, key)] = {
            "fingerprint": fingerprint,
            "response": dict(response),
        }

    async def release(self, tenant_id: UUID, operation: str, key: str) -> None:
        self.values.pop((tenant_id, operation, key), None)


_memory_idempotency = MemoryIdempotencyStore()


def get_idempotency_store() -> IdempotencyStore:
    settings = get_settings()
    if settings.app_env in {"dev", "test"}:
        return _memory_idempotency
    return RedisIdempotencyStore(settings.redis_url)
