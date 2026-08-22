import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from google.protobuf.duration_pb2 import Duration
from livekit import api as livekit_api
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    CloseEvent,
    ConversationItemAddedEvent,
    JobContext,
    MetricsCollectedEvent,
    SessionUsageUpdatedEvent,
    UserInputTranscribedEvent,
    UserStateChangedEvent,
    cli,
    function_tool,
    llm,
    stt,
    tts,
)
from livekit.agents.llm import Tool, Toolset
from livekit.plugins import anthropic, cartesia, deepgram, elevenlabs, openai, silero

from .accounting import CallAccounting
from .api_client import RedisRuntimeCache, WorkerAPI
from .phone_runtime import (
    AnthropicAMDClassifier,
    HeuristicAMDClassifier,
    business_hours_open,
)
from .prompting import build_system_prompt
from .recording import start_room_recording

DTMF_CODES = {**{str(value): value for value in range(10)}, "*": 10, "#": 11, "A": 12, "B": 13, "C": 14, "D": 15}


async def send_dtmf(participant: Any, digits: str) -> None:
    normalized = digits.upper()
    if not normalized or len(normalized) > 32 or any(digit not in DTMF_CODES for digit in normalized):
        raise ValueError("digits must contain 1-32 DTMF symbols: 0-9, *, #, A-D")
    for index, digit in enumerate(normalized):
        await participant.publish_dtmf(code=DTMF_CODES[digit], digit=digit)
        if index < len(normalized) - 1:
            await asyncio.sleep(0.15)


async def transfer_phone_call(
    room: Any,
    metadata: dict[str, Any],
    behavior: dict[str, Any],
    arguments: dict[str, Any],
) -> dict[str, Any]:
    destination = str(arguments.get("destination") or behavior.get("transfer_number") or "")
    if not destination.startswith("+") or not destination[1:].isdigit():
        return {"error": "invalid_destination", "message": "Transfer destination must be E.164"}
    mode = str(arguments.get("mode") or "cold")
    if mode not in {"cold", "warm"}:
        return {"error": "invalid_mode", "message": "Transfer mode must be cold or warm"}
    client = livekit_api.LiveKitAPI(
        os.getenv("LIVEKIT_URL", ""),
        os.getenv("LIVEKIT_API_KEY", ""),
        os.getenv("LIVEKIT_API_SECRET", ""),
    )
    try:
        if mode == "cold":
            requested_identity = str(arguments.get("participant_identity") or "")
            sip_participant = next(
                (
                    participant
                    for participant in room.remote_participants.values()
                    if (requested_identity and participant.identity == requested_identity)
                    or int(participant.kind) == 3
                ),
                None,
            )
            if not sip_participant:
                return {"error": "sip_participant_not_found", "message": "No SIP leg to transfer"}
            transferred = await client.sip.transfer_sip_participant(
                livekit_api.TransferSIPParticipantRequest(
                    participant_identity=sip_participant.identity,
                    room_name=room.name,
                    transfer_to=f"tel:{destination}",
                    play_dialtone=True,
                )
            )
            return {
                "status": "transferred",
                "mode": "cold",
                "destination": destination,
                "participant_identity": transferred.participant_identity,
            }
        trunk_id = os.getenv("LIVEKIT_SIP_TRUNK_ID_OUTBOUND", "")
        from_number = str(metadata.get("from") or metadata.get("to") or "")
        if not trunk_id or not from_number:
            return {"error": "sip_not_configured", "message": "Warm transfer trunk is unavailable"}
        identity = f"transfer_{destination.removeprefix('+')}"
        participant = await client.sip.create_sip_participant(
            livekit_api.CreateSIPParticipantRequest(
                sip_trunk_id=trunk_id,
                sip_call_to=destination,
                sip_number=from_number,
                room_name=room.name,
                participant_identity=identity,
                participant_name=f"Transfer {destination}",
                wait_until_answered=True,
                play_dialtone=False,
                krisp_enabled=True,
            )
        )
        return {
            "status": "transferred",
            "mode": "warm",
            "destination": destination,
            "participant_identity": participant.participant_identity or identity,
        }
    finally:
        await client.aclose()


async def dial_outbound(
    api: WorkerAPI, call_id: UUID, room_name: str, metadata: dict[str, Any]
) -> None:
    trunk_id = os.getenv("LIVEKIT_SIP_TRUNK_ID_OUTBOUND", "")
    to_number = str(metadata.get("to") or "")
    from_number = str(metadata.get("from") or "")
    if not trunk_id or not to_number or not from_number:
        await api.update_call(
            call_id,
            {
                "status": "failed",
                "end_reason": "error",
                "ended_at": datetime.now(UTC).isoformat(),
            },
        )
        raise RuntimeError("outbound SIP metadata or trunk is not configured")
    await api.update_call(call_id, {"status": "ringing", "livekit_room": room_name})
    client = livekit_api.LiveKitAPI(
        os.getenv("LIVEKIT_URL", ""),
        os.getenv("LIVEKIT_API_KEY", ""),
        os.getenv("LIVEKIT_API_SECRET", ""),
    )
    try:
        participant = await client.sip.create_sip_participant(
            livekit_api.CreateSIPParticipantRequest(
                sip_trunk_id=trunk_id,
                sip_call_to=to_number,
                sip_number=from_number,
                room_name=room_name,
                participant_identity=f"phone_{to_number.removeprefix('+')}",
                participant_name=to_number,
                participant_metadata=json.dumps({"channel": "phone_outbound"}),
                wait_until_answered=True,
                play_dialtone=False,
                krisp_enabled=True,
                ringing_timeout=Duration(seconds=30),
            )
        )
    except Exception as exc:
        message = str(exc).casefold()
        status = (
            "busy"
            if "busy" in message or "486" in message
            else "no_answer"
            if "timeout" in message or "deadline" in message or "no answer" in message
            else "failed"
        )
        await api.update_call(
            call_id,
            {
                "status": status,
                "end_reason": "error",
                "ended_at": datetime.now(UTC).isoformat(),
            },
        )
        raise
    finally:
        await client.aclose()
    await api.update_call(
        call_id,
        {
            "status": "in_progress",
            "provider_call_sid": str(participant.sip_call_id),
            "answered_at": datetime.now(UTC).isoformat(),
        },
    )


def _jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "__dict__"):
        return {key: _jsonable(item) for key, item in vars(value).items() if not key.startswith("_")}
    return value


@dataclass
class LiveKitCallBridge:
    api: WorkerAPI
    call_id: UUID
    variables: dict[str, Any]
    ordinal: int = 0
    end_reason: str = "completed"
    pending: set[asyncio.Task[None]] = field(default_factory=set)
    accounting: CallAccounting = field(default_factory=CallAccounting)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def spawn(self, coroutine: Any) -> None:
        task = asyncio.create_task(coroutine)
        self.pending.add(task)
        task.add_done_callback(self.pending.discard)

    async def drain(self) -> None:
        if self.pending:
            await asyncio.gather(*tuple(self.pending), return_exceptions=True)

    async def persist_event(self, event_type: str, payload: dict[str, Any]) -> None:
        await self.api.append_events(
            self.call_id,
            [{"type": event_type, "payload": payload, "at": datetime.now(UTC).isoformat()}],
        )

    async def user_transcript(self, event: UserInputTranscribedEvent) -> None:
        await self.persist_event(
            "stt.final" if event.is_final else "stt.interim",
            {"text": event.transcript, "is_final": event.is_final, "language": str(event.language or "")},
        )
        if event.is_final and event.transcript.strip():
            self.accounting.turns += 1
            await self.api.append_turns(
                self.call_id,
                [{"ordinal": self.ordinal, "role": "user", "text": event.transcript, "started_at": datetime.now(UTC).isoformat()}],
            )
            self.ordinal += 1

    async def conversation_item(self, event: ConversationItemAddedEvent) -> None:
        item = event.item
        role = str(getattr(item, "role", ""))
        content = getattr(item, "text_content", None) or getattr(item, "content", None)
        if role != "assistant" or not content:
            return
        text = content if isinstance(content, str) else " ".join(str(part) for part in content)
        metrics = getattr(item, "metrics", None)
        e2e_latency = (
            metrics.get("e2e_latency")
            if isinstance(metrics, dict)
            else getattr(metrics, "e2e_latency", None)
        )
        self.accounting.observe_e2e_latency(e2e_latency)
        await self.api.append_turns(
            self.call_id,
            [{"ordinal": self.ordinal, "role": "assistant", "text": text, "started_at": datetime.now(UTC).isoformat()}],
        )
        self.ordinal += 1
        self.accounting.turns += 1

    async def metric(self, event: MetricsCollectedEvent) -> None:
        self.accounting.observe_metric(event)
        await self.persist_event("pipeline.metric", {"metric": _jsonable(event.metrics)})

    async def usage(self, event: SessionUsageUpdatedEvent) -> None:
        self.accounting.observe_usage(event)
        await self.persist_event("pipeline.usage", {"usage": _jsonable(event.usage)})

    async def close(self, event: CloseEvent | None = None) -> None:
        await self.drain()
        if event and event.error:
            self.end_reason = "provider_error"
        duration_s = max(0, round((datetime.now(UTC) - self.started_at).total_seconds()))
        await self.api.update_call(
            self.call_id,
            {
                "status": "failed" if self.end_reason == "provider_error" else "completed",
                "end_reason": self.end_reason,
                "ended_at": datetime.now(UTC).isoformat(),
                "duration_s": duration_s,
                "billable_seconds": duration_s,
                "latency": self.accounting.latency(),
                "cost": self.accounting.cost(duration_s),
                "variables": self.variables,
            },
        )
        try:
            await self.api.postprocess_call(self.call_id)
        except RuntimeError:
            await self.persist_event("call.postprocess_enqueue_failed", {})


@dataclass
class SessionGuards:
    session: AgentSession[Any]
    bridge: LiveKitCallBridge
    silence_prompt: str
    max_duration_s: int
    silence_count: int = 0
    duration_task: asyncio.Task[None] | None = None

    def start(self) -> None:
        self.duration_task = asyncio.create_task(self.enforce_duration())

    async def enforce_duration(self) -> None:
        await asyncio.sleep(self.max_duration_s)
        self.bridge.end_reason = "max_duration"
        speech = self.session.say("Atingimos o tempo máximo desta conversa. Obrigado pelo contato.", allow_interruptions=False)
        await speech.wait_for_playout()
        self.session.shutdown(drain=True)

    async def user_state(self, event: UserStateChangedEvent) -> None:
        if event.new_state != "away":
            return
        self.silence_count += 1
        await self.bridge.persist_event("silence.detected", {"count": self.silence_count})
        if self.silence_count == 1:
            await self.session.say(self.silence_prompt, allow_interruptions=True).wait_for_playout()
        else:
            self.bridge.end_reason = "silence"
            await self.session.say("Vou encerrar por falta de resposta. Até logo!", allow_interruptions=False).wait_for_playout()
            self.session.shutdown(drain=True)

    def cancel(self) -> None:
        if self.duration_task and not self.duration_task.done():
            self.duration_task.cancel()


def dynamic_tools(
    api: WorkerAPI,
    call_id: UUID,
    tools: list[dict[str, Any]],
    variables: dict[str, Any],
    end_user: dict[str, Any],
    session_ref: dict[str, AgentSession[Any]],
    bridge: LiveKitCallBridge,
    dtmf_sender: Callable[[str], Awaitable[None]] | None = None,
    transfer_handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]] | None = None,
) -> list[Tool | Toolset]:
    result: list[Tool | Toolset] = []
    for definition in tools:
        tool_id = str(definition["id"])
        name = str(definition["name"])
        kind = str(definition.get("native_kind") or name)

        async def execute(
            raw_arguments: dict[str, Any],
            *,
            remote_tool_id: str = tool_id,
            tool_name: str = name,
            tool_kind: str = kind,
        ) -> dict[str, Any]:
            if tool_kind == "set_variable":
                variables[str(raw_arguments["name"])] = raw_arguments.get("value")
                await bridge.persist_event("variable.set", {"name": raw_arguments["name"]})
                return {"status": "ok", "name": raw_arguments["name"], "value": raw_arguments.get("value")}
            if tool_kind == "end_call":
                bridge.end_reason = str(raw_arguments.get("reason") or "agent_hangup")
                farewell = str(raw_arguments.get("farewell") or "Obrigado pelo contato. Até logo!")

                async def finish_after_farewell() -> None:
                    speech = session_ref["session"].say(farewell, allow_interruptions=False)
                    await speech.wait_for_playout()
                    session_ref["session"].shutdown(drain=True)

                asyncio.create_task(finish_after_farewell())
                return {"status": "ending", "reason": bridge.end_reason}
            if tool_kind == "dtmf":
                if dtmf_sender is None:
                    return {"error": "channel_unsupported", "message": "DTMF requires a phone call"}
                digits = str(raw_arguments.get("digits") or "")
                try:
                    await dtmf_sender(digits)
                except ValueError as exc:
                    return {"error": "invalid_digits", "message": str(exc)}
                await bridge.persist_event("dtmf", {"digits": digits})
                return {"status": "sent", "digits": digits}
            if tool_kind == "transfer_call":
                if transfer_handler is None:
                    return {
                        "error": "channel_unsupported",
                        "message": "Transfer requires a phone call",
                    }
                await bridge.persist_event("transfer.requested", raw_arguments)
                transferred = await transfer_handler(raw_arguments)
                if "error" in transferred:
                    return transferred
                bridge.end_reason = "transferred"
                await bridge.persist_event("transfer.completed", transferred)
                if transferred.get("mode") == "warm":
                    summary = str(
                        raw_arguments.get("summary")
                        or f"Transferência solicitada. Motivo: {raw_arguments.get('reason', 'atendimento humano')}."
                    )
                    await session_ref["session"].say(
                        summary, allow_interruptions=False
                    ).wait_for_playout()
                session_ref["session"].shutdown(drain=True)
                return transferred
            return await api.execute_tool(
                {
                    "tool_id": remote_tool_id,
                    "call_id": str(call_id),
                    "arguments": raw_arguments,
                    "session_variables": variables,
                    "end_user": end_user,
                }
            )

        schema = {
            "name": name,
            "description": str(definition.get("description") or name),
            "parameters": dict(definition.get("parameters_schema") or {"type": "object"}),
        }
        result.append(function_tool(raw_schema=schema)(execute))
    return result


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
    if metadata.get("call_id"):
        call_id = UUID(str(metadata["call_id"]))
        if metadata.get("channel") == "phone_outbound":
            await dial_outbound(api, call_id, ctx.room.name, metadata)
        else:
            await api.update_call(call_id, {"status": "in_progress", "livekit_room": ctx.room.name, "answered_at": datetime.now(UTC).isoformat()})
    else:
        created = await api.create_call(
            {
                "tenant_id": runtime["tenant_id"],
                "agent_id": runtime["agent_id"],
                "agent_version_id": runtime["version_id"],
                "channel": str(metadata.get("channel") or "web"),
                "livekit_room": ctx.room.name,
                "variables": variables,
                "metadata": {"dispatch": metadata},
            }
        )
        call_id = UUID(str(created["id"]))
        await api.update_call(call_id, {"status": "in_progress", "answered_at": datetime.now(UTC).isoformat()})
    bridge = LiveKitCallBridge(api, call_id, variables)
    prompt = build_system_prompt(
        {"id": runtime["tenant_id"]},
        runtime,
        channel=str(metadata.get("channel") or "web"),
        variables=variables,
        end_user=metadata.get("end_user"),
        tools=list(runtime.get("tools", [])),
        now=datetime.now(UTC),
    )
    pipeline = provider_pipeline(runtime)
    turn = runtime.get("turn") or {}
    behavior = runtime.get("behavior") or {}
    amd_transcript: list[str] = []
    session_ref: dict[str, AgentSession[Any]] = {}
    tools = dynamic_tools(
        api,
        call_id,
        list(runtime.get("tools", [])),
        variables,
        dict(metadata.get("end_user") or {}),
        session_ref,
        bridge,
        (lambda digits: send_dtmf(ctx.room.local_participant, digits))
        if str(metadata.get("channel") or "web").startswith("phone_")
        else None,
        (
            lambda arguments: transfer_phone_call(
                ctx.room, metadata, behavior, arguments
            )
        )
        if str(metadata.get("channel") or "web").startswith("phone_")
        else None,
    )
    session = AgentSession(
        **pipeline,
        tools=tools,
        min_endpointing_delay=float(turn.get("min_endpointing_delay", 0.5)),
        max_endpointing_delay=float(turn.get("max_endpointing_delay", 3.0)),
        allow_interruptions=True,
        min_interruption_duration=float(turn.get("min_interruption_duration", 0.5)),
        min_interruption_words=int(turn.get("min_interruption_words", 1)),
        user_away_timeout=float(behavior.get("silence_timeout_s", 8)),
    )
    session_ref["session"] = session
    guards = SessionGuards(
        session,
        bridge,
        str(behavior.get("silence_prompt") or "Você ainda está aí?"),
        int(behavior.get("max_call_duration_s", 900)),
    )
    def user_transcribed(event: UserInputTranscribedEvent) -> None:
        bridge.spawn(bridge.user_transcript(event))
        if metadata.get("channel") == "phone_outbound" and event.is_final:
            amd_transcript.append(event.transcript)

    session.on("user_input_transcribed", user_transcribed)
    session.on("conversation_item_added", lambda event: bridge.spawn(bridge.conversation_item(event)))
    session.on("metrics_collected", lambda event: bridge.spawn(bridge.metric(event)))
    session.on("session_usage_updated", lambda event: bridge.spawn(bridge.usage(event)))
    session.on("user_state_changed", lambda event: bridge.spawn(guards.user_state(event)))

    async def close_session(event: CloseEvent) -> None:
        guards.cancel()
        await bridge.close(event)

    session.on("close", lambda event: asyncio.create_task(close_session(event)))
    await session.start(room=ctx.room, agent=Agent(instructions=prompt))
    guards.start()
    await ctx.connect()
    greeting = str(runtime.get("greeting") or "Olá! Como posso ajudar?")
    tenant_settings = dict(runtime.get("tenant_settings") or {})
    if metadata.get("channel") == "phone_inbound" and not business_hours_open(
        dict(behavior.get("business_hours") or {}), datetime.now(UTC)
    ):
        greeting = str(
            behavior.get("out_of_hours_message")
            or "Nosso atendimento está fora do horário. Deixe sua mensagem após o sinal."
        )
    if tenant_settings.get("recording_enabled"):
        try:
            egress_id, key = await start_room_recording(
                room_name=ctx.room.name,
                tenant_id=UUID(str(runtime["tenant_id"])),
                call_id=call_id,
                bucket=os.getenv("S3_BUCKET_RECORDINGS", "voiceos-recordings"),
                region=os.getenv("AWS_REGION", "sa-east-1"),
            )
            await bridge.persist_event("recording.started", {"egress_id": egress_id, "s3_key": key})
        except Exception as exc:
            await bridge.persist_event("recording.failed", {"error": type(exc).__name__})
        if tenant_settings.get("recording_notice"):
            notice = str(tenant_settings.get("recording_notice_text") or "Esta ligação pode ser gravada.")
            greeting = f"{notice} {greeting}"
    if metadata.get("channel") == "phone_outbound":
        await asyncio.sleep(4)
        transcript = " ".join(amd_transcript)
        classifier = (
            AnthropicAMDClassifier(
                os.environ["ANTHROPIC_API_KEY"],
                os.getenv("ANTHROPIC_POSTPROCESS_MODEL", "claude-haiku-4-5"),
            )
            if os.getenv("ANTHROPIC_API_KEY") and transcript
            else HeuristicAMDClassifier()
        )
        try:
            classification = await classifier.classify(transcript)
        except Exception:
            classification = await HeuristicAMDClassifier().classify(transcript)
        await bridge.persist_event(
            "amd.classified", {"classification": classification, "transcript": transcript[:500]}
        )
        if classification == "voicemail":
            await asyncio.sleep(1.5)
            voicemail = str(
                behavior.get("voicemail_message")
                or "Olá. Tentamos entrar em contato. Por favor, retorne quando puder."
            )
            await session.say(voicemail, allow_interruptions=False).wait_for_playout()
            bridge.end_reason = "voicemail_left"
            session.shutdown(drain=True)
            return
    await session.say(greeting, allow_interruptions=True)


def run() -> None:
    cli.run_app(server)
