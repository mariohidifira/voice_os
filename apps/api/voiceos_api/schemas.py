from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


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


class AgentToolsSet(BaseModel):
    tool_ids: list[UUID]


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


class ToolPatch(BaseModel):
    name: str | None = None
    description: str | None = Field(default=None, max_length=300)
    native_kind: str | None = None
    parameters_schema: dict[str, Any] | None = None
    webhook: dict[str, Any] | None = None
    speak_before: str | None = None
    async_: bool | None = Field(default=None, alias="async")


class ToolTestRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)
    session_variables: dict[str, Any] = Field(default_factory=dict)
    end_user: dict[str, Any] = Field(default_factory=dict)


class InternalToolExecute(ToolTestRequest):
    tool_id: UUID
    call_id: UUID


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    embedding_model: str = "text-embedding-3-small"
    chunk_size: int = Field(default=800, ge=100, le=4000)
    chunk_overlap: int = Field(default=120, ge=0, le=1000)

    @field_validator("chunk_overlap")
    @classmethod
    def overlap_is_bounded(cls, value: int, info: Any) -> int:
        if value >= info.data.get("chunk_size", 800):
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return value


class KnowledgeBasePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    chunk_size: int | None = Field(default=None, ge=100, le=4000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=1000)


class DocumentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    text: str | None = None
    url: str | None = None

    @model_validator(mode="after")
    def require_one_source(self) -> "DocumentCreate":
        if not self.url and not self.text:
            raise ValueError("text or url is required")
        return self


class KnowledgeQuery(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=0.65, ge=0, le=1)


class InternalRagQuery(KnowledgeQuery):
    knowledge_base_id: UUID


class SecretCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=16_384)


class MemberCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: str = "viewer"

    @field_validator("role")
    @classmethod
    def valid_role(cls, value: str) -> str:
        if value not in {"owner", "admin", "developer", "operator", "viewer"}:
            raise ValueError("invalid member role")
        return value


class MemberPatch(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def valid_role(cls, value: str) -> str:
        return MemberCreate.valid_role(value)


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scope: str = "secret"
    allowed_origins: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("scope")
    @classmethod
    def valid_scope(cls, value: str) -> str:
        if value not in {"public", "secret"}:
            raise ValueError("scope must be public or secret")
        return value

    @model_validator(mode="after")
    def public_key_requires_origins(self) -> "ApiKeyCreate":
        if self.scope == "public" and not self.allowed_origins:
            raise ValueError("public keys require at least one allowed origin")
        return self


class CallEvent(BaseModel):
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    at: datetime


class CallPatch(BaseModel):
    status: str | None = None
    end_reason: str | None = None
    livekit_room: str | None = None
    answered_at: datetime | None = None
    ended_at: datetime | None = None
    duration_s: int | None = Field(default=None, ge=0)
    billable_seconds: int | None = Field(default=None, ge=0)
    cost: dict[str, Any] | None = None
    latency: dict[str, Any] | None = None
    summary: str | None = None
    outcome: dict[str, Any] | None = None
    variables: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class InternalCallCreate(BaseModel):
    tenant_id: UUID
    agent_id: UUID
    agent_version_id: UUID | None = None
    channel: str = "web"
    livekit_room: str | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CallEventBatch(BaseModel):
    events: list[CallEvent] = Field(min_length=1, max_length=100)


class CallTurnCreate(BaseModel):
    id: UUID | None = None
    ordinal: int = Field(ge=0)
    role: str
    text: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    interrupted: bool = False
    ttfb_ms: int | None = Field(default=None, ge=0)
    stt_confidence: float | None = Field(default=None, ge=0, le=1)
    audio_offset_ms: int = Field(default=0, ge=0)


class CallTurnBatch(BaseModel):
    turns: list[CallTurnCreate] = Field(min_length=1, max_length=100)


class CallToolCallCreate(BaseModel):
    id: UUID | None = None
    turn_id: UUID | None = None
    tool_id: UUID | None = None
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any] | None = None
    status: str
    duration_ms: int | None = Field(default=None, ge=0)
    started_at: datetime | None = None
