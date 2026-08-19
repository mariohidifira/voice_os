from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4


class MemoryStore:
    """Deterministic dev adapter. Production endpoints use the same contract with Postgres."""

    def __init__(self) -> None:
        self.agents: dict[UUID, dict[str, Any]] = {}
        self.calls: dict[UUID, dict[str, Any]] = {}
        self.tools: dict[UUID, dict[str, Any]] = {}

    def create_agent(self, tenant_id: UUID, name: str) -> dict[str, Any]:
        agent_id, draft_id = uuid4(), uuid4()
        now = datetime.now(UTC)
        result = {"id": agent_id, "tenant_id": tenant_id, "name": name, "status": "draft", "current_version_id": None, "draft_version_id": draft_id, "created_at": now, "updated_at": now}
        self.agents[agent_id] = result
        return result


store = MemoryStore()

