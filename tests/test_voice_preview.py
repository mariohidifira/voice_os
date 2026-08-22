import json

import httpx
import pytest
from voiceos_api.voice_preview import ElevenLabsVoicePreview


@pytest.mark.asyncio
async def test_voice_catalog_and_preview_use_elevenlabs_contract() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["xi-api-key"] == "secret"
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "voices": [
                        {
                            "voice_id": "voice-1",
                            "name": "Ana",
                            "category": "premade",
                            "labels": {"language": "pt"},
                        }
                    ]
                },
            )
        payload = json.loads(request.content)
        assert payload["model_id"] == "eleven_flash_v2_5"
        assert payload["voice_settings"]["speed"] == 1.1
        return httpx.Response(200, content=b"ID3audio")

    service = ElevenLabsVoicePreview("secret", httpx.MockTransport(handler))
    assert (await service.list_voices())[0]["name"] == "Ana"
    assert await service.synthesize("voice-1", "Olá!", 1.1) == b"ID3audio"
    assert requests[1].url.path.endswith("/voice-1/stream")


@pytest.mark.asyncio
async def test_voice_preview_retries_provider_failure() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503)

    service = ElevenLabsVoicePreview("secret", httpx.MockTransport(handler))
    with pytest.raises(RuntimeError, match="3 attempts"):
        await service.list_voices()
    assert attempts == 3
