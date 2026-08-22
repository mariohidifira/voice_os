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


class ExportStorage:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        self.client = client or boto3.client("s3", region_name=settings.aws_region)

    async def upload(self, key: str, body: bytes, content_type: str = "text/csv") -> None:
        await asyncio.to_thread(
            self.client.put_object,
            Bucket=self.settings.s3_bucket_exports,
            Key=key,
            Body=body,
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )

    async def download_url(self, key: str, expires_s: int = 900) -> str:
        return await asyncio.to_thread(
            self.client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self.settings.s3_bucket_exports, "Key": key},
            ExpiresIn=expires_s,
        )


class RetentionStorage:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        self.client = client or boto3.client("s3", region_name=settings.aws_region)

    async def delete(self, recording_keys: list[str], document_keys: list[str]) -> None:
        for bucket, keys in (
            (self.settings.s3_bucket_recordings, recording_keys),
            (self.settings.s3_bucket_documents, document_keys),
        ):
            if keys:
                await asyncio.to_thread(
                    self.client.delete_objects,
                    Bucket=bucket,
                    Delete={"Objects": [{"Key": key} for key in keys], "Quiet": True},
                )

@lru_cache
def get_recording_storage() -> RecordingStorage:
    return RecordingStorage(get_settings())


@lru_cache
def get_export_storage() -> ExportStorage:
    return ExportStorage(get_settings())


@lru_cache
def get_retention_storage() -> RetentionStorage:
    return RetentionStorage(get_settings())
