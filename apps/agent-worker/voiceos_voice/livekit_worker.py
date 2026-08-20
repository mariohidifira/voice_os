import json
import os
from typing import Any
from uuid import UUID

from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli, llm, stt, tts
from livekit.plugins import anthropic, cartesia, deepgram, elevenlabs, openai, silero

from .api_client import RedisRuntimeCache, WorkerAPI
from .prompting import build_system_prompt


def room_metadata(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("room metadata must be valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("room metadata must be a JSON object")
    return value


def provider_pipeline(runtime: dict[str, Any]) -> dict[str, Any]:
    stt_config = runtime.get("stt") or {}
    llm_config = runtime.get("llm") or {}
    tts_config = runtime.get("tts") or {}
    language = str(runtime.get("language") or "pt-BR")
    primary_stt = deepgram.STT(
        model=str(stt_config.get("model") or "nova-3"),
        language=language,
        interim_results=True,
        smart_format=True,
        endpointing_ms=int(stt_config.get("endpointing_ms", 300)),
        utterance_end_ms=int(stt_config.get("utterance_end_ms", 1000)),
    )
    fallback_stt = openai.STT(model=str(stt_config.get("fallback_model") or "whisper-1"), language=language)
    primary_llm = anthropic.LLM(
        model=str(llm_config.get("model") or "claude-sonnet-4-6"),
        temperature=float(llm_config.get("temperature", 0.3)),
        max_tokens=int(llm_config.get("max_tokens", 350)),
        max_retries=1,
    )
    fallback_llm = openai.LLM(model=str(llm_config.get("fallback_model") or "gpt-4.1"), temperature=0.3)
    voice = str(tts_config.get("voice_id") or os.getenv("ELEVENLABS_VOICE_ID") or "EXAVITQu4vr4xnSDxMaL")
    primary_tts = elevenlabs.TTS(
        voice_id=voice,
        model=str(tts_config.get("model") or "eleven_flash_v2_5"),
        streaming_latency=3,
        language=language,
    )
    fallback_tts = cartesia.TTS(
        model=str(tts_config.get("fallback_model") or "sonic-3"),
        voice=str(tts_config.get("fallback_voice_id") or "f786b574-daa5-4673-aa0c-cbe3e8534c02"),
        language=language,
    )
    return {
        "stt": stt.FallbackAdapter([primary_stt, fallback_stt], attempt_timeout=3, max_retry_per_stt=1),
        "llm": llm.FallbackAdapter([primary_llm, fallback_llm], attempt_timeout=8, max_retry_per_llm=1),
        "tts": tts.FallbackAdapter([primary_tts, fallback_tts], max_retry_per_tts=1),
        "vad": silero.VAD.load(
            min_speech_duration=0.05,
            min_silence_duration=float((runtime.get("turn") or {}).get("min_silence_duration", 0.55)),
            activation_threshold=0.5,
        ),
    }


server = AgentServer()


@server.rtc_session(agent_name="voiceos-agent")
async def voiceos_agent(ctx: JobContext) -> None:
    metadata = room_metadata(ctx.room.metadata)
    if not metadata.get("agent_id"):
        raise ValueError("room metadata requires agent_id")
    api = WorkerAPI(
        os.getenv("WORKER_API_URL", "http://api:8000"),
        os.getenv("INTERNAL_API_TOKEN", ""),
        RedisRuntimeCache(os.getenv("REDIS_URL", "redis://redis:6379/0")),
    )
    runtime = await api.runtime(UUID(str(metadata["agent_id"])), str(metadata.get("version") or "current"))
    variables = {**runtime.get("variables", {}), **dict(metadata.get("variables") or {})}
    prompt = build_system_prompt(
        {"id": runtime["tenant_id"]},
        runtime,
        channel=str(metadata.get("channel") or "web"),
        variables=variables,
        end_user=metadata.get("end_user"),
        tools=list(runtime.get("tools", [])),
        now=__import__("datetime").datetime.now(__import__("datetime").UTC),
    )
    pipeline = provider_pipeline(runtime)
    turn = runtime.get("turn") or {}
    session = AgentSession(
        **pipeline,
        min_endpointing_delay=float(turn.get("min_endpointing_delay", 0.5)),
        max_endpointing_delay=float(turn.get("max_endpointing_delay", 3.0)),
        allow_interruptions=True,
        min_interruption_duration=float(turn.get("min_interruption_duration", 0.5)),
        min_interruption_words=int(turn.get("min_interruption_words", 1)),
    )
    await session.start(room=ctx.room, agent=Agent(instructions=prompt))
    await ctx.connect()
    greeting = str(runtime.get("greeting") or "Olá! Como posso ajudar?")
    await session.say(greeting, allow_interruptions=True)


def run() -> None:
    cli.run_app(server)
