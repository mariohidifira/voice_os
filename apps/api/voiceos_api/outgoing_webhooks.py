import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

RETRY_DELAYS = (60, 300, 1_800, 7_200, 43_200)


def webhook_signature(body: bytes, secret: str, timestamp: int | None = None) -> str:
    ts = timestamp if timestamp is not None else int(time.time())
    digest = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


class OutgoingWebhookSender:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client

    async def send(self, url: str, payload: dict[str, Any], secret: str) -> int:
        body = json.dumps(payload, separators=(",", ":"), default=str).encode()
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "VoiceOS-Webhooks/1.0",
            "X-VoiceOS-Signature": webhook_signature(body, secret),
        }
        if self.client:
            response = await self.client.post(url, content=body, headers=headers, timeout=10)
            return response.status_code
        async with httpx.AsyncClient() as client:
            response = await client.post(url, content=body, headers=headers, timeout=10)
            return response.status_code


def delivery_result(attempts: int, status_code: int | None) -> dict[str, Any]:
    if status_code is not None and 200 <= status_code < 300:
        return {"status": "delivered", "last_status_code": status_code, "next_retry_at": None}
    if attempts >= len(RETRY_DELAYS):
        return {"status": "failed", "last_status_code": status_code, "next_retry_at": None}
    return {
        "status": "retrying",
        "last_status_code": status_code,
        "next_retry_at": datetime.now(UTC) + timedelta(seconds=RETRY_DELAYS[max(0, attempts - 1)]),
    }
