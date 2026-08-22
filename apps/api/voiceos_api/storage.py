import asyncio
from functools import lru_cache
from typing import Any

import boto3  # type: ignore[import-untyped]

from .config import Settings, get_settings


class RecordingStorage:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        self.client = client or boto3.client("s3", region_name=settings.aws_region)

    async def playback_url(self, key: str, expires_s: int = 900) -> str:
        return await asyncio.to_thread(
            self.client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self.settings.s3_bucket_recordings, "Key": key},
            ExpiresIn=expires_s,
        )


@lru_cache
def get_recording_storage() -> RecordingStorage:
    return RecordingStorage(get_settings())
