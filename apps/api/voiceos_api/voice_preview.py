import asyncio
from functools import lru_cache
from typing import Any, Protocol

import httpx

from .config import get_settings


class VoicePreview(Protocol):
    @property
    def configured(self) -> bool: ...
    async def list_voices(self) -> list[dict[str, Any]]: ...
    async def synthesize(self, voice_id: str, text: str, speed: float) -> bytes: ...


class ElevenLabsVoicePreview:
    configured = True

    def __init__(self, api_key: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.api_key = api_key
        self.transport = transport

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        error: Exception | None = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(transport=self.transport, timeout=20) as client:
                    response = await client.request(
                        method, url, headers={"xi-api-key": self.api_key}, **kwargs
                    )
                    response.raise_for_status()
                    return response
            except httpx.HTTPError as exc:
                error = exc
                if attempt < 2:
                    await asyncio.sleep(0.1 * (attempt + 1))
        raise RuntimeError(f"ElevenLabs request failed after 3 attempts: {error}") from error

    async def list_voices(self) -> list[dict[str, Any]]:
        response = await self._request("GET", "https://api.elevenlabs.io/v1/voices")
        return [
            {
                "id": str(item["voice_id"]),
                "name": str(item.get("name") or item["voice_id"]),
                "category": item.get("category"),
                "labels": item.get("labels") or {},
            }
            for item in response.json().get("voices", [])
            if item.get("voice_id")
        ]

    async def synthesize(self, voice_id: str, text: str, speed: float) -> bytes:
        response = await self._request(
            "POST",
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream",
            params={"output_format": "mp3_44100_128"},
            json={
                "text": text,
                "model_id": "eleven_flash_v2_5",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "speed": speed},
            },
        )
        return response.content


class UnavailableVoicePreview:
    configured = False

    async def list_voices(self) -> list[dict[str, Any]]:
        return []

    async def synthesize(self, voice_id: str, text: str, speed: float) -> bytes:
        raise RuntimeError("ELEVENLABS_API_KEY is required for voice preview")


@lru_cache
def get_voice_preview() -> VoicePreview:
    api_key = get_settings().elevenlabs_api_key
    return ElevenLabsVoicePreview(api_key) if api_key else UnavailableVoicePreview()
