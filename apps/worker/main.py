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


async def billing_meter(client: httpx.AsyncClient) -> None:
    response = await client.post("/internal/billing/tick")
    response.raise_for_status()
    logging.info("billing_meter: %s", response.json())


async def webhook_runner(client: httpx.AsyncClient) -> None:
    response = await client.post("/internal/webhooks/tick")
    response.raise_for_status()
    result = response.json()
    if result.get("claimed"):
        logging.info("webhook_runner: %s", result)


async def export_runner(client: httpx.AsyncClient) -> None:
    response = await client.post("/internal/exports/tick")
    response.raise_for_status()
    result = response.json()
    if result.get("claimed"):
        logging.info("export_runner: %s", result)


async def retention_runner(client: httpx.AsyncClient) -> None:
    response = await client.post("/internal/retention/tick")
    response.raise_for_status()
    logging.info("retention_runner: %s", response.json())


async def calls_runner(client: httpx.AsyncClient) -> None:
    response = await client.post("/internal/calls/tick")
    response.raise_for_status()
    result = response.json()
    if result.get("expired"):
        logging.warning("calls_runner expired stale calls: %s", result)


async def run() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.info("VoiceOS worker ready: ingest, QA, billing, exports, WhatsApp and retention jobs")
    api_url = os.getenv("WORKER_API_URL", "http://api:8000")
    token = os.getenv("INTERNAL_API_TOKEN", "dev-internal-token")
    async with httpx.AsyncClient(
        base_url=api_url, headers={"X-Internal-Token": token}, timeout=25
    ) as client:
        next_billing = 0.0
        next_retention = 0.0
        while True:
            try:
                await campaign_runner(client)
            except Exception:
                logging.exception("campaign_runner failed; next attempt in 30 seconds")
            try:
                await webhook_runner(client)
            except Exception:
                logging.exception("webhook_runner failed; next attempt in 30 seconds")
            try:
                await export_runner(client)
            except Exception:
                logging.exception("export_runner failed; next attempt in 30 seconds")
            try:
                await calls_runner(client)
            except Exception:
                logging.exception("calls_runner failed; next attempt in 30 seconds")
            if asyncio.get_running_loop().time() >= next_billing:
                try:
                    await billing_meter(client)
                except Exception:
                    logging.exception("billing_meter failed; next attempt in one hour")
                next_billing = asyncio.get_running_loop().time() + 3600
            if asyncio.get_running_loop().time() >= next_retention:
                try:
                    await retention_runner(client)
                except Exception:
                    logging.exception("retention_runner failed; next attempt in one day")
                next_retention = asyncio.get_running_loop().time() + 86400
            await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(run())
