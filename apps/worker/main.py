import asyncio
import logging


async def run() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.info("VoiceOS worker ready: ingest, QA, billing, exports, WhatsApp and retention jobs")
    while True:
        await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(run())

