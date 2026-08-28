from __future__ import annotations

from typing import Any

import pytest
from voiceos_voice import livekit_worker


def test_provider_pipeline_uses_available_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
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
    monkeypatch.setattr(
        livekit_worker.llm,
        "FallbackAdapter",
        lambda providers, **_: ("llm-fallback", providers),
    )

    pipeline = livekit_worker.provider_pipeline({"language": "pt-BR"})

    assert pipeline["stt"] == "openai-stt"
    assert pipeline["llm"] == ("llm-fallback", ["anthropic-llm", "openai-llm"])
    assert pipeline["tts"] == "elevenlabs-tts"
    assert pipeline["vad"] == "silero-vad"


def test_provider_pipeline_requires_stt_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="required for STT"):
        livekit_worker.provider_pipeline({})


def test_provider_pipeline_skips_broken_anthropic_and_passes_elevenlabs_key(
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

    pipeline = livekit_worker.provider_pipeline({"language": "pt-BR"})

    assert pipeline["llm"] == "openai-llm"
    assert pipeline["tts"] == "elevenlabs-tts"
    assert received["api_key"] == "elevenlabs-test"
