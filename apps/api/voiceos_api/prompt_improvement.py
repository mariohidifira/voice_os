import asyncio
import re
from functools import lru_cache
from typing import Protocol

import httpx

from .config import get_settings

VARIABLE_PATTERN = re.compile(r"{{\s*[^{}]+?\s*}}")


class PromptImprover(Protocol):
    async def improve(self, prompt: str) -> str: ...


class AnthropicPromptImprover:
    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.transport = transport

    async def improve(self, prompt: str) -> str:
        variables = set(VARIABLE_PATTERN.findall(prompt))
        instruction = (
            "Reescreva o system prompt abaixo para um agente de voz em pt-BR. Preserve todas as variáveis Jinja "
            "exatamente, mantenha o objetivo e as regras de negócio, elimine ambiguidades e organize instruções para "
            "respostas curtas, naturais, sem markdown e com uso seguro de ferramentas. Retorne somente o prompt final, "
            "sem comentários nem cercas de código. Limite de 6000 caracteres.\n\nPROMPT ATUAL:\n"
            + prompt
        )
        error: Exception | None = None
        for attempt in range(3):
            try:
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
                            "max_tokens": 1800,
                            "temperature": 0.2,
                            "messages": [{"role": "user", "content": instruction}],
                        },
                    )
                    response.raise_for_status()
                    improved = (
                        str(response.json()["content"][0]["text"])
                        .removeprefix("```")
                        .removesuffix("```")
                        .strip()
                    )
                    if (
                        not improved
                        or len(improved) > 6000
                        or not variables.issubset(set(VARIABLE_PATTERN.findall(improved)))
                    ):
                        raise ValueError("improved prompt is invalid or dropped template variables")
                    return improved
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
                error = exc
                if attempt < 2:
                    await asyncio.sleep(0.1 * (attempt + 1))
        raise RuntimeError(f"prompt improvement failed after 3 attempts: {error}") from error


class UnavailablePromptImprover:
    async def improve(self, prompt: str) -> str:
        raise RuntimeError("ANTHROPIC_API_KEY is required for prompt improvement")


@lru_cache
def get_prompt_improver() -> PromptImprover:
    settings = get_settings()
    if not settings.anthropic_api_key:
        return UnavailablePromptImprover()
    return AnthropicPromptImprover(settings.anthropic_api_key)
