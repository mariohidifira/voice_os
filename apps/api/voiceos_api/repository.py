from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .db import SessionFactory
from .store import MemoryStore, store


class Repository(Protocol):
    async def list_agents(self, tenant_id: UUID) -> list[dict[str, Any]]: ...
    async def create_agent(self, tenant_id: UUID, name: str, user_id: str) -> dict[str, Any]: ...
    async def publish_agent(self, tenant_id: UUID, agent_id: UUID) -> dict[str, Any] | None: ...
    async def get_agent(self, tenant_id: UUID, agent_id: UUID) -> dict[str, Any] | None: ...
    async def create_call(self, tenant_id: UUID, agent_id: UUID, variables: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]: ...
    async def list_calls(self, tenant_id: UUID) -> list[dict[str, Any]]: ...
    async def create_tool(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]: ...
    async def get_runtime(self, agent_id: UUID) -> dict[str, Any] | None: ...


class PostgresRepository:
    @asynccontextmanager
    async def tenant_session(self, tenant_id: UUID) -> AsyncIterator[AsyncSession]:
        async with SessionFactory() as db, db.begin():
            await db.execute(text("SET LOCAL app.tenant_id = :tenant_id"), {"tenant_id": str(tenant_id)})
            yield db

    async def list_agents(self, tenant_id: UUID) -> list[dict[str, Any]]:
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(text("SELECT * FROM agents WHERE deleted_at IS NULL ORDER BY created_at DESC"))
            return [dict(row) for row in rows.mappings()]

    async def create_agent(self, tenant_id: UUID, name: str, user_id: str) -> dict[str, Any]:
        agent_id, draft_id = uuid4(), uuid4()
        async with self.tenant_session(tenant_id) as db:
            await db.execute(text("INSERT INTO agents(id,tenant_id,name,status,draft_version_id) VALUES(:id,:tenant,:name,'draft',:draft)"), {"id": agent_id, "tenant": tenant_id, "name": name, "draft": draft_id})
            await db.execute(text("INSERT INTO agent_versions(id,tenant_id,agent_id,version,system_prompt,greeting,llm,stt,tts,turn_config,behavior,rag,variables,created_by) VALUES(:id,:tenant,:agent,1,:prompt,:greeting,:llm,:stt,:tts,:turn,:behavior,:rag,'{}'::jsonb,:user)"), {"id": draft_id, "tenant": tenant_id, "agent": agent_id, "prompt": "Você é um agente de voz cordial e objetivo.", "greeting": f"Olá! Aqui é {name}. Como posso ajudar?", "llm": '{"provider":"anthropic","temperature":0.3,"max_tokens":350}', "stt": '{"provider":"deepgram","model":"nova-3"}', "tts": '{"provider":"elevenlabs","model":"eleven_flash_v2_5"}', "turn": '{"allow_interruptions":true}', "behavior": '{"max_call_duration_s":900}', "rag": '{"enabled":false}', "user": user_id})
        return (await self.get_agent(tenant_id, agent_id)) or {}

    async def get_agent(self, tenant_id: UUID, agent_id: UUID) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(text("SELECT * FROM agents WHERE id=:id AND deleted_at IS NULL"), {"id": agent_id})
            mapping = row.mappings().first()
            return dict(mapping) if mapping else None

    async def publish_agent(self, tenant_id: UUID, agent_id: UUID) -> dict[str, Any] | None:
        new_draft = uuid4()
        async with self.tenant_session(tenant_id) as db:
            current = (await db.execute(text("SELECT draft_version_id FROM agents WHERE id=:id FOR UPDATE"), {"id": agent_id})).scalar_one_or_none()
            if current is None:
                return None
            await db.execute(text("UPDATE agent_versions SET published_at=now() WHERE id=:version"), {"version": current})
            await db.execute(text("INSERT INTO agent_versions(id,tenant_id,agent_id,version,system_prompt,greeting,llm,stt,tts,turn_config,behavior,rag,variables,created_by) SELECT :new,tenant_id,agent_id,version+1,system_prompt,greeting,llm,stt,tts,turn_config,behavior,rag,variables,created_by FROM agent_versions WHERE id=:current"), {"new": new_draft, "current": current})
            await db.execute(text("UPDATE agents SET current_version_id=:current,draft_version_id=:draft,status='active',updated_at=now() WHERE id=:id"), {"current": current, "draft": new_draft, "id": agent_id})
        return await self.get_agent(tenant_id, agent_id)

    async def create_call(self, tenant_id: UUID, agent_id: UUID, variables: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
        call_id = uuid4()
        async with self.tenant_session(tenant_id) as db:
            await db.execute(text("INSERT INTO calls(id,tenant_id,agent_id,channel,status,variables,metadata,started_at) VALUES(:id,:tenant,:agent,'web','queued',CAST(:variables AS jsonb),CAST(:metadata AS jsonb),now())"), {"id": call_id, "tenant": tenant_id, "agent": agent_id, "variables": __import__('json').dumps(variables), "metadata": __import__('json').dumps(metadata)})
        return {"id": call_id, "tenant_id": tenant_id, "agent_id": agent_id, "channel": "web", "status": "queued", "variables": variables, "metadata": metadata}

    async def list_calls(self, tenant_id: UUID) -> list[dict[str, Any]]:
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(text("SELECT * FROM calls ORDER BY created_at DESC"))
            return [dict(row) for row in rows.mappings()]

    async def create_tool(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        import json

        tool_id = uuid4()
        async with self.tenant_session(tenant_id) as db:
            await db.execute(text("INSERT INTO tools(id,tenant_id,name,description,type,native_kind,parameters_schema,webhook,speak_before,is_async) VALUES(:id,:tenant,:name,:description,:type,:native_kind,CAST(:schema AS jsonb),CAST(:webhook AS jsonb),:speak_before,:is_async)"), {"id": tool_id, "tenant": tenant_id, "name": data["name"], "description": data["description"], "type": data["type"], "native_kind": data.get("native_kind"), "schema": json.dumps(data["parameters_schema"]), "webhook": json.dumps(data.get("webhook")), "speak_before": data.get("speak_before"), "is_async": data.get("async", False)})
        return {"id": tool_id, "tenant_id": tenant_id, **data}

    async def get_runtime(self, agent_id: UUID) -> dict[str, Any] | None:
        async with SessionFactory() as db, db.begin():
            await db.execute(text("SET LOCAL row_security = off"))
            row = await db.execute(text("SELECT a.id agent_id,a.tenant_id,a.name,v.* FROM agents a JOIN agent_versions v ON v.id=COALESCE(a.current_version_id,a.draft_version_id) WHERE a.id=:id AND a.deleted_at IS NULL"), {"id": agent_id})
            mapping = row.mappings().first()
            return dict(mapping) if mapping else None


class MemoryRepository:
    def __init__(self, memory: MemoryStore = store) -> None:
        self.memory = memory

    async def list_agents(self, tenant_id: UUID) -> list[dict[str, Any]]:
        return [a for a in self.memory.agents.values() if a["tenant_id"] == tenant_id]

    async def create_agent(self, tenant_id: UUID, name: str, user_id: str) -> dict[str, Any]:
        return self.memory.create_agent(tenant_id, name)

    async def get_agent(self, tenant_id: UUID, agent_id: UUID) -> dict[str, Any] | None:
        agent = self.memory.agents.get(agent_id)
        return agent if agent and agent["tenant_id"] == tenant_id else None

    async def publish_agent(self, tenant_id: UUID, agent_id: UUID) -> dict[str, Any] | None:
        agent = await self.get_agent(tenant_id, agent_id)
        if agent:
            agent["current_version_id"], agent["draft_version_id"], agent["status"] = agent["draft_version_id"], uuid4(), "active"
        return agent

    async def create_call(self, tenant_id: UUID, agent_id: UUID, variables: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
        call_id = uuid4()
        result = {"id": call_id, "tenant_id": tenant_id, "agent_id": agent_id, "channel": "web", "status": "queued", "metadata": metadata, "variables": variables, "created_at": datetime.now(UTC)}
        self.memory.calls[call_id] = result
        return result

    async def list_calls(self, tenant_id: UUID) -> list[dict[str, Any]]:
        return [c for c in self.memory.calls.values() if c["tenant_id"] == tenant_id]

    async def create_tool(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        tool_id = uuid4()
        result = {"id": tool_id, "tenant_id": tenant_id, **data}
        self.memory.tools[tool_id] = result
        return result

    async def get_runtime(self, agent_id: UUID) -> dict[str, Any] | None:
        return self.memory.agents.get(agent_id)


postgres_repository = PostgresRepository()


async def get_repository() -> Repository:
    return postgres_repository
