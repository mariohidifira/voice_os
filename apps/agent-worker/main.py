import asyncio
import contextlib
import signal
from dataclasses import dataclass

import uvicorn
from fastapi import FastAPI


@dataclass
class WorkerState:
    active_rooms: int = 0
    draining: bool = False


state = WorkerState()
health = FastAPI()


@health.get("/health")
async def healthcheck() -> dict[str, object]:
    return {"status": "ok", "service": "agent-worker", "active_rooms": state.active_rooms, "draining": state.draining}


async def main() -> None:
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)
    server = uvicorn.Server(uvicorn.Config(health, host="0.0.0.0", port=8081, log_level="info"))
    task = asyncio.create_task(server.serve())
    await stop.wait()
    state.draining = True
    while state.active_rooms:
        await asyncio.sleep(1)
    server.should_exit = True
    await task


if __name__ == "__main__":
    asyncio.run(main())

