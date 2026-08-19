from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class AgentPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    status: str | None = None


class AgentDraftPatch(BaseModel):
    system_prompt: str | None = Field(default=None, max_length=6000)
    greeting: str | None = Field(default=None, max_length=1000)
    language: str | None = Field(default=None, min_length=2, max_length=20)
    extra_languages: list[str] | None = None
    llm: dict[str, Any] | None = None
    stt: dict[str, Any] | None = None
    tts: dict[str, Any] | None = None
    turn_config: dict[str, Any] | None = None
    behavior: dict[str, Any] | None = None
    knowledge_base_id: UUID | None = None
    rag: dict[str, Any] | None = None
    variables: dict[str, Any] | None = None


class AgentRollback(BaseModel):
    version_id: UUID


class SessionCreate(BaseModel):
    agent_id: UUID
    end_user: dict[str, Any] | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolCreate(BaseModel):
    name: str
    description: str = Field(max_length=300)
    type: str
    native_kind: str | None = None
    parameters_schema: dict[str, Any]
    webhook: dict[str, Any] | None = None
    speak_before: str | None = None
    async_: bool = Field(default=False, alias="async")

    @field_validator("name")
    @classmethod
    def snake_case(cls, value: str) -> str:
        if len(value) > 40 or not value.replace("_", "").isalnum() or value.lower() != value:
            raise ValueError("name must be snake_case and <= 40 characters")
        return value


class CallEvent(BaseModel):
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    at: datetime
