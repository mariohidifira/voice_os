from __future__ import annotations

from typing import Any

import pytest
from voiceos_voice import livekit_worker


def test_provider_pipeline_uses_configured_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-test")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "elevenlabs-test")
    monkeypatch.delenv("CARTESIA_API_KEY", raising=False)

    def unavailable(**_: Any) -> Any:
        raise AssertionError("provider without a configured key was initialized")

    monkeypatch.setattr(livekit_worker.deepgram, "STT", unavailable)
    monkeypatch.setattr(livekit_worker.openai, "STT", lambda **_: "openai-stt")
    monkeypatch.setattr(livekit_worker.anthropic, "LLM", lambda **_: "anthropic-llm")
    monkeypatch.setattr(livekit_worker.openai, "LLM", lambda **_: "openai-llm")
    monkeypatch.setattr(livekit_worker.elevenlabs, "TTS", lambda **_: "elevenlabs-tts")
    monkeypatch.setattr(livekit_worker.cartesia, "TTS", unavailable)
    monkeypatch.setattr(livekit_worker.silero.VAD, "load", lambda **_: "silero-vad")
    pipeline = livekit_worker.provider_pipeline({"language": "pt-BR"})

    assert pipeline["stt"] == "openai-stt"
    assert pipeline["llm"] == "anthropic-llm"
    assert pipeline["tts"] == "elevenlabs-tts"
    assert pipeline["vad"] == "silero-vad"


def test_provider_pipeline_pins_locale_and_cartesia_voice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-test")
    monkeypatch.setenv("CARTESIA_API_KEY", "cartesia-test")
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    received: dict[str, Any] = {}
    def openai_stt(**kwargs: Any) -> str:
        received["stt"] = kwargs
        return "stt"

    def cartesia_tts(**kwargs: Any) -> str:
        received["tts"] = kwargs
        return "tts"

    monkeypatch.setattr(livekit_worker.openai, "STT", openai_stt)
    monkeypatch.setattr(livekit_worker.anthropic, "LLM", lambda **_: "llm")
    monkeypatch.setattr(livekit_worker.cartesia, "TTS", cartesia_tts)
    monkeypatch.setattr(livekit_worker.silero.VAD, "load", lambda **_: "vad")

    livekit_worker.provider_pipeline(
        {"language": "pt_br", "tts": {"provider": "cartesia", "voice_id": "stable-voice"}}
    )

    assert received["stt"]["language"] == "pt-BR"
    assert received["tts"]["language"] == "pt-BR"
    assert received["tts"]["voice"] == "stable-voice"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Obrigado pelo contato. Até logo!", True),
        ("Tchau, tenha um bom dia.", True),
        ("Obrigado, vou consultar seu pedido.", False),
    ],
)
def test_is_farewell_requires_explicit_closing(text: str, expected: bool) -> None:
    assert livekit_worker.is_farewell(text) is expected


def test_provider_pipeline_requires_stt_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="required for STT"):
        livekit_worker.provider_pipeline({})


def test_deterministic_pipeline_does_not_initialize_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-test")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "elevenlabs-test")
    monkeypatch.setattr(livekit_worker.openai, "STT", lambda **_: "openai-stt")
    monkeypatch.setattr(livekit_worker.elevenlabs, "TTS", lambda **_: "elevenlabs-tts")
    monkeypatch.setattr(livekit_worker.silero.VAD, "load", lambda **_: "silero-vad")
    monkeypatch.setattr(
        livekit_worker.anthropic,
        "LLM",
        lambda **_: (_ for _ in ()).throw(AssertionError("LLM must not be initialized")),
    )
    pipeline = livekit_worker.provider_pipeline(
        {"language": "pt-BR", "behavior": {"execution_mode": "deterministic"}}
    )
    assert "llm" not in pipeline


def test_provider_pipeline_rejects_broken_configured_anthropic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-test")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "elevenlabs-test")
    monkeypatch.delenv("CARTESIA_API_KEY", raising=False)
    received: dict[str, Any] = {}

    monkeypatch.setattr(livekit_worker.openai, "STT", lambda **_: "openai-stt")
    monkeypatch.setattr(
        livekit_worker.anthropic,
        "LLM",
        lambda **_: (_ for _ in ()).throw(TypeError("incompatible SDK")),
    )
    monkeypatch.setattr(livekit_worker.openai, "LLM", lambda **_: "openai-llm")

    def elevenlabs_tts(**kwargs: Any) -> str:
        received.update(kwargs)
        return "elevenlabs-tts"

    monkeypatch.setattr(livekit_worker.elevenlabs, "TTS", elevenlabs_tts)
    monkeypatch.setattr(livekit_worker.silero.VAD, "load", lambda **_: "silero-vad")

    with pytest.raises(RuntimeError, match="required for LLM"):
        livekit_worker.provider_pipeline({"language": "pt-BR"})
