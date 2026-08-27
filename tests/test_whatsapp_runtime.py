import json

import httpx

from voiceos_api.config import Settings
from voiceos_api.whatsapp_runtime import (
    fallback_reply,
    generate_whatsapp_reply,
    synthesize_whatsapp_audio,
    transcribe_whatsapp_audio,
)


class FakeVoicePreview:
    configured = True

    async def synthesize(self, voice_id: str, text: str, speed: float) -> bytes:
        assert voice_id == "voice-1"
        assert text
        assert speed == 1.0
        return b"preview-mp3"


async def test_transcribe_whatsapp_audio_uses_deepgram_first() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "results": {
                    "channels": [{"alternatives": [{"transcript": "ola pelo deepgram"}]}]
                }
            },
        )
    )
    settings = Settings(app_env="test", deepgram_api_key="dg-key")
    text = await transcribe_whatsapp_audio(
        settings, {"stt": {"model": "nova-3"}}, b"audio", transport=transport
    )
    assert text == "ola pelo deepgram"


async def test_transcribe_whatsapp_audio_falls_back_to_openai() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "deepgram" in str(request.url):
            return httpx.Response(503, json={"error": "down"})
        return httpx.Response(200, json={"text": "ola pelo openai"})

    settings = Settings(app_env="test", deepgram_api_key="dg-key", openai_api_key="oa-key")
    text = await transcribe_whatsapp_audio(
        settings, {"language": "pt-BR"}, b"audio", transport=httpx.MockTransport(handler)
    )
    assert text == "ola pelo openai"


async def test_generate_whatsapp_reply_runs_tool_and_returns_follow_up_text() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    async def execute_tool(tool: dict[str, object], arguments: dict[str, object]) -> dict[str, object]:
        calls.append((str(tool["name"]), arguments))
        return {"available": ["2026-08-26T10:00:00Z"]}

    responses = [
        {
            "content": [
                {"type": "text", "text": "Vou consultar."},
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "google_calendar_check",
                    "input": {"date": "2026-08-26"},
                },
            ]
        },
        {"content": [{"type": "text", "text": "Tenho horario livre as 10h."}]},
    ]

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=responses.pop(0))

    settings = Settings(app_env="test", anthropic_api_key="ant-key")
    runtime = {
        "system_prompt": "Ajude com agendamentos.",
        "greeting": "Ola",
        "llm": {"provider": "anthropic", "model": "claude-haiku-4-5"},
        "tools": [
            {
                "id": "tool-1",
                "name": "google_calendar_check",
                "description": "Consulta agenda",
                "parameters_schema": {
                    "type": "object",
                    "properties": {"date": {"type": "string"}},
                    "required": ["date"],
                },
            }
        ],
    }
    reply, handoff, tool_calls = await generate_whatsapp_reply(
        settings,
        runtime,
        "Quais horarios eu tenho amanha?",
        "text",
        execute_tool=execute_tool,
        transport=httpx.MockTransport(handler),
    )
    assert reply == "Vou consultar. Tenho horario livre as 10h."
    assert handoff is False
    assert calls == [("google_calendar_check", {"date": "2026-08-26"})]
    assert len(tool_calls) == 1
    assert tool_calls[0]["status"] == "ok"


async def test_generate_whatsapp_reply_falls_back_without_provider() -> None:
    reply, handoff, tool_calls = await generate_whatsapp_reply(
        Settings(app_env="test"),
        {"greeting": "Ola!"},
        "Quero falar com humano",
        "text",
    )
    assert "atendente humano" in reply
    assert handoff is True
    assert tool_calls == []


async def test_synthesize_whatsapp_audio_prefers_elevenlabs_ogg() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=b"ogg-audio"))
    audio = await synthesize_whatsapp_audio(
        Settings(app_env="test", elevenlabs_api_key="el-key"),
        {"tts": {"voice_id": "voice-1", "model": "eleven_flash_v2_5"}},
        "Resposta curta",
        FakeVoicePreview(),
        transport=transport,
    )
    assert audio == (b"ogg-audio", "reply.ogg", "audio/ogg")


async def test_synthesize_whatsapp_audio_falls_back_to_preview() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "tts down"})

    audio = await synthesize_whatsapp_audio(
        Settings(app_env="test", elevenlabs_api_key="el-key"),
        {"tts": {"voice_id": "voice-1", "model": "eleven_flash_v2_5"}},
        "Resposta curta",
        FakeVoicePreview(),
        transport=httpx.MockTransport(handler),
    )
    assert audio == (b"preview-mp3", "reply.mp3", "audio/mpeg")


def test_fallback_reply_for_audio_message() -> None:
    reply, handoff = fallback_reply({"greeting": "Ola"}, "Preciso remarcar", "audio")
    assert reply == "Recebi sua mensagem de voz. Preciso remarcar"
    assert handoff is False
