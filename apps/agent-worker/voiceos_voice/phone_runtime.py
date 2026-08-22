import json
from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
    "segunda": 0,
    "terca": 1,
    "quarta": 2,
    "quinta": 3,
    "sexta": 4,
    "sabado": 5,
    "domingo": 6,
}


def business_hours_open(config: dict[str, object], now: datetime) -> bool:
    if not config or config.get("enabled") is False:
        return True
    try:
        local = now.astimezone(ZoneInfo(str(config.get("timezone") or "America/Sao_Paulo")))
    except ZoneInfoNotFoundError:
        return False
    raw_days = config.get("days") or [0, 1, 2, 3, 4]
    if not isinstance(raw_days, list):
        return False
    days = {
        int(day) if isinstance(day, int) else WEEKDAYS.get(str(day).lower(), -1)
        for day in raw_days
    }
    if local.weekday() not in days:
        return False
    try:
        start_hour, start_minute = map(int, str(config.get("start") or "08:00").split(":"))
        end_hour, end_minute = map(int, str(config.get("end") or "20:00").split(":"))
        start = local.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
        end = local.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
    except (TypeError, ValueError):
        return False
    return start <= local < end


class AMDClassifier(Protocol):
    async def classify(self, transcript: str) -> str: ...


class HeuristicAMDClassifier:
    async def classify(self, transcript: str) -> str:
        normalized = transcript.casefold()
        voicemail = (
            "deixe seu recado",
            "deixe uma mensagem",
            "após o sinal",
            "apos o sinal",
            "caixa postal",
            "leave a message",
            "after the tone",
            "beep",
        )
        ivr = (
            "digite",
            "pressione",
            "tecle",
            "para falar com",
            "press one",
            "main menu",
        )
        if any(marker in normalized for marker in voicemail):
            return "voicemail"
        if any(marker in normalized for marker in ivr):
            return "ivr"
        return "human"


class AnthropicAMDClassifier:
    def __init__(
        self,
        api_key: str,
        model: str = "claude-haiku-4-5",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.transport = transport

    async def classify(self, transcript: str) -> str:
        prompt = (
            "Classifique os primeiros segundos de uma chamada outbound. "
            "Responda somente JSON: {\"classification\":\"human|voicemail|ivr\"}. "
            f"Transcrição: {transcript[:2000]!r}"
        )
        async with httpx.AsyncClient(transport=self.transport, timeout=8) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 30,
                    "temperature": 0,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
        raw = str(response.json()["content"][0]["text"])
        result = json.loads(raw.removeprefix("```json").removesuffix("```").strip())
        classification = str(result.get("classification") or "")
        if classification not in {"human", "voicemail", "ivr"}:
            raise ValueError("invalid AMD classification")
        return classification
