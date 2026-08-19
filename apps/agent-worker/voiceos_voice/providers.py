from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from .contracts import LLMResponse, ToolCall


@dataclass
class MockSTT:
    transcript: str = "Olá"
    name: str = "mock-stt"
    calls: int = 0

    async def transcribe(self, audio: bytes, *, language: str) -> str:
        self.calls += 1
        if audio.startswith(b"FAIL"):
            raise RuntimeError("mock STT failure")
        return self.transcript


@dataclass
class MockLLM:
    replies: list[LLMResponse] = field(default_factory=lambda: [LLMResponse(text="Como posso ajudar?")])
    name: str = "mock-llm"
    calls: int = 0

    async def complete(
        self, messages: list[dict[str, str]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        self.calls += 1
        if not self.replies:
            return LLMResponse(text="Posso ajudar em algo mais?")
        return self.replies.pop(0)

    @staticmethod
    def tool(name: str, arguments: dict[str, Any]) -> LLMResponse:
        return LLMResponse(tool_calls=(ToolCall("mock-call", name, arguments),))


@dataclass
class MockTTS:
    name: str = "mock-tts"
    chunks: list[str] = field(default_factory=list)

    async def synthesize(self, text: str, *, voice: str | None = None) -> AsyncIterator[bytes]:
        self.chunks.append(text)
        for sentence in text.split(". "):
            yield sentence.encode()


@dataclass
class MockRAG:
    documents: list[str] = field(default_factory=list)
    delay_s: float = 0

    async def query(self, text: str, *, top_k: int, min_score: float) -> list[str]:
        if self.delay_s:
            import asyncio

            await asyncio.sleep(self.delay_s)
        return self.documents[:top_k]
