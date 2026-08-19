from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class LLMResponse:
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class VoiceEvent:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)


class STTProvider(Protocol):
    name: str

    async def transcribe(self, audio: bytes, *, language: str) -> str: ...


class LLMProvider(Protocol):
    name: str

    async def complete(
        self, messages: list[dict[str, str]], tools: list[dict[str, Any]]
    ) -> LLMResponse: ...


class TTSProvider(Protocol):
    name: str

    def synthesize(self, text: str, *, voice: str | None = None) -> AsyncIterator[bytes]: ...


ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class RAGProvider(Protocol):
    async def query(self, text: str, *, top_k: int, min_score: float) -> list[str]: ...
