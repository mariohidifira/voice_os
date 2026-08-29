import httpx
import pytest
from voiceos_api.config import Settings
from voiceos_api.knowledge import Embeddings, chunk_text, cosine_similarity, extract_bytes


def test_chunk_text_respects_overlap_and_boundaries() -> None:
    chunks = chunk_text("um dois três quatro cinco seis sete oito", 20, 5)
    assert len(chunks) > 1
    assert all(len(chunk) <= 20 for chunk in chunks)
    assert chunk_text("   ", 100, 10) == []


def test_extract_html_upload() -> None:
    assert "Prazo de sete dias" in extract_bytes(b"<p>Prazo de sete dias</p>", "text/html", "faq.html")


def test_embeddings_deterministic_and_similarity() -> None:
    async def exercise() -> None:
        embeddings = Embeddings(Settings(app_env="dev"))
        values = await embeddings.create(["olá"], "test-model")
        assert len(values) == 1 and len(values[0]) == 1536
        assert cosine_similarity(values[0], values[0]) == pytest.approx(1.0)

    import asyncio

    asyncio.run(exercise())


@pytest.mark.asyncio
async def test_embeddings_openai_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/v1/embeddings")
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2]}]})

    embeddings = Embeddings(Settings(app_env="prod", openai_api_key="test"), httpx.MockTransport(handler))
    assert await embeddings.create(["hello"], "text-embedding-3-small") == [[0.1, 0.2]]


def test_extract_plain_text_and_cosine() -> None:
    assert extract_bytes(b"plain text", None, "notes.txt") == "plain text"
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
