import httpx
import pytest
from voiceos_api.prompt_improvement import AnthropicPromptImprover


@pytest.mark.asyncio
async def test_prompt_improver_preserves_jinja_variables() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "secret"
        return httpx.Response(
            200,
            json={
                "content": [
                    {"text": "Você é {{ agent.name }} e atende {{ tenant.name }} com objetividade."}
                ]
            },
        )

    improver = AnthropicPromptImprover("secret", transport=httpx.MockTransport(handler))
    result = await improver.improve("Você é {{ agent.name }} da empresa {{ tenant.name }}.")
    assert "{{ agent.name }}" in result and "{{ tenant.name }}" in result


@pytest.mark.asyncio
async def test_prompt_improver_retries_when_provider_drops_variable() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            200, json={"content": [{"text": "Prompt sem a variável obrigatória."}]}
        )

    improver = AnthropicPromptImprover("secret", transport=httpx.MockTransport(handler))
    with pytest.raises(RuntimeError, match="3 attempts"):
        await improver.improve("Atenda como {{ agent.name }} com educação.")
    assert attempts == 3
