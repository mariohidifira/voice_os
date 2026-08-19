from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4


class MemoryStore:
    """Deterministic dev adapter. Production endpoints use the same contract with Postgres."""

    def __init__(self) -> None:
        self.agents: dict[UUID, dict[str, Any]] = {}
        self.agent_versions: dict[UUID, dict[str, Any]] = {}
        self.calls: dict[UUID, dict[str, Any]] = {}
        self.tools: dict[UUID, dict[str, Any]] = {}

    def create_agent(self, tenant_id: UUID, name: str) -> dict[str, Any]:
        agent_id, draft_id = uuid4(), uuid4()
        now = datetime.now(UTC)
        result = {"id": agent_id, "tenant_id": tenant_id, "name": name, "status": "draft", "current_version_id": None, "draft_version_id": draft_id, "created_at": now, "updated_at": now}
        self.agents[agent_id] = result
        self.agent_versions[draft_id] = {
            "id": draft_id,
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "version": 1,
            "published_at": None,
            "system_prompt": "Você é um agente de voz cordial e objetivo.",
            "greeting": f"Olá! Aqui é {name}. Como posso ajudar?",
            "language": "pt-BR",
            "extra_languages": [],
            "llm": {"provider": "anthropic", "temperature": 0.3, "max_tokens": 350},
            "stt": {"provider": "deepgram", "model": "nova-3"},
            "tts": {"provider": "elevenlabs", "model": "eleven_flash_v2_5"},
            "turn_config": {"allow_interruptions": True},
            "behavior": {"max_call_duration_s": 900},
            "knowledge_base_id": None,
            "rag": {"enabled": False},
            "variables": {},
            "created_at": now,
            "updated_at": now,
        }
        return result


store = MemoryStore()
