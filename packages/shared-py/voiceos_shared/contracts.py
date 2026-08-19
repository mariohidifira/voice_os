from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class RuntimeConfig(BaseModel):
    tenant_id: UUID
    agent_id: UUID
    version_id: UUID
    system_prompt: str
    greeting: str
    language: str = "pt-BR"
    llm: dict[str, Any]
    stt: dict[str, Any]
    tts: dict[str, Any]
    turn: dict[str, Any]
    behavior: dict[str, Any]
    rag: dict[str, Any]
    tools: list[dict[str, Any]] = Field(default_factory=list)

