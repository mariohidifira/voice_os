import asyncio
import logging
import os

import httpx


async def campaign_runner(client: httpx.AsyncClient) -> None:
    response = await client.post("/internal/campaigns/tick")
    response.raise_for_status()
    result = response.json()
    if result.get("claimed"):
        logging.info("campaign_runner: %s", result)


async def run() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.info("VoiceOS worker ready: ingest, QA, billing, exports, WhatsApp and retention jobs")
    api_url = os.getenv("WORKER_API_URL", "http://api:8000")
    token = os.getenv("INTERNAL_API_TOKEN", "dev-internal-token")
    async with httpx.AsyncClient(
        base_url=api_url, headers={"X-Internal-Token": token}, timeout=25
    ) as client:
        while True:
            try:
                await campaign_runner(client)
            except Exception:
                logging.exception("campaign_runner failed; next attempt in 30 seconds")
            await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(run())
