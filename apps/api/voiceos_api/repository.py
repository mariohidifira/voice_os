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
    async def get_agent_detail(self, tenant_id: UUID, agent_id: UUID) -> dict[str, Any] | None: ...
    async def update_agent(self, tenant_id: UUID, agent_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None: ...
    async def delete_agent(self, tenant_id: UUID, agent_id: UUID) -> bool: ...
    async def list_versions(self, tenant_id: UUID, agent_id: UUID) -> list[dict[str, Any]]: ...
    async def get_version(self, tenant_id: UUID, agent_id: UUID, version_id: UUID) -> dict[str, Any] | None: ...
    async def update_draft(self, tenant_id: UUID, agent_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None: ...
    async def rollback_agent(self, tenant_id: UUID, agent_id: UUID, version_id: UUID) -> dict[str, Any] | None: ...
    async def upsert_end_user(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]: ...
    async def create_call(self, tenant_id: UUID, agent_id: UUID, variables: dict[str, Any], metadata: dict[str, Any], *, agent_version_id: UUID | None = None, end_user_id: UUID | None = None) -> dict[str, Any]: ...
    async def list_calls(self, tenant_id: UUID, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]: ...
    async def get_call(self, tenant_id: UUID, call_id: UUID) -> dict[str, Any] | None: ...
    async def get_call_detail(self, tenant_id: UUID, call_id: UUID) -> dict[str, Any] | None: ...
    async def update_call(self, tenant_id: UUID, call_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None: ...
    async def create_internal_call(self, data: dict[str, Any]) -> dict[str, Any]: ...
    async def update_internal_call(self, call_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None: ...
    async def append_call_events(self, call_id: UUID, events: list[dict[str, Any]]) -> int: ...
    async def append_call_turns(self, call_id: UUID, turns: list[dict[str, Any]]) -> int: ...
    async def append_call_tool_call(self, call_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None: ...
    async def get_call_tenant(self, call_id: UUID) -> UUID | None: ...
    async def upsert_call_recording(self, call_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None: ...
    async def create_tool(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]: ...
    async def list_tools(self, tenant_id: UUID) -> list[dict[str, Any]]: ...
    async def get_tool(self, tenant_id: UUID, tool_id: UUID) -> dict[str, Any] | None: ...
    async def update_tool(self, tenant_id: UUID, tool_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None: ...
    async def delete_tool(self, tenant_id: UUID, tool_id: UUID) -> bool: ...
    async def set_draft_tools(self, tenant_id: UUID, agent_id: UUID, tool_ids: list[UUID]) -> list[dict[str, Any]] | None: ...
    async def get_runtime(self, agent_id: UUID, version: str = "current") -> dict[str, Any] | None: ...
    async def list_knowledge_bases(self, tenant_id: UUID) -> list[dict[str, Any]]: ...
    async def create_knowledge_base(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]: ...
    async def get_knowledge_base(self, tenant_id: UUID, kb_id: UUID) -> dict[str, Any] | None: ...
    async def update_knowledge_base(self, tenant_id: UUID, kb_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None: ...
    async def delete_knowledge_base(self, tenant_id: UUID, kb_id: UUID) -> bool: ...
    async def list_documents(self, tenant_id: UUID, kb_id: UUID) -> list[dict[str, Any]]: ...
    async def create_document(self, tenant_id: UUID, kb_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None: ...
    async def delete_document(self, tenant_id: UUID, kb_id: UUID, document_id: UUID) -> bool: ...
    async def complete_document(self, tenant_id: UUID, document_id: UUID, chunks: list[dict[str, Any]]) -> None: ...
    async def fail_document(self, tenant_id: UUID, document_id: UUID, error: str) -> None: ...
    async def query_chunks(self, tenant_id: UUID, kb_id: UUID, embedding: list[float], top_k: int, min_score: float) -> list[dict[str, Any]]: ...
    async def get_knowledge_base_tenant(self, kb_id: UUID) -> UUID | None: ...
    async def create_secret(self, tenant_id: UUID, name: str, ciphertext: bytes, key_id: str) -> dict[str, Any]: ...
    async def list_secrets(self, tenant_id: UUID) -> list[dict[str, Any]]: ...
    async def get_secret(self, tenant_id: UUID, secret_id: UUID) -> dict[str, Any] | None: ...
    async def delete_secret(self, tenant_id: UUID, secret_id: UUID) -> bool: ...
    async def get_integration(self, tenant_id: UUID, provider: str) -> dict[str, Any] | None: ...
    async def upsert_integration(self, tenant_id: UUID, provider: str, data: dict[str, Any]) -> dict[str, Any]: ...


class PostgresRepository:
    @asynccontextmanager
    async def tenant_session(self, tenant_id: UUID) -> AsyncIterator[AsyncSession]:
        async with SessionFactory() as db, db.begin():
            await db.execute(
                text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
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

    async def get_agent_detail(self, tenant_id: UUID, agent_id: UUID) -> dict[str, Any] | None:
        agent = await self.get_agent(tenant_id, agent_id)
        if not agent:
            return None
        versions = await self.list_versions(tenant_id, agent_id)
        by_id = {version["id"]: version for version in versions}
        return {
            **agent,
            "draft": by_id.get(agent["draft_version_id"]),
            "current": by_id.get(agent["current_version_id"]),
        }

    async def update_agent(self, tenant_id: UUID, agent_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        assignments = []
        params: dict[str, Any] = {"id": agent_id}
        for field in ("name", "status"):
            if field in data:
                assignments.append(f"{field}=:{field}")
                params[field] = data[field]
        if not assignments:
            return await self.get_agent(tenant_id, agent_id)
        async with self.tenant_session(tenant_id) as db:
            result = await db.execute(
                text(f"UPDATE agents SET {', '.join(assignments)},updated_at=now() WHERE id=:id AND deleted_at IS NULL RETURNING id"),
                params,
            )
            if not result.scalar_one_or_none():
                return None
        return await self.get_agent(tenant_id, agent_id)

    async def delete_agent(self, tenant_id: UUID, agent_id: UUID) -> bool:
        async with self.tenant_session(tenant_id) as db:
            result = await db.execute(
                text("UPDATE agents SET deleted_at=now(),updated_at=now() WHERE id=:id AND deleted_at IS NULL RETURNING id"),
                {"id": agent_id},
            )
            return result.scalar_one_or_none() is not None

    async def list_versions(self, tenant_id: UUID, agent_id: UUID) -> list[dict[str, Any]]:
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(
                text("SELECT * FROM agent_versions WHERE agent_id=:agent ORDER BY version DESC,created_at DESC"),
                {"agent": agent_id},
            )
            return [dict(row) for row in rows.mappings()]

    async def get_version(self, tenant_id: UUID, agent_id: UUID, version_id: UUID) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text("SELECT * FROM agent_versions WHERE id=:id AND agent_id=:agent"),
                {"id": version_id, "agent": agent_id},
            )
            mapping = row.mappings().first()
            return dict(mapping) if mapping else None

    async def update_draft(self, tenant_id: UUID, agent_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        json_fields = {"llm", "stt", "tts", "turn_config", "behavior", "rag", "variables"}
        allowed = {
            "system_prompt", "greeting", "language", "extra_languages", "llm", "stt", "tts",
            "turn_config", "behavior", "knowledge_base_id", "rag", "variables",
        }
        assignments: list[str] = []
        params: dict[str, Any] = {"agent": agent_id}
        for field, value in data.items():
            if field not in allowed:
                continue
            params[field] = __import__("json").dumps(value) if field in json_fields else value
            assignments.append(f"{field}=CAST(:{field} AS jsonb)" if field in json_fields else f"{field}=:{field}")
        if not assignments:
            agent = await self.get_agent(tenant_id, agent_id)
            return await self.get_version(tenant_id, agent_id, agent["draft_version_id"]) if agent else None
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text(f"UPDATE agent_versions SET {', '.join(assignments)},updated_at=now() WHERE id=(SELECT draft_version_id FROM agents WHERE id=:agent AND deleted_at IS NULL) AND published_at IS NULL RETURNING *"),
                params,
            )
            mapping = row.mappings().first()
            return dict(mapping) if mapping else None

    async def rollback_agent(self, tenant_id: UUID, agent_id: UUID, version_id: UUID) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            target = await db.execute(
                text("SELECT id FROM agent_versions WHERE id=:version AND agent_id=:agent AND published_at IS NOT NULL"),
                {"version": version_id, "agent": agent_id},
            )
            if target.scalar_one_or_none() is None:
                return None
            await db.execute(
                text("UPDATE agents SET current_version_id=:version,status='active',updated_at=now() WHERE id=:agent AND deleted_at IS NULL"),
                {"version": version_id, "agent": agent_id},
            )
        return await self.get_agent_detail(tenant_id, agent_id)

    async def publish_agent(self, tenant_id: UUID, agent_id: UUID) -> dict[str, Any] | None:
        new_draft = uuid4()
        async with self.tenant_session(tenant_id) as db:
            current = (await db.execute(text("SELECT draft_version_id FROM agents WHERE id=:id FOR UPDATE"), {"id": agent_id})).scalar_one_or_none()
            if current is None:
                return None
            await db.execute(text("UPDATE agent_versions SET published_at=now() WHERE id=:version"), {"version": current})
            await db.execute(text("INSERT INTO agent_versions(id,tenant_id,agent_id,version,system_prompt,greeting,llm,stt,tts,turn_config,behavior,rag,variables,created_by) SELECT :new,tenant_id,agent_id,version+1,system_prompt,greeting,llm,stt,tts,turn_config,behavior,rag,variables,created_by FROM agent_versions WHERE id=:current"), {"new": new_draft, "current": current})
            await db.execute(text("INSERT INTO agent_tools(tenant_id,agent_version_id,tool_id,enabled) SELECT tenant_id,:new,tool_id,enabled FROM agent_tools WHERE agent_version_id=:current"), {"new": new_draft, "current": current})
            await db.execute(text("UPDATE agents SET current_version_id=:current,draft_version_id=:draft,status='active',updated_at=now() WHERE id=:id"), {"current": current, "draft": new_draft, "id": agent_id})
        return await self.get_agent(tenant_id, agent_id)

    async def upsert_end_user(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        import json

        if not any(data.get(field) for field in ("external_id", "phone", "email")):
            raise ValueError("end_user requires external_id, phone, or email")
        async with self.tenant_session(tenant_id) as db:
            existing = await db.execute(
                text("""SELECT id FROM end_users WHERE
                (external_id=:external_id AND :external_id IS NOT NULL) OR
                (phone=:phone AND :phone IS NOT NULL) OR
                (email=:email AND :email IS NOT NULL)
                ORDER BY updated_at DESC LIMIT 1 FOR UPDATE"""),
                {"external_id": data.get("external_id"), "phone": data.get("phone"), "email": data.get("email")},
            )
            existing_id = existing.scalar_one_or_none()
            if existing_id:
                row = await db.execute(
                    text("""UPDATE end_users SET external_id=COALESCE(:external_id,external_id),phone=COALESCE(:phone,phone),email=COALESCE(:email,email),name=COALESCE(:name,name),metadata=metadata || CAST(:metadata AS jsonb),last_seen_at=now(),updated_at=now() WHERE id=:id RETURNING *"""),
                    {"id": existing_id, "external_id": data.get("external_id"), "phone": data.get("phone"), "email": data.get("email"), "name": data.get("name"), "metadata": json.dumps(data.get("metadata", {}))},
                )
                return dict(row.mappings().one())
            row = await db.execute(
                text("INSERT INTO end_users(id,tenant_id,external_id,phone,email,name,metadata,first_seen_at,last_seen_at) VALUES(:id,:tenant,:external_id,:phone,:email,:name,CAST(:metadata AS jsonb),now(),now()) RETURNING *"),
                {"id": uuid4(), "tenant": tenant_id, "external_id": data.get("external_id"), "phone": data.get("phone"), "email": data.get("email"), "name": data.get("name"), "metadata": json.dumps(data.get("metadata", {}))},
            )
            return dict(row.mappings().one())

    async def create_call(self, tenant_id: UUID, agent_id: UUID, variables: dict[str, Any], metadata: dict[str, Any], *, agent_version_id: UUID | None = None, end_user_id: UUID | None = None) -> dict[str, Any]:
        call_id = uuid4()
        async with self.tenant_session(tenant_id) as db:
            await db.execute(text("INSERT INTO calls(id,tenant_id,agent_id,agent_version_id,end_user_id,channel,status,variables,metadata,started_at) VALUES(:id,:tenant,:agent,:version,:end_user,'web','queued',CAST(:variables AS jsonb),CAST(:metadata AS jsonb),now())"), {"id": call_id, "tenant": tenant_id, "agent": agent_id, "version": agent_version_id, "end_user": end_user_id, "variables": __import__('json').dumps(variables), "metadata": __import__('json').dumps(metadata)})
        return {"id": call_id, "tenant_id": tenant_id, "agent_id": agent_id, "agent_version_id": agent_version_id, "end_user_id": end_user_id, "channel": "web", "status": "queued", "variables": variables, "metadata": metadata}

    async def list_calls(self, tenant_id: UUID, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        filters = filters or {}
        clauses, params = [], {}
        for field in ("agent_id", "channel", "status", "end_user_id"):
            if filters.get(field) is not None:
                clauses.append(f"{field}=:{field}")
                params[field] = filters[field]
        if filters.get("from") is not None:
            clauses.append("started_at >= :from_date")
            params["from_date"] = filters["from"]
        if filters.get("to") is not None:
            clauses.append("started_at <= :to_date")
            params["to_date"] = filters["to"]
        if filters.get("q"):
            clauses.append("(summary ILIKE :q OR EXISTS (SELECT 1 FROM call_turns ct WHERE ct.call_id=calls.id AND ct.text ILIKE :q))")
            params["q"] = f"%{filters['q']}%"
        async with self.tenant_session(tenant_id) as db:
            where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = await db.execute(text(f"SELECT * FROM calls{where} ORDER BY created_at DESC"), params)
            return [dict(row) for row in rows.mappings()]

    async def get_call(self, tenant_id: UUID, call_id: UUID) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(text("SELECT * FROM calls WHERE id=:id"), {"id": call_id})
            mapping = row.mappings().first()
            return dict(mapping) if mapping else None

    async def get_call_detail(self, tenant_id: UUID, call_id: UUID) -> dict[str, Any] | None:
        call = await self.get_call(tenant_id, call_id)
        if not call:
            return None
        async with self.tenant_session(tenant_id) as db:
            turns = await db.execute(text("SELECT * FROM call_turns WHERE call_id=:id ORDER BY ordinal"), {"id": call_id})
            tools = await db.execute(text("SELECT * FROM call_tool_calls WHERE call_id=:id ORDER BY started_at,id"), {"id": call_id})
            events = await db.execute(text("SELECT * FROM call_events WHERE call_id=:id ORDER BY at,id"), {"id": call_id})
            recording = await db.execute(text("SELECT * FROM call_recordings WHERE call_id=:id"), {"id": call_id})
            qa = await db.execute(text("SELECT * FROM call_qa WHERE call_id=:id"), {"id": call_id})
            return {
                **call,
                "turns": [dict(row) for row in turns.mappings()],
                "tool_calls": [dict(row) for row in tools.mappings()],
                "events": [dict(row) for row in events.mappings()],
                "recording": dict(item) if (item := recording.mappings().first()) else None,
                "qa": dict(item) if (item := qa.mappings().first()) else None,
            }

    async def update_call(self, tenant_id: UUID, call_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        return await self._update_call(tenant_id, call_id, data, internal=False)

    async def _update_call(self, tenant_id: UUID, call_id: UUID, data: dict[str, Any], *, internal: bool) -> dict[str, Any] | None:
        allowed = {"status", "end_reason", "livekit_room", "answered_at", "ended_at", "duration_s", "billable_seconds", "cost", "latency", "summary", "outcome", "variables", "metadata"}
        json_fields = {"cost", "latency", "outcome", "variables", "metadata"}
        assignments: list[str] = []
        params: dict[str, Any] = {"id": call_id}
        for field, value in data.items():
            if field not in allowed:
                continue
            params[field] = __import__("json").dumps(value) if field in json_fields else value
            assignments.append(f"{field}=CAST(:{field} AS jsonb)" if field in json_fields else f"{field}=:{field}")
        if not assignments:
            return await self.get_call(tenant_id, call_id)
        context = self._internal_session() if internal else self.tenant_session(tenant_id)
        async with context as db:
            row = await db.execute(text(f"UPDATE calls SET {', '.join(assignments)},updated_at=now() WHERE id=:id RETURNING *"), params)
            mapping = row.mappings().first()
            return dict(mapping) if mapping else None

    @asynccontextmanager
    async def _internal_session(self) -> AsyncIterator[AsyncSession]:
        async with SessionFactory() as db, db.begin():
            await db.execute(text("SET LOCAL row_security = off"))
            yield db

    async def create_internal_call(self, data: dict[str, Any]) -> dict[str, Any]:
        call_id = uuid4()
        async with self._internal_session() as db:
            row = await db.execute(
                text("INSERT INTO calls(id,tenant_id,agent_id,agent_version_id,channel,status,livekit_room,variables,metadata,started_at) VALUES(:id,:tenant_id,:agent_id,:agent_version_id,:channel,'queued',:livekit_room,CAST(:variables AS jsonb),CAST(:metadata AS jsonb),now()) RETURNING *"),
                {**data, "id": call_id, "variables": __import__("json").dumps(data.get("variables", {})), "metadata": __import__("json").dumps(data.get("metadata", {}))},
            )
            return dict(row.mappings().one())

    async def update_internal_call(self, call_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        async with self._internal_session() as db:
            tenant_id = (await db.execute(text("SELECT tenant_id FROM calls WHERE id=:id"), {"id": call_id})).scalar_one_or_none()
        return await self._update_call(tenant_id, call_id, data, internal=True) if tenant_id else None

    async def _call_tenant(self, db: AsyncSession, call_id: UUID) -> UUID | None:
        return (await db.execute(text("SELECT tenant_id FROM calls WHERE id=:id"), {"id": call_id})).scalar_one_or_none()

    async def get_call_tenant(self, call_id: UUID) -> UUID | None:
        async with self._internal_session() as db:
            return await self._call_tenant(db, call_id)

    async def upsert_call_recording(self, call_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        async with self._internal_session() as db:
            tenant_id = await self._call_tenant(db, call_id)
            if not tenant_id:
                return None
            row = await db.execute(
                text(
                    "INSERT INTO call_recordings(id,tenant_id,call_id,s3_key,format,duration_s,size_bytes,status) "
                    "VALUES(:id,:tenant,:call,:s3_key,:format,:duration_s,:size_bytes,:status) "
                    "ON CONFLICT(call_id) DO UPDATE SET s3_key=excluded.s3_key,format=excluded.format,duration_s=excluded.duration_s,"
                    "size_bytes=excluded.size_bytes,status=excluded.status,updated_at=now() RETURNING *"
                ),
                {"id": uuid4(), "tenant": tenant_id, "call": call_id, "s3_key": data["s3_key"], "format": data.get("format", "ogg"), "duration_s": data.get("duration_s"), "size_bytes": data.get("size_bytes"), "status": data["status"]},
            )
            return dict(row.mappings().one())

    async def append_call_events(self, call_id: UUID, events: list[dict[str, Any]]) -> int:
        async with self._internal_session() as db:
            tenant_id = await self._call_tenant(db, call_id)
            if not tenant_id:
                return 0
            for event in events:
                await db.execute(text("INSERT INTO call_events(tenant_id,call_id,type,payload,at) VALUES(:tenant,:call,:type,CAST(:payload AS jsonb),:at)"), {"tenant": tenant_id, "call": call_id, "type": event["type"], "payload": __import__("json").dumps(event.get("payload", {})), "at": event["at"]})
            return len(events)

    async def append_call_turns(self, call_id: UUID, turns: list[dict[str, Any]]) -> int:
        async with self._internal_session() as db:
            tenant_id = await self._call_tenant(db, call_id)
            if not tenant_id:
                return 0
            for turn in turns:
                values = {**turn, "id": turn.get("id") or uuid4(), "tenant": tenant_id, "call": call_id}
                await db.execute(text("INSERT INTO call_turns(id,tenant_id,call_id,ordinal,role,text,started_at,ended_at,interrupted,ttfb_ms,stt_confidence,audio_offset_ms) VALUES(:id,:tenant,:call,:ordinal,:role,:text,:started_at,:ended_at,:interrupted,:ttfb_ms,:stt_confidence,:audio_offset_ms)"), values)
            return len(turns)

    async def append_call_tool_call(self, call_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        async with self._internal_session() as db:
            tenant_id = await self._call_tenant(db, call_id)
            if not tenant_id:
                return None
            values = {**data, "id": data.get("id") or uuid4(), "tenant": tenant_id, "call": call_id, "arguments": __import__("json").dumps(data["arguments"]), "result": __import__("json").dumps(data.get("result"))}
            row = await db.execute(text("INSERT INTO call_tool_calls(id,tenant_id,call_id,turn_id,tool_id,name,arguments,result,status,duration_ms,started_at) VALUES(:id,:tenant,:call,:turn_id,:tool_id,:name,CAST(:arguments AS jsonb),CAST(:result AS jsonb),:status,:duration_ms,:started_at) RETURNING *"), values)
            return dict(row.mappings().one())

    async def create_tool(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        import json

        tool_id = uuid4()
        async with self.tenant_session(tenant_id) as db:
            await db.execute(text("INSERT INTO tools(id,tenant_id,name,description,type,native_kind,parameters_schema,webhook,speak_before,is_async) VALUES(:id,:tenant,:name,:description,:type,:native_kind,CAST(:schema AS jsonb),CAST(:webhook AS jsonb),:speak_before,:is_async)"), {"id": tool_id, "tenant": tenant_id, "name": data["name"], "description": data["description"], "type": data["type"], "native_kind": data.get("native_kind"), "schema": json.dumps(data["parameters_schema"]), "webhook": json.dumps(data.get("webhook")), "speak_before": data.get("speak_before"), "is_async": data.get("async", False)})
        return {"id": tool_id, "tenant_id": tenant_id, **data}

    async def list_tools(self, tenant_id: UUID) -> list[dict[str, Any]]:
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(text("SELECT * FROM tools ORDER BY created_at DESC"))
            return [dict(row) for row in rows.mappings()]

    async def get_tool(self, tenant_id: UUID, tool_id: UUID) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(text("SELECT * FROM tools WHERE id=:id"), {"id": tool_id})
            mapping = row.mappings().first()
            return dict(mapping) if mapping else None

    async def update_tool(self, tenant_id: UUID, tool_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        json_fields = {"parameters_schema", "webhook"}
        column_names = {"async": "is_async"}
        assignments, params = [], {"id": tool_id}
        for field, value in data.items():
            column = column_names.get(field, field)
            params[field] = __import__("json").dumps(value) if field in json_fields else value
            assignments.append(f"{column}=CAST(:{field} AS jsonb)" if field in json_fields else f"{column}=:{field}")
        if not assignments:
            return await self.get_tool(tenant_id, tool_id)
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(text(f"UPDATE tools SET {', '.join(assignments)},updated_at=now() WHERE id=:id RETURNING *"), params)
            mapping = row.mappings().first()
            return dict(mapping) if mapping else None

    async def delete_tool(self, tenant_id: UUID, tool_id: UUID) -> bool:
        async with self.tenant_session(tenant_id) as db:
            result = await db.execute(text("DELETE FROM tools WHERE id=:id RETURNING id"), {"id": tool_id})
            return result.scalar_one_or_none() is not None

    async def set_draft_tools(self, tenant_id: UUID, agent_id: UUID, tool_ids: list[UUID]) -> list[dict[str, Any]] | None:
        async with self.tenant_session(tenant_id) as db:
            draft_id = (await db.execute(text("SELECT draft_version_id FROM agents WHERE id=:id AND deleted_at IS NULL"), {"id": agent_id})).scalar_one_or_none()
            if draft_id is None:
                return None
            if tool_ids:
                count = (await db.execute(text("SELECT count(*) FROM tools WHERE id = ANY(:ids)"), {"ids": tool_ids})).scalar_one()
                if count != len(set(tool_ids)):
                    raise ValueError("one or more tools do not belong to tenant")
            await db.execute(text("DELETE FROM agent_tools WHERE agent_version_id=:version"), {"version": draft_id})
            for tool_id in dict.fromkeys(tool_ids):
                await db.execute(text("INSERT INTO agent_tools(tenant_id,agent_version_id,tool_id,enabled) VALUES(:tenant,:version,:tool,true)"), {"tenant": tenant_id, "version": draft_id, "tool": tool_id})
        return [tool for tool_id in tool_ids if (tool := await self.get_tool(tenant_id, tool_id))]

    async def get_runtime(self, agent_id: UUID, version: str = "current") -> dict[str, Any] | None:
        async with SessionFactory() as db, db.begin():
            await db.execute(text("SET LOCAL row_security = off"))
            agent_row = await db.execute(text("SELECT tenant_id,current_version_id,draft_version_id FROM agents WHERE id=:id AND deleted_at IS NULL"), {"id": agent_id})
            agent = agent_row.mappings().first()
            if not agent:
                return None
            try:
                version_id = agent["current_version_id"] if version == "current" else agent["draft_version_id"] if version == "draft" else UUID(version)
            except ValueError:
                return None
            if version_id is None:
                return None
            row = await db.execute(
                text(
                    "SELECT a.id agent_id,a.tenant_id,a.name,t.settings tenant_settings,v.id version_id,v.system_prompt,"
                    "v.greeting,v.language,v.extra_languages,v.llm,v.stt,v.tts,v.turn_config,"
                    "v.behavior,v.knowledge_base_id,v.rag,v.variables "
                    "FROM agents a JOIN tenants t ON t.id=a.tenant_id JOIN agent_versions v "
                    "ON v.agent_id=a.id "
                    "WHERE a.id=:id AND v.id=:version AND a.deleted_at IS NULL"
                ),
                {"id": agent_id, "version": version_id},
            )
            mapping = row.mappings().first()
            if not mapping:
                return None
            tools = await db.execute(text("SELECT t.* FROM tools t JOIN agent_tools at ON at.tool_id=t.id WHERE at.agent_version_id=:version AND at.enabled ORDER BY t.name"), {"version": version_id})
            return {**dict(mapping), "tools": [dict(tool) for tool in tools.mappings()]}

    async def list_knowledge_bases(self, tenant_id: UUID) -> list[dict[str, Any]]:
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(text("SELECT * FROM knowledge_bases ORDER BY created_at DESC"))
            return [dict(row) for row in rows.mappings()]

    async def create_knowledge_base(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        kb_id = uuid4()
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(text("INSERT INTO knowledge_bases(id,tenant_id,name,embedding_model,chunk_size,chunk_overlap,status) VALUES(:id,:tenant,:name,:embedding_model,:chunk_size,:chunk_overlap,'ready') RETURNING *"), {"id": kb_id, "tenant": tenant_id, **data})
            return dict(row.mappings().one())

    async def get_knowledge_base(self, tenant_id: UUID, kb_id: UUID) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(text("SELECT * FROM knowledge_bases WHERE id=:id"), {"id": kb_id})
            mapping = row.mappings().first()
            return dict(mapping) if mapping else None

    async def update_knowledge_base(self, tenant_id: UUID, kb_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        if not data:
            return await self.get_knowledge_base(tenant_id, kb_id)
        assignments = [f"{field}=:{field}" for field in data]
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(text(f"UPDATE knowledge_bases SET {', '.join(assignments)},updated_at=now() WHERE id=:id RETURNING *"), {"id": kb_id, **data})
            mapping = row.mappings().first()
            return dict(mapping) if mapping else None

    async def delete_knowledge_base(self, tenant_id: UUID, kb_id: UUID) -> bool:
        async with self.tenant_session(tenant_id) as db:
            result = await db.execute(text("DELETE FROM knowledge_bases WHERE id=:id RETURNING id"), {"id": kb_id})
            return result.scalar_one_or_none() is not None

    async def list_documents(self, tenant_id: UUID, kb_id: UUID) -> list[dict[str, Any]]:
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(text("SELECT * FROM documents WHERE knowledge_base_id=:kb AND deleted_at IS NULL ORDER BY created_at DESC"), {"kb": kb_id})
            return [dict(row) for row in rows.mappings()]

    async def create_document(self, tenant_id: UUID, kb_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        if not await self.get_knowledge_base(tenant_id, kb_id):
            return None
        document_id = uuid4()
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(text("INSERT INTO documents(id,tenant_id,knowledge_base_id,name,source_type,source_uri,mime,size_bytes,status) VALUES(:id,:tenant,:kb,:name,:source_type,:source_uri,:mime,:size_bytes,'pending') RETURNING *"), {"id": document_id, "tenant": tenant_id, "kb": kb_id, "name": data["name"], "source_type": data["source_type"], "source_uri": data.get("source_uri"), "mime": data.get("mime"), "size_bytes": data.get("size_bytes")})
            return dict(row.mappings().one())

    async def delete_document(self, tenant_id: UUID, kb_id: UUID, document_id: UUID) -> bool:
        async with self.tenant_session(tenant_id) as db:
            result = await db.execute(text("UPDATE documents SET deleted_at=now(),updated_at=now() WHERE id=:id AND knowledge_base_id=:kb AND deleted_at IS NULL RETURNING id"), {"id": document_id, "kb": kb_id})
            return result.scalar_one_or_none() is not None

    async def complete_document(self, tenant_id: UUID, document_id: UUID, chunks: list[dict[str, Any]]) -> None:
        import json

        async with self.tenant_session(tenant_id) as db:
            document = (await db.execute(text("SELECT knowledge_base_id FROM documents WHERE id=:id FOR UPDATE"), {"id": document_id})).scalar_one()
            await db.execute(text("DELETE FROM chunks WHERE document_id=:id"), {"id": document_id})
            for ordinal, chunk in enumerate(chunks):
                vector = "[" + ",".join(str(value) for value in chunk["embedding"]) + "]"
                await db.execute(text("INSERT INTO chunks(id,tenant_id,document_id,knowledge_base_id,ordinal,content,embedding,metadata,token_count) VALUES(:id,:tenant,:document,:kb,:ordinal,:content,CAST(:embedding AS vector),CAST(:metadata AS jsonb),:tokens)"), {"id": uuid4(), "tenant": tenant_id, "document": document_id, "kb": document, "ordinal": ordinal, "content": chunk["content"], "embedding": vector, "metadata": json.dumps(chunk.get("metadata", {})), "tokens": chunk["token_count"]})
            await db.execute(text("UPDATE documents SET status='ready',error=NULL,chunk_count=:count,updated_at=now() WHERE id=:id"), {"id": document_id, "count": len(chunks)})

    async def fail_document(self, tenant_id: UUID, document_id: UUID, error: str) -> None:
        async with self.tenant_session(tenant_id) as db:
            await db.execute(text("UPDATE documents SET status='error',error=:error,updated_at=now() WHERE id=:id"), {"id": document_id, "error": error[:1000]})

    async def query_chunks(self, tenant_id: UUID, kb_id: UUID, embedding: list[float], top_k: int, min_score: float) -> list[dict[str, Any]]:
        vector = "[" + ",".join(str(value) for value in embedding) + "]"
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(text("SELECT id,document_id,ordinal,content,metadata,token_count,1-(embedding <=> CAST(:embedding AS vector)) AS score FROM chunks WHERE knowledge_base_id=:kb AND 1-(embedding <=> CAST(:embedding AS vector)) >= :score ORDER BY embedding <=> CAST(:embedding AS vector) LIMIT :limit"), {"embedding": vector, "kb": kb_id, "score": min_score, "limit": top_k})
            return [dict(row) for row in rows.mappings()]

    async def get_knowledge_base_tenant(self, kb_id: UUID) -> UUID | None:
        async with self._internal_session() as db:
            return (await db.execute(text("SELECT tenant_id FROM knowledge_bases WHERE id=:id"), {"id": kb_id})).scalar_one_or_none()

    async def create_secret(self, tenant_id: UUID, name: str, ciphertext: bytes, key_id: str) -> dict[str, Any]:
        secret_id = uuid4()
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(text("INSERT INTO secrets(id,tenant_id,name,ciphertext,kms_key_id) VALUES(:id,:tenant,:name,:ciphertext,:key) RETURNING id,tenant_id,name,kms_key_id,created_at,rotated_at"), {"id": secret_id, "tenant": tenant_id, "name": name, "ciphertext": ciphertext, "key": key_id})
            return dict(row.mappings().one())

    async def list_secrets(self, tenant_id: UUID) -> list[dict[str, Any]]:
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(text("SELECT id,tenant_id,name,kms_key_id,created_at,rotated_at FROM secrets ORDER BY created_at DESC"))
            return [dict(row) for row in rows.mappings()]

    async def get_secret(self, tenant_id: UUID, secret_id: UUID) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(text("SELECT * FROM secrets WHERE id=:id"), {"id": secret_id})
            mapping = row.mappings().first()
            return dict(mapping) if mapping else None

    async def delete_secret(self, tenant_id: UUID, secret_id: UUID) -> bool:
        async with self.tenant_session(tenant_id) as db:
            result = await db.execute(text("DELETE FROM secrets WHERE id=:id RETURNING id"), {"id": secret_id})
            return result.scalar_one_or_none() is not None

    async def get_integration(self, tenant_id: UUID, provider: str) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(text("SELECT * FROM integrations WHERE provider=:provider ORDER BY updated_at DESC LIMIT 1"), {"provider": provider})
            mapping = row.mappings().first()
            return dict(mapping) if mapping else None

    async def upsert_integration(self, tenant_id: UUID, provider: str, data: dict[str, Any]) -> dict[str, Any]:
        async with self.tenant_session(tenant_id) as db:
            existing = (await db.execute(text("SELECT id FROM integrations WHERE provider=:provider ORDER BY updated_at DESC LIMIT 1 FOR UPDATE"), {"provider": provider})).scalar_one_or_none()
            if existing:
                row = await db.execute(text("UPDATE integrations SET scopes=:scopes,refresh_token_secret_id=:secret,account_email=:email,status=:status,updated_at=now() WHERE id=:id RETURNING *"), {"id": existing, "scopes": data["scopes"], "secret": data.get("refresh_token_secret_id"), "email": data.get("account_email"), "status": data["status"]})
            else:
                row = await db.execute(text("INSERT INTO integrations(id,tenant_id,provider,scopes,refresh_token_secret_id,account_email,status) VALUES(:id,:tenant,:provider,:scopes,:secret,:email,:status) RETURNING *"), {"id": uuid4(), "tenant": tenant_id, "provider": provider, "scopes": data["scopes"], "secret": data.get("refresh_token_secret_id"), "email": data.get("account_email"), "status": data["status"]})
            return dict(row.mappings().one())


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

    async def get_agent_detail(self, tenant_id: UUID, agent_id: UUID) -> dict[str, Any] | None:
        agent = await self.get_agent(tenant_id, agent_id)
        if not agent:
            return None
        return {
            **agent,
            "draft": self.memory.agent_versions.get(agent["draft_version_id"]),
            "current": self.memory.agent_versions.get(agent["current_version_id"]),
        }

    async def update_agent(self, tenant_id: UUID, agent_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        agent = await self.get_agent(tenant_id, agent_id)
        if not agent:
            return None
        agent.update(data)
        agent["updated_at"] = datetime.now(UTC)
        return agent

    async def delete_agent(self, tenant_id: UUID, agent_id: UUID) -> bool:
        agent = await self.get_agent(tenant_id, agent_id)
        if not agent:
            return False
        agent["deleted_at"] = datetime.now(UTC)
        self.memory.agents.pop(agent_id)
        return True

    async def list_versions(self, tenant_id: UUID, agent_id: UUID) -> list[dict[str, Any]]:
        return sorted(
            [v for v in self.memory.agent_versions.values() if v["tenant_id"] == tenant_id and v["agent_id"] == agent_id],
            key=lambda version: (version["version"], version["created_at"]),
            reverse=True,
        )

    async def get_version(self, tenant_id: UUID, agent_id: UUID, version_id: UUID) -> dict[str, Any] | None:
        version = self.memory.agent_versions.get(version_id)
        return version if version and version["tenant_id"] == tenant_id and version["agent_id"] == agent_id else None

    async def update_draft(self, tenant_id: UUID, agent_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        agent = await self.get_agent(tenant_id, agent_id)
        if not agent:
            return None
        draft = self.memory.agent_versions[agent["draft_version_id"]]
        if draft["published_at"] is not None:
            return None
        draft.update(data)
        draft["updated_at"] = datetime.now(UTC)
        return draft

    async def rollback_agent(self, tenant_id: UUID, agent_id: UUID, version_id: UUID) -> dict[str, Any] | None:
        agent = await self.get_agent(tenant_id, agent_id)
        version = await self.get_version(tenant_id, agent_id, version_id)
        if not agent or not version or version["published_at"] is None:
            return None
        agent["current_version_id"] = version_id
        agent["status"] = "active"
        agent["updated_at"] = datetime.now(UTC)
        return await self.get_agent_detail(tenant_id, agent_id)

    async def publish_agent(self, tenant_id: UUID, agent_id: UUID) -> dict[str, Any] | None:
        agent = await self.get_agent(tenant_id, agent_id)
        if agent:
            now = datetime.now(UTC)
            published = self.memory.agent_versions[agent["draft_version_id"]]
            published["published_at"] = now
            new_id = uuid4()
            draft = {**published, "id": new_id, "version": published["version"] + 1, "published_at": None, "created_at": now, "updated_at": now}
            self.memory.agent_versions[new_id] = draft
            self.memory.agent_tools[new_id] = set(self.memory.agent_tools.get(published["id"], set()))
            agent["current_version_id"], agent["draft_version_id"], agent["status"] = published["id"], new_id, "active"
            agent["updated_at"] = now
        return await self.get_agent_detail(tenant_id, agent_id)

    async def upsert_end_user(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        if not any(data.get(field) for field in ("external_id", "phone", "email")):
            raise ValueError("end_user requires external_id, phone, or email")
        match = next((item for item in self.memory.end_users.values() if item["tenant_id"] == tenant_id and any(data.get(field) and item.get(field) == data[field] for field in ("external_id", "phone", "email"))), None)
        now = datetime.now(UTC)
        if match:
            match.update({key: value for key, value in data.items() if value is not None})
            match["last_seen_at"] = now
            return match
        item = {"id": uuid4(), "tenant_id": tenant_id, **data, "metadata": data.get("metadata", {}), "first_seen_at": now, "last_seen_at": now}
        self.memory.end_users[item["id"]] = item
        return item

    async def create_call(self, tenant_id: UUID, agent_id: UUID, variables: dict[str, Any], metadata: dict[str, Any], *, agent_version_id: UUID | None = None, end_user_id: UUID | None = None) -> dict[str, Any]:
        call_id = uuid4()
        result = {"id": call_id, "tenant_id": tenant_id, "agent_id": agent_id, "agent_version_id": agent_version_id, "end_user_id": end_user_id, "channel": "web", "status": "queued", "metadata": metadata, "variables": variables, "created_at": datetime.now(UTC)}
        self.memory.calls[call_id] = result
        return result

    async def list_calls(self, tenant_id: UUID, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        filters = filters or {}
        calls = [c for c in self.memory.calls.values() if c["tenant_id"] == tenant_id]
        for field in ("agent_id", "channel", "status", "end_user_id"):
            if filters.get(field) is not None:
                calls = [call for call in calls if call.get(field) == filters[field]]
        if filters.get("q"):
            query = filters["q"].casefold()
            calls = [call for call in calls if query in (call.get("summary") or "").casefold() or any(query in turn.get("text", "").casefold() for turn in self.memory.call_turns.get(call["id"], []))]
        return calls

    async def get_call(self, tenant_id: UUID, call_id: UUID) -> dict[str, Any] | None:
        call = self.memory.calls.get(call_id)
        return call if call and call["tenant_id"] == tenant_id else None

    async def get_call_detail(self, tenant_id: UUID, call_id: UUID) -> dict[str, Any] | None:
        call = await self.get_call(tenant_id, call_id)
        if not call:
            return None
        return {**call, "turns": self.memory.call_turns.get(call_id, []), "tool_calls": self.memory.call_tool_calls.get(call_id, []), "events": self.memory.call_events.get(call_id, []), "recording": self.memory.call_recordings.get(call_id), "qa": None}

    async def update_call(self, tenant_id: UUID, call_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        call = await self.get_call(tenant_id, call_id)
        if not call:
            return None
        call.update(data)
        call["updated_at"] = datetime.now(UTC)
        return call

    async def create_internal_call(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self.create_call(data["tenant_id"], data["agent_id"], data.get("variables", {}), data.get("metadata", {}))

    async def update_internal_call(self, call_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        call = self.memory.calls.get(call_id)
        return await self.update_call(call["tenant_id"], call_id, data) if call else None

    async def append_call_events(self, call_id: UUID, events: list[dict[str, Any]]) -> int:
        if call_id not in self.memory.calls:
            return 0
        self.memory.call_events.setdefault(call_id, []).extend(events)
        return len(events)

    async def append_call_turns(self, call_id: UUID, turns: list[dict[str, Any]]) -> int:
        if call_id not in self.memory.calls:
            return 0
        normalized = [{**turn, "id": turn.get("id") or uuid4()} for turn in turns]
        self.memory.call_turns.setdefault(call_id, []).extend(normalized)
        return len(normalized)

    async def append_call_tool_call(self, call_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        if call_id not in self.memory.calls:
            return None
        item = {**data, "id": data.get("id") or uuid4()}
        self.memory.call_tool_calls.setdefault(call_id, []).append(item)
        return item

    async def get_call_tenant(self, call_id: UUID) -> UUID | None:
        call = self.memory.calls.get(call_id)
        return call["tenant_id"] if call else None

    async def upsert_call_recording(self, call_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        call = self.memory.calls.get(call_id)
        if not call:
            return None
        now = datetime.now(UTC)
        item = {"id": self.memory.call_recordings.get(call_id, {}).get("id", uuid4()), "tenant_id": call["tenant_id"], "call_id": call_id, **data, "updated_at": now}
        self.memory.call_recordings[call_id] = item
        return item

    async def create_tool(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        tool_id = uuid4()
        result = {"id": tool_id, "tenant_id": tenant_id, **data}
        self.memory.tools[tool_id] = result
        return result

    async def list_tools(self, tenant_id: UUID) -> list[dict[str, Any]]:
        return [tool for tool in self.memory.tools.values() if tool["tenant_id"] == tenant_id]

    async def get_tool(self, tenant_id: UUID, tool_id: UUID) -> dict[str, Any] | None:
        tool = self.memory.tools.get(tool_id)
        return tool if tool and tool["tenant_id"] == tenant_id else None

    async def update_tool(self, tenant_id: UUID, tool_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        tool = await self.get_tool(tenant_id, tool_id)
        if not tool:
            return None
        tool.update(data)
        tool["updated_at"] = datetime.now(UTC)
        return tool

    async def delete_tool(self, tenant_id: UUID, tool_id: UUID) -> bool:
        if not await self.get_tool(tenant_id, tool_id):
            return False
        self.memory.tools.pop(tool_id)
        for tool_ids in self.memory.agent_tools.values():
            tool_ids.discard(tool_id)
        return True

    async def set_draft_tools(self, tenant_id: UUID, agent_id: UUID, tool_ids: list[UUID]) -> list[dict[str, Any]] | None:
        agent = await self.get_agent(tenant_id, agent_id)
        if not agent:
            return None
        tools = [tool for tool_id in tool_ids if (tool := await self.get_tool(tenant_id, tool_id))]
        if len(tools) != len(set(tool_ids)):
            raise ValueError("one or more tools do not belong to tenant")
        self.memory.agent_tools[agent["draft_version_id"]] = set(tool_ids)
        return tools

    async def get_runtime(self, agent_id: UUID, version: str = "current") -> dict[str, Any] | None:
        agent = self.memory.agents.get(agent_id)
        if not agent:
            return None
        try:
            version_id = agent["current_version_id"] if version == "current" else agent["draft_version_id"] if version == "draft" else UUID(version)
        except ValueError:
            return None
        selected = self.memory.agent_versions.get(version_id)
        if not selected or selected["agent_id"] != agent_id:
            return None
        tools = [self.memory.tools[tool_id] for tool_id in self.memory.agent_tools.get(version_id, set()) if tool_id in self.memory.tools]
        return {**agent, **selected, "version_id": selected["id"], "tenant_settings": {}, "tools": sorted(tools, key=lambda tool: tool["name"])}

    async def list_knowledge_bases(self, tenant_id: UUID) -> list[dict[str, Any]]:
        return [kb for kb in self.memory.knowledge_bases.values() if kb["tenant_id"] == tenant_id]

    async def create_knowledge_base(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        item = {"id": uuid4(), "tenant_id": tenant_id, **data, "status": "ready", "created_at": now, "updated_at": now}
        self.memory.knowledge_bases[item["id"]] = item
        return item

    async def get_knowledge_base(self, tenant_id: UUID, kb_id: UUID) -> dict[str, Any] | None:
        item = self.memory.knowledge_bases.get(kb_id)
        return item if item and item["tenant_id"] == tenant_id else None

    async def update_knowledge_base(self, tenant_id: UUID, kb_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        item = await self.get_knowledge_base(tenant_id, kb_id)
        if not item:
            return None
        item.update(data)
        item["updated_at"] = datetime.now(UTC)
        return item

    async def delete_knowledge_base(self, tenant_id: UUID, kb_id: UUID) -> bool:
        if not await self.get_knowledge_base(tenant_id, kb_id):
            return False
        self.memory.knowledge_bases.pop(kb_id)
        for document_id in [doc_id for doc_id, doc in self.memory.documents.items() if doc["knowledge_base_id"] == kb_id]:
            self.memory.documents.pop(document_id)
            self.memory.chunks.pop(document_id, None)
        return True

    async def list_documents(self, tenant_id: UUID, kb_id: UUID) -> list[dict[str, Any]]:
        return [doc for doc in self.memory.documents.values() if doc["tenant_id"] == tenant_id and doc["knowledge_base_id"] == kb_id and not doc.get("deleted_at")]

    async def create_document(self, tenant_id: UUID, kb_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        if not await self.get_knowledge_base(tenant_id, kb_id):
            return None
        now = datetime.now(UTC)
        item = {"id": uuid4(), "tenant_id": tenant_id, "knowledge_base_id": kb_id, **data, "status": "pending", "chunk_count": 0, "created_at": now, "updated_at": now}
        self.memory.documents[item["id"]] = item
        return item

    async def delete_document(self, tenant_id: UUID, kb_id: UUID, document_id: UUID) -> bool:
        item = self.memory.documents.get(document_id)
        if not item or item["tenant_id"] != tenant_id or item["knowledge_base_id"] != kb_id or item.get("deleted_at"):
            return False
        item["deleted_at"] = datetime.now(UTC)
        self.memory.chunks.pop(document_id, None)
        return True

    async def complete_document(self, tenant_id: UUID, document_id: UUID, chunks: list[dict[str, Any]]) -> None:
        document = self.memory.documents[document_id]
        if document["tenant_id"] != tenant_id:
            return
        self.memory.chunks[document_id] = [{**chunk, "id": uuid4(), "document_id": document_id, "knowledge_base_id": document["knowledge_base_id"], "ordinal": ordinal} for ordinal, chunk in enumerate(chunks)]
        document.update({"status": "ready", "error": None, "chunk_count": len(chunks), "updated_at": datetime.now(UTC)})

    async def fail_document(self, tenant_id: UUID, document_id: UUID, error: str) -> None:
        document = self.memory.documents.get(document_id)
        if document and document["tenant_id"] == tenant_id:
            document.update({"status": "error", "error": error[:1000], "updated_at": datetime.now(UTC)})

    async def query_chunks(self, tenant_id: UUID, kb_id: UUID, embedding: list[float], top_k: int, min_score: float) -> list[dict[str, Any]]:
        from .knowledge import cosine_similarity

        candidates = [{**chunk, "score": cosine_similarity(embedding, chunk["embedding"])} for document_id, chunks in self.memory.chunks.items() if self.memory.documents[document_id]["tenant_id"] == tenant_id and self.memory.documents[document_id]["knowledge_base_id"] == kb_id for chunk in chunks]
        return sorted([chunk for chunk in candidates if chunk["score"] >= min_score], key=lambda chunk: chunk["score"], reverse=True)[:top_k]

    async def get_knowledge_base_tenant(self, kb_id: UUID) -> UUID | None:
        item = self.memory.knowledge_bases.get(kb_id)
        return item["tenant_id"] if item else None

    async def create_secret(self, tenant_id: UUID, name: str, ciphertext: bytes, key_id: str) -> dict[str, Any]:
        now = datetime.now(UTC)
        secret_id = uuid4()
        item = {"id": secret_id, "tenant_id": tenant_id, "name": name, "ciphertext": ciphertext, "kms_key_id": key_id, "created_at": now, "rotated_at": None}
        self.memory.secrets[secret_id] = item
        return {key: value for key, value in item.items() if key != "ciphertext"}

    async def list_secrets(self, tenant_id: UUID) -> list[dict[str, Any]]:
        return [{key: value for key, value in item.items() if key != "ciphertext"} for item in self.memory.secrets.values() if item["tenant_id"] == tenant_id]

    async def get_secret(self, tenant_id: UUID, secret_id: UUID) -> dict[str, Any] | None:
        item = self.memory.secrets.get(secret_id)
        return item if item and item["tenant_id"] == tenant_id else None

    async def delete_secret(self, tenant_id: UUID, secret_id: UUID) -> bool:
        if not await self.get_secret(tenant_id, secret_id):
            return False
        self.memory.secrets.pop(secret_id)
        return True

    async def get_integration(self, tenant_id: UUID, provider: str) -> dict[str, Any] | None:
        return next((item for item in self.memory.integrations.values() if item["tenant_id"] == tenant_id and item["provider"] == provider), None)

    async def upsert_integration(self, tenant_id: UUID, provider: str, data: dict[str, Any]) -> dict[str, Any]:
        item = await self.get_integration(tenant_id, provider)
        now = datetime.now(UTC)
        if item:
            item.update(data)
            item["updated_at"] = now
            return item
        item = {"id": uuid4(), "tenant_id": tenant_id, "provider": provider, **data, "created_at": now, "updated_at": now}
        self.memory.integrations[item["id"]] = item
        return item


postgres_repository = PostgresRepository()


async def get_repository() -> Repository:
    return postgres_repository
