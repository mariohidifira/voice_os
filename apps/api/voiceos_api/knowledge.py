import hashlib
import io
import math
import re
from html.parser import HTMLParser

import httpx

from .config import Settings, get_settings


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    chunks, start = [], 0
    while start < len(normalized):
        end = min(start + size, len(normalized))
        if end < len(normalized):
            boundary = normalized.rfind(" ", start, end)
            if boundary > start:
                end = boundary
        chunks.append(normalized[start:end].strip())
        if end == len(normalized):
            break
        start = max(start + 1, end - overlap)
    return chunks


class Embeddings:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings, self.transport = settings, transport

    async def create(self, texts: list[str], model: str) -> list[list[float]]:
        if self.settings.openai_api_key:
            async with httpx.AsyncClient(transport=self.transport, timeout=30) as client:
                response = await client.post("https://api.openai.com/v1/embeddings", headers={"Authorization": f"Bearer {self.settings.openai_api_key}"}, json={"model": model, "input": texts, "dimensions": 1536})
                response.raise_for_status()
                return [item["embedding"] for item in response.json()["data"]]
        if self.settings.app_env not in {"dev", "test"}:
            raise RuntimeError("OPENAI_API_KEY is required for document ingestion")
        return [self._deterministic(text) for text in texts]

    @staticmethod
    def _deterministic(text: str) -> list[float]:
        digest = hashlib.sha256(text.encode()).digest()
        values = [((digest[index % len(digest)] / 255) * 2) - 1 for index in range(1536)]
        norm = math.sqrt(sum(value * value for value in values)) or 1
        return [value / norm for value in values]


async def extract_url(url: str) -> str:
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
    extractor = _TextExtractor()
    extractor.feed(response.text)
    return " ".join(extractor.parts)


def extract_bytes(content: bytes, mime: str | None, name: str) -> str:
    kind = (mime or "").lower()
    suffix = name.lower().rsplit(".", 1)[-1] if "." in name else ""
    if "pdf" in kind or suffix == "pdf":
        from pypdf import PdfReader

        return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)
    if "wordprocessingml" in kind or suffix == "docx":
        from docx import Document

        return "\n".join(paragraph.text for paragraph in Document(io.BytesIO(content)).paragraphs)
    decoded = content.decode("utf-8", errors="replace")
    if "html" in kind or suffix in {"html", "htm"}:
        extractor = _TextExtractor()
        extractor.feed(decoded)
        return " ".join(extractor.parts)
    return decoded


def get_embeddings() -> Embeddings:
    return Embeddings(get_settings())


def cosine_similarity(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))
