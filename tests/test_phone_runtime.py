from datetime import UTC, datetime

import httpx
import pytest
from voiceos_voice.phone_runtime import (
    AnthropicAMDClassifier,
    HeuristicAMDClassifier,
    business_hours_open,
)


def test_business_hours_respects_timezone_days_and_window() -> None:
    config = {
        "timezone": "America/Sao_Paulo",
        "days": ["segunda", "terca", "quarta", "quinta", "sexta"],
        "start": "08:00",
        "end": "18:00",
    }
    assert business_hours_open(config, datetime(2026, 8, 24, 14, 0, tzinfo=UTC))
    assert not business_hours_open(config, datetime(2026, 8, 24, 22, 0, tzinfo=UTC))
    assert not business_hours_open(config, datetime(2026, 8, 23, 14, 0, tzinfo=UTC))
    assert business_hours_open({}, datetime.now(UTC))


@pytest.mark.asyncio
async def test_amd_heuristics_distinguish_human_voicemail_and_ivr() -> None:
    classifier = HeuristicAMDClassifier()
    assert await classifier.classify("Alô, quem fala?") == "human"
    assert await classifier.classify("Deixe sua mensagem após o sinal") == "voicemail"
    assert await classifier.classify("Para vendas, pressione um") == "ivr"


@pytest.mark.asyncio
async def test_anthropic_amd_uses_haiku_contract() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"content": [{"text": '{"classification":"voicemail"}'}]},
        )

    classifier = AnthropicAMDClassifier(
        "anthropic-key", transport=httpx.MockTransport(handler)
    )
    assert await classifier.classify("Caixa postal") == "voicemail"
    payload = __import__("json").loads(requests[0].content)
    assert payload["model"] == "claude-haiku-4-5"
    assert payload["temperature"] == 0
