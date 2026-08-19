import asyncio
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text

from .config import Settings, get_settings
from .db import engine


class HealthChecker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def _database(self) -> bool:
        try:
            async with asyncio.timeout(2), engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def _redis(self) -> bool:
        client = Redis.from_url(self.settings.redis_url, socket_connect_timeout=2)
        try:
            async with asyncio.timeout(2):
                return bool(await client.ping())
        except Exception:
            return False
        finally:
            await client.aclose()

    async def check(self) -> dict[str, Any]:
        database, redis = await asyncio.gather(self._database(), self._redis())
        components = {
            "database": database,
            "redis": redis,
            "s3": all((self.settings.s3_bucket_recordings, self.settings.s3_bucket_documents, self.settings.s3_bucket_exports)),
            "livekit_token": all((self.settings.livekit_url, self.settings.livekit_api_key, self.settings.livekit_api_secret)),
        }
        return {"status": "ok" if all(components.values()) else "degraded", "service": "api", "components": components}


def get_health_checker() -> HealthChecker:
    return HealthChecker(get_settings())

