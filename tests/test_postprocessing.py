import httpx
import pytest
from voiceos_api.postprocessing import AnthropicPostprocessor


@pytest.mark.asyncio
async def test_postprocessor_sends_transcript_and_validates_structured_result() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "secret"
        body = __import__("json").loads(request.content)
        assert "user: Preciso cancelar" in body["messages"][0]["content"]
        return httpx.Response(
            200,
            json={
                "content": [
                    {
                        "text": '{"summary":"Cliente pediu cancelamento.","outcome":{"resolved":true,"intent":"cancelamento","sentiment":"neutral","next_action":null,"tags":["cancelamento"]}}'
                    }
                ]
            },
        )

    processor = AnthropicPostprocessor("secret", transport=httpx.MockTransport(handler))
    result = await processor.process({"turns": [{"role": "user", "text": "Preciso cancelar"}]})
    assert result["summary"] == "Cliente pediu cancelamento."
    assert result["outcome"]["resolved"] is True


@pytest.mark.asyncio
async def test_postprocessor_retries_invalid_provider_response() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, json={"content": [{"text": "not-json"}]})

    processor = AnthropicPostprocessor("secret", transport=httpx.MockTransport(handler))
    with pytest.raises(RuntimeError, match="3 attempts"):
        await processor.process({"turns": []})
    assert attempts == 3
