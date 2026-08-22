from uuid import uuid4

import pytest
from voiceos_api.config import get_settings
from voiceos_api.idempotency import RedisIdempotencyStore


@pytest.mark.asyncio
async def test_redis_idempotency_reserves_replays_rejects_and_releases() -> None:
    tenant_id = uuid4()
    operation = "test:outbound"
    key = f"pytest-{uuid4()}"
    store = RedisIdempotencyStore(get_settings().redis_url)

    assert await store.reserve(tenant_id, operation, key, "fingerprint-a") is None
    assert await store.reserve(tenant_id, operation, key, "fingerprint-a") == {
        "_pending": True
    }
    await store.complete(
        tenant_id,
        operation,
        key,
        "fingerprint-a",
        {"call_id": "call-1"},
    )
    assert await store.reserve(tenant_id, operation, key, "fingerprint-a") == {
        "call_id": "call-1"
    }
    assert await store.reserve(tenant_id, operation, key, "fingerprint-b") == {
        "_conflict": True
    }

    await store.release(tenant_id, operation, key)
    assert await store.reserve(tenant_id, operation, key, "fingerprint-b") is None
    await store.release(tenant_id, operation, key)
