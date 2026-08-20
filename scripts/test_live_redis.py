import asyncio
from uuid import UUID

from voiceos_api.live import RedisEventBus


async def main() -> None:
    tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    call_id = UUID("00000000-0000-0000-0000-000000000099")
    bus = RedisEventBus("redis://localhost:6379/0")
    received = asyncio.Event()

    async def subscriber() -> None:
        async for event in bus.subscribe(tenant_id, call_id):
            if event.get("type") == "turn.user":
                assert event["turn"]["text"] == "Olá"
                received.set()
                return

    task = asyncio.create_task(subscriber())
    await asyncio.sleep(0.1)
    await bus.publish(tenant_id, call_id, {"type": "turn.user", "turn": {"text": "Olá"}})
    await asyncio.wait_for(received.wait(), timeout=3)
    await task
    print("Redis live-event acceptance passed")


if __name__ == "__main__":
    asyncio.run(main())
