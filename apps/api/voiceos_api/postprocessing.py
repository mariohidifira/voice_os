import asyncio
import json
from typing import Any, Protocol

import httpx

from .config import get_settings


class Postprocessor(Protocol):
    async def process(self, call: dict[str, Any]) -> dict[str, Any]: ...


class AnthropicPostprocessor:
    def __init__(
        self,
        api_key: str,
        model: str = "claude-haiku-4-5",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.transport = transport

    async def process(self, call: dict[str, Any]) -> dict[str, Any]:
        transcript = "\n".join(
            f"{turn['role']}: {turn['text']}" for turn in call.get("turns", [])
        )[-30_000:]
        prompt = (
            "Analise a conversa abaixo. Retorne somente JSON válido com: "
            '"summary" (string curta) e "outcome" (objeto com resolved boolean, intent string, '
            'sentiment "positive|neutral|negative", next_action string|null e tags array de strings).\n\n'
            + transcript
        )
        error: Exception | None = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(transport=self.transport, timeout=15) as client:
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
                            "temperature": 0,
                            "messages": [{"role": "user", "content": prompt}],
                        },
                    )
                    response.raise_for_status()
                    text = str(response.json()["content"][0]["text"])
                    result = json.loads(text.removeprefix("```json").removesuffix("```").strip())
                    if not isinstance(result.get("summary"), str) or not isinstance(result.get("outcome"), dict):
                        raise ValueError("invalid postprocessing schema")
                    return {"summary": result["summary"][:2000], "outcome": result["outcome"]}
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
                error = exc
                if attempt < 2:
                    await asyncio.sleep(0.1 * (attempt + 1))
        raise RuntimeError(f"postprocessing failed after 3 attempts: {error}") from error


def get_postprocessor() -> Postprocessor:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required for postprocessing")
    return AnthropicPostprocessor(settings.anthropic_api_key, settings.anthropic_postprocess_model)
