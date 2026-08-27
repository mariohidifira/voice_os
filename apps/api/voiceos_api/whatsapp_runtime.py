import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from .config import Settings
from .voice_preview import VoicePreview

ToolCallback = Callable[[dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any]]]


def handoff_requested(text: str) -> bool:
    lowered = text.casefold()
    return any(
        phrase in lowered
        for phrase in (
            "humano",
            "atendente",
            "pessoa",
            "suporte humano",
            "falar com alguem",
        )
    )


def fallback_reply(
    runtime: dict[str, Any] | None, user_text: str, inbound_type: str
) -> tuple[str, bool]:
    greeting = str((runtime or {}).get("greeting") or "Olá! Como posso ajudar?")
    cleaned = user_text.strip()
    if handoff_requested(cleaned):
        return ("Vou encaminhar sua conversa para um atendente humano agora.", True)
    if not cleaned:
        if inbound_type == "audio":
            return (
                "Recebi sua mensagem de voz. Pode me dizer em texto ou áudio o que você precisa?",
                False,
            )
        return (greeting, False)
    if inbound_type == "audio":
        return (f"Recebi sua mensagem de voz. {cleaned}", False)
    return (f"Recebi sua mensagem: {cleaned}", False)


class DeepgramTranscriber:
    def __init__(
        self, api_key: str, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.api_key = api_key
        self.transport = transport

    async def transcribe(self, audio: bytes, model: str = "nova-3") -> str:
        async with httpx.AsyncClient(transport=self.transport, timeout=15) as client:
            response = await client.post(
                "https://api.deepgram.com/v1/listen",
                params={"model": model, "smart_format": "true"},
                headers={
                    "Authorization": f"Token {self.api_key}",
                    "Content-Type": "application/octet-stream",
                },
                content=audio,
            )
            response.raise_for_status()
        payload = response.json()
        return str(
            payload["results"]["channels"][0]["alternatives"][0].get("transcript") or ""
        ).strip()


class OpenAITranscriber:
    def __init__(
        self, api_key: str, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.api_key = api_key
        self.transport = transport

    async def transcribe(self, audio: bytes, language: str | None = None) -> str:
        data = {"model": "whisper-1"}
        if language:
            data["language"] = language
        async with httpx.AsyncClient(transport=self.transport, timeout=30) as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                data=data,
                files={"file": ("message.ogg", audio, "audio/ogg")},
            )
            response.raise_for_status()
        return str(response.json().get("text") or "").strip()


class AnthropicWhatsAppResponder:
    def __init__(
        self,
        api_key: str,
        model: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.transport = transport

    async def _request(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(transport=self.transport, timeout=20) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 500,
                    "temperature": 0.2,
                    "system": system,
                    "messages": messages,
                    "tools": tools,
                },
            )
            response.raise_for_status()
        return dict(response.json())

    async def complete(
        self,
        runtime: dict[str, Any] | None,
        user_text: str,
        inbound_type: str,
        execute_tool: ToolCallback | None,
    ) -> tuple[str, bool, list[dict[str, Any]]]:
        system_prompt = str((runtime or {}).get("system_prompt") or "").strip()
        greeting = str((runtime or {}).get("greeting") or "Olá! Como posso ajudar?")
        system = (
            f"{system_prompt}\n\n"
            "Você está respondendo no WhatsApp. Responda de forma objetiva, natural e curta. "
            "Se o usuário pedir humano, responda com uma frase curta confirmando o handoff. "
            "Se houver tool adequada, você pode usá-la antes de responder."
        ).strip()
        tools = [
            {
                "name": str(tool["name"]),
                "description": str(tool.get("description") or tool["name"]),
                "input_schema": dict(tool.get("parameters_schema") or {}),
            }
            for tool in list((runtime or {}).get("tools") or [])
            if tool.get("name") and isinstance(tool.get("parameters_schema"), dict)
        ]
        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": f"Canal: WhatsApp\nTipo de entrada: {inbound_type}\nMensagem: {user_text}",
            }
        ]
        response = await self._request(system=system, messages=messages, tools=tools)
        content = list(response.get("content") or [])
        text_parts = [str(block.get("text") or "") for block in content if block.get("type") == "text"]
        tool_calls: list[dict[str, Any]] = []
        pending_results: list[dict[str, Any]] = []
        if execute_tool:
            for block in content:
                if block.get("type") != "tool_use":
                    continue
                name = str(block.get("name") or "")
                tool = next(
                    (item for item in list((runtime or {}).get("tools") or []) if item.get("name") == name),
                    None,
                )
                if not tool:
                    continue
                arguments = dict(block.get("input") or {})
                result = await execute_tool(tool, arguments)
                tool_calls.append(
                    {
                        "name": name,
                        "arguments": arguments,
                        "result": result,
                        "status": "error" if "error" in result else "ok",
                    }
                )
                pending_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": str(block["id"]),
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    }
                )
        if pending_results:
            follow_up = await self._request(
                system=system,
                messages=[
                    *messages,
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": pending_results},
                ],
                tools=tools,
            )
            text_parts.extend(
                str(block.get("text") or "")
                for block in list(follow_up.get("content") or [])
                if block.get("type") == "text"
            )
        reply = " ".join(part.strip() for part in text_parts if part.strip()).strip() or greeting
        return reply[:4096], handoff_requested(user_text) or handoff_requested(reply), tool_calls


class ElevenLabsAudioReply:
    def __init__(
        self, api_key: str, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.api_key = api_key
        self.transport = transport

    async def synthesize(
        self, voice_id: str, text: str, model_id: str, speed: float = 1.0
    ) -> bytes:
        async with httpx.AsyncClient(transport=self.transport, timeout=30) as client:
            response = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream",
                params={"output_format": "ogg_44100_128"},
                headers={"xi-api-key": self.api_key},
                json={
                    "text": text,
                    "model_id": model_id,
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                        "speed": speed,
                    },
                },
            )
            response.raise_for_status()
        return response.content


async def transcribe_whatsapp_audio(
    settings: Settings,
    runtime: dict[str, Any] | None,
    audio: bytes,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    stt = dict((runtime or {}).get("stt") or {})
    language = str((runtime or {}).get("language") or "pt")
    if settings.deepgram_api_key:
        try:
            return await DeepgramTranscriber(settings.deepgram_api_key, transport).transcribe(
                audio, model=str(stt.get("model") or "nova-3")
            )
        except httpx.HTTPError:
            pass
    if settings.openai_api_key:
        return await OpenAITranscriber(settings.openai_api_key, transport).transcribe(
            audio, language=language.split("-", 1)[0]
        )
    raise RuntimeError("No STT provider configured for WhatsApp audio")


async def generate_whatsapp_reply(
    settings: Settings,
    runtime: dict[str, Any] | None,
    user_text: str,
    inbound_type: str,
    execute_tool: ToolCallback | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[str, bool, list[dict[str, Any]]]:
    llm = dict((runtime or {}).get("llm") or {})
    if settings.anthropic_api_key and (llm.get("provider") in {None, "", "anthropic"}):
        try:
            responder = AnthropicWhatsAppResponder(
                settings.anthropic_api_key,
                model=str(llm.get("model") or settings.anthropic_postprocess_model),
                transport=transport,
            )
            return await responder.complete(runtime, user_text, inbound_type, execute_tool)
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass
    reply, handoff = fallback_reply(runtime, user_text, inbound_type)
    return reply, handoff, []


async def synthesize_whatsapp_audio(
    settings: Settings,
    runtime: dict[str, Any] | None,
    text: str,
    voice_preview: VoicePreview,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[bytes, str, str] | None:
    tts = dict((runtime or {}).get("tts") or {})
    voice_id = str(tts.get("voice_id") or "")
    model_id = str(tts.get("model") or "eleven_flash_v2_5")
    if settings.elevenlabs_api_key and voice_id:
        try:
            audio = await ElevenLabsAudioReply(settings.elevenlabs_api_key, transport).synthesize(
                voice_id, text, model_id
            )
            return audio, "reply.ogg", "audio/ogg"
        except httpx.HTTPError:
            pass
    if voice_preview.configured and voice_id:
        audio = await voice_preview.synthesize(voice_id, text, 1.0)
        return audio, "reply.mp3", "audio/mpeg"
    return None


async def guarded_sleep() -> None:
    await asyncio.sleep(0.1)
