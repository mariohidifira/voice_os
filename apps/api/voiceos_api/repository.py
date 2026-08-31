import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .billing import PLANS
from .campaigns import retry_at
from .db import SessionFactory
from .store import MemoryStore, store


class LastOwnerError(ValueError):
    """Raised when a membership mutation would leave a tenant without an owner."""


class Repository(Protocol):
    async def get_tenant(self, tenant_id: UUID) -> dict[str, Any] | None: ...
    async def update_tenant(
        self, tenant_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None: ...
    async def list_members(self, tenant_id: UUID) -> list[dict[str, Any]]: ...
    async def create_member(self, tenant_id: UUID, email: str, role: str) -> dict[str, Any]: ...
    async def update_member(
        self, tenant_id: UUID, user_id: UUID, role: str
    ) -> dict[str, Any] | None: ...
    async def delete_member(self, tenant_id: UUID, user_id: UUID) -> bool: ...
    async def list_api_keys(self, tenant_id: UUID) -> list[dict[str, Any]]: ...
    async def create_api_key(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]: ...
    async def revoke_api_key(self, tenant_id: UUID, key_id: UUID) -> bool: ...
    async def get_api_key_by_hash(
        self, tenant_id: UUID, prefix: str, hash_value: str
    ) -> dict[str, Any] | None: ...
    async def list_agents(self, tenant_id: UUID) -> list[dict[str, Any]]: ...
    async def create_agent(self, tenant_id: UUID, name: str, user_id: str) -> dict[str, Any]: ...
    async def publish_agent(self, tenant_id: UUID, agent_id: UUID) -> dict[str, Any] | None: ...
    async def get_agent(self, tenant_id: UUID, agent_id: UUID) -> dict[str, Any] | None: ...
    async def get_agent_detail(self, tenant_id: UUID, agent_id: UUID) -> dict[str, Any] | None: ...
    async def update_agent(
        self, tenant_id: UUID, agent_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None: ...
    async def delete_agent(self, tenant_id: UUID, agent_id: UUID) -> bool: ...
    async def list_versions(self, tenant_id: UUID, agent_id: UUID) -> list[dict[str, Any]]: ...
    async def get_version(
        self, tenant_id: UUID, agent_id: UUID, version_id: UUID
    ) -> dict[str, Any] | None: ...
    async def update_draft(
        self, tenant_id: UUID, agent_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None: ...
    async def rollback_agent(
        self, tenant_id: UUID, agent_id: UUID, version_id: UUID
    ) -> dict[str, Any] | None: ...
    async def upsert_end_user(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]: ...
    async def list_end_users(self, tenant_id: UUID, query: str | None = None) -> list[dict[str, Any]]: ...
    async def get_end_user(self, tenant_id: UUID, end_user_id: UUID) -> dict[str, Any] | None: ...
    async def update_end_user(self, tenant_id: UUID, end_user_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None: ...
    async def anonymize_end_user(self, tenant_id: UUID, end_user_id: UUID) -> bool: ...
    async def create_call(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        variables: dict[str, Any],
        metadata: dict[str, Any],
        *,
        agent_version_id: UUID | None = None,
        end_user_id: UUID | None = None,
        channel: str = "web",
        status: str = "queued",
        from_number: str | None = None,
        to_number: str | None = None,
        campaign_id: UUID | None = None,
    ) -> dict[str, Any]: ...
    async def list_calls(
        self, tenant_id: UUID, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]: ...
    async def get_call(self, tenant_id: UUID, call_id: UUID) -> dict[str, Any] | None: ...
    async def get_call_detail(self, tenant_id: UUID, call_id: UUID) -> dict[str, Any] | None: ...
    async def upsert_call_qa(self, tenant_id: UUID, call_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None: ...
    async def update_call(
        self, tenant_id: UUID, call_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None: ...
    async def expire_stale_calls(self) -> int: ...
    async def create_internal_call(self, data: dict[str, Any]) -> dict[str, Any]: ...
    async def update_internal_call(
        self, call_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None: ...
    async def append_call_events(self, call_id: UUID, events: list[dict[str, Any]]) -> int: ...
    async def append_call_turns(self, call_id: UUID, turns: list[dict[str, Any]]) -> int: ...
    async def append_call_tool_call(
        self, call_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None: ...
    async def get_call_tenant(self, call_id: UUID) -> UUID | None: ...
    async def upsert_call_recording(
        self, call_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None: ...
    async def create_tool(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]: ...
    async def list_tools(self, tenant_id: UUID) -> list[dict[str, Any]]: ...
    async def get_tool(self, tenant_id: UUID, tool_id: UUID) -> dict[str, Any] | None: ...
    async def update_tool(
        self, tenant_id: UUID, tool_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None: ...
    async def delete_tool(self, tenant_id: UUID, tool_id: UUID) -> bool: ...
    async def set_draft_tools(
        self, tenant_id: UUID, agent_id: UUID, tool_ids: list[UUID]
    ) -> list[dict[str, Any]] | None: ...
    async def get_runtime(
        self, agent_id: UUID, version: str = "current"
    ) -> dict[str, Any] | None: ...
    async def list_knowledge_bases(self, tenant_id: UUID) -> list[dict[str, Any]]: ...
    async def create_knowledge_base(
        self, tenant_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any]: ...
    async def get_knowledge_base(self, tenant_id: UUID, kb_id: UUID) -> dict[str, Any] | None: ...
    async def update_knowledge_base(
        self, tenant_id: UUID, kb_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None: ...
    async def delete_knowledge_base(self, tenant_id: UUID, kb_id: UUID) -> bool: ...
    async def list_documents(self, tenant_id: UUID, kb_id: UUID) -> list[dict[str, Any]]: ...
    async def create_document(
        self, tenant_id: UUID, kb_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None: ...
    async def delete_document(self, tenant_id: UUID, kb_id: UUID, document_id: UUID) -> bool: ...
    async def complete_document(
        self, tenant_id: UUID, document_id: UUID, chunks: list[dict[str, Any]]
    ) -> None: ...
    async def fail_document(self, tenant_id: UUID, document_id: UUID, error: str) -> None: ...
    async def query_chunks(
        self, tenant_id: UUID, kb_id: UUID, embedding: list[float], top_k: int, min_score: float
    ) -> list[dict[str, Any]]: ...
    async def get_knowledge_base_tenant(self, kb_id: UUID) -> UUID | None: ...
    async def create_secret(
        self, tenant_id: UUID, name: str, ciphertext: bytes, key_id: str
    ) -> dict[str, Any]: ...
    async def list_secrets(self, tenant_id: UUID) -> list[dict[str, Any]]: ...
    async def get_secret(self, tenant_id: UUID, secret_id: UUID) -> dict[str, Any] | None: ...
    async def delete_secret(self, tenant_id: UUID, secret_id: UUID) -> bool: ...
    async def get_integration(self, tenant_id: UUID, provider: str) -> dict[str, Any] | None: ...
    async def upsert_integration(
        self, tenant_id: UUID, provider: str, data: dict[str, Any]
    ) -> dict[str, Any]: ...
    async def list_phone_numbers(self, tenant_id: UUID) -> list[dict[str, Any]]: ...
    async def get_phone_number(self, tenant_id: UUID, number_id: UUID) -> dict[str, Any] | None: ...
    async def create_phone_number(
        self, tenant_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any]: ...
    async def update_phone_number(
        self, tenant_id: UUID, number_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None: ...
    async def list_campaigns(self, tenant_id: UUID) -> list[dict[str, Any]]: ...
    async def create_campaign(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]: ...
    async def get_campaign(self, tenant_id: UUID, campaign_id: UUID) -> dict[str, Any] | None: ...
    async def update_campaign(
        self, tenant_id: UUID, campaign_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None: ...
    async def add_campaign_contacts(
        self, tenant_id: UUID, campaign_id: UUID, contacts: list[dict[str, Any]]
    ) -> list[dict[str, Any]]: ...
    async def list_campaign_contacts(
        self, tenant_id: UUID, campaign_id: UUID, status: str | None = None
    ) -> list[dict[str, Any]]: ...
    async def list_do_not_call(self, tenant_id: UUID) -> list[dict[str, Any]]: ...
    async def add_do_not_call(
        self, tenant_id: UUID, phone: str, reason: str | None
    ) -> dict[str, Any]: ...
    async def remove_do_not_call(self, tenant_id: UUID, phone: str) -> bool: ...
    async def claim_campaign_contacts(self, limit: int = 100) -> list[dict[str, Any]]: ...
    async def update_campaign_contact_internal(
        self, contact_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None: ...
    async def get_plan_concurrency(self, tenant_id: UUID) -> int: ...
    async def get_billing_plan(self, tenant_id: UUID) -> dict[str, Any] | None: ...
    async def get_plan_by_code(self, code: str) -> dict[str, Any] | None: ...
    async def get_billing_usage(self, tenant_id: UUID, period: date) -> dict[str, Any]: ...
    async def list_invoices(self, tenant_id: UUID) -> list[dict[str, Any]]: ...
    async def upsert_invoice(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]: ...
    async def upsert_subscription(
        self, tenant_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any]: ...
    async def update_billing_tenant(
        self, tenant_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None: ...
    async def billing_meter_batches(self) -> list[dict[str, Any]]: ...
    async def mark_usage_reported(
        self, tenant_id: UUID, record_ids: list[UUID], stripe_id: str
    ) -> None: ...
    async def billing_threshold_events(self) -> list[dict[str, Any]]: ...
    async def list_webhooks(self, tenant_id: UUID) -> list[dict[str, Any]]: ...
    async def create_webhook(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]: ...
    async def update_webhook(self, tenant_id: UUID, webhook_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None: ...
    async def delete_webhook(self, tenant_id: UUID, webhook_id: UUID) -> bool: ...
    async def list_webhook_deliveries(self, tenant_id: UUID, webhook_id: UUID) -> list[dict[str, Any]]: ...
    async def queue_webhook_event(self, tenant_id: UUID, event: str, data: dict[str, Any]) -> int: ...
    async def claim_webhook_deliveries(self, limit: int = 100) -> list[dict[str, Any]]: ...
    async def update_webhook_delivery(self, delivery_id: UUID, data: dict[str, Any]) -> None: ...
    async def retry_webhook_delivery(self, tenant_id: UUID, webhook_id: UUID, delivery_id: UUID) -> bool: ...
    async def create_export(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]: ...
    async def get_export(self, tenant_id: UUID, export_id: UUID) -> dict[str, Any] | None: ...
    async def claim_exports(self, limit: int = 20) -> list[dict[str, Any]]: ...
    async def complete_export(self, export_id: UUID, s3_key: str | None, error: bool = False) -> None: ...
    async def purge_retention(self) -> dict[str, Any]: ...
    async def analytics_overview(self, tenant_id: UUID, start: date, end: date, agent_id: UUID | None = None) -> dict[str, Any]: ...
    async def analytics_tools(self, tenant_id: UUID, start: date, end: date) -> list[dict[str, Any]]: ...
    async def admin_list_tenants(self) -> list[dict[str, Any]]: ...
    async def admin_update_tenant(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None: ...
    async def admin_metrics(self) -> dict[str, Any]: ...
    async def ingest_whatsapp_message(self, data: dict[str, Any]) -> bool: ...
    async def claim_whatsapp_messages(self, limit: int = 100) -> list[dict[str, Any]]: ...
    async def complete_whatsapp_message(self, message_id: UUID, data: dict[str, Any]) -> None: ...
    async def create_simulation(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]: ...
    async def get_simulation(self, tenant_id: UUID, simulation_id: UUID) -> dict[str, Any] | None: ...
    async def complete_simulation(self, tenant_id: UUID, simulation_id: UUID, report: dict[str, Any]) -> dict[str, Any] | None: ...


class PostgresRepository:
    @asynccontextmanager
    async def tenant_session(self, tenant_id: UUID) -> AsyncIterator[AsyncSession]:
        async with SessionFactory() as db, db.begin():
            await db.execute(text("SET LOCAL ROLE voiceos_app"))
            await db.execute(
                text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            yield db

    async def get_tenant(self, tenant_id: UUID) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text(
                    "SELECT id,slug,name,status,settings,created_at,updated_at FROM tenants WHERE id=:id AND deleted_at IS NULL"
                ),
                {"id": tenant_id},
            )
            item = row.mappings().first()
            return dict(item) if item else None

    async def update_tenant(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        assignments: list[str] = []
        params: dict[str, Any] = {"id": tenant_id}
        if "name" in data:
            assignments.append("name=:name")
            params["name"] = data["name"]
        if settings := data.get("settings"):
            assignments.append("settings=settings || CAST(:settings AS jsonb)")
            params["settings"] = json.dumps(settings)
        if not assignments:
            return await self.get_tenant(tenant_id)
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text(
                    f"UPDATE tenants SET {', '.join(assignments)},updated_at=now() WHERE id=:id AND deleted_at IS NULL RETURNING id,slug,name,status,settings,created_at,updated_at"
                ),
                params,
            )
            item = row.mappings().first()
            return dict(item) if item else None

    async def list_members(self, tenant_id: UUID) -> list[dict[str, Any]]:
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(
                text(
                    "SELECT u.id,u.email,u.name,u.avatar_url,m.role,m.created_at FROM memberships m JOIN users u ON u.id=m.user_id ORDER BY m.created_at"
                )
            )
            return [dict(row) for row in rows.mappings()]

    async def create_member(self, tenant_id: UUID, email: str, role: str) -> dict[str, Any]:
        async with self.tenant_session(tenant_id) as db:
            user_id = (
                await db.execute(
                    text(
                        "INSERT INTO users(email) VALUES(:email) ON CONFLICT(email) DO UPDATE SET email=excluded.email RETURNING id"
                    ),
                    {"email": email.casefold()},
                )
            ).scalar_one()
            await db.execute(
                text(
                    "INSERT INTO memberships(tenant_id,user_id,role) VALUES(:tenant,:user,:role) ON CONFLICT(user_id,tenant_id) DO UPDATE SET role=excluded.role,updated_at=now()"
                ),
                {"tenant": tenant_id, "user": user_id, "role": role},
            )
            row = await db.execute(
                text(
                    "SELECT u.id,u.email,u.name,u.avatar_url,m.role,m.created_at FROM memberships m JOIN users u ON u.id=m.user_id WHERE m.user_id=:user"
                ),
                {"user": user_id},
            )
            return dict(row.mappings().one())

    async def list_phone_numbers(self, tenant_id: UUID) -> list[dict[str, Any]]:
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(text("SELECT * FROM phone_numbers ORDER BY created_at DESC"))
            return [dict(row) for row in rows.mappings()]

    async def get_phone_number(self, tenant_id: UUID, number_id: UUID) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text("SELECT * FROM phone_numbers WHERE id=:id"), {"id": number_id}
            )
            mapping = row.mappings().first()
            return dict(mapping) if mapping else None

    async def create_phone_number(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text(
                    "INSERT INTO phone_numbers(id,tenant_id,agent_id,e164,provider,provider_sid,capabilities,status,livekit_dispatch_rule_id) "
                    "VALUES(:id,:tenant,:agent_id,:e164,:provider,:provider_sid,CAST(:capabilities AS jsonb),'active',:rule_id) RETURNING *"
                ),
                {
                    "id": uuid4(),
                    "tenant": tenant_id,
                    "agent_id": data.get("agent_id"),
                    "e164": data["e164"],
                    "provider": data.get("provider", "twilio"),
                    "provider_sid": data.get("provider_sid"),
                    "capabilities": json.dumps(data.get("capabilities", {})),
                    "rule_id": data.get("livekit_dispatch_rule_id"),
                },
            )
            return dict(row.mappings().one())

    async def update_phone_number(
        self, tenant_id: UUID, number_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        allowed = {"agent_id", "status", "livekit_dispatch_rule_id"}
        assignments = [f"{key}=:{key}" for key in data if key in allowed]
        if not assignments:
            return await self.get_phone_number(tenant_id, number_id)
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text(
                    f"UPDATE phone_numbers SET {', '.join(assignments)},updated_at=now() "
                    "WHERE id=:id RETURNING *"
                ),
                {"id": number_id, **{key: value for key, value in data.items() if key in allowed}},
            )
            mapping = row.mappings().first()
            return dict(mapping) if mapping else None

    async def update_member(
        self, tenant_id: UUID, user_id: UUID, role: str
    ) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            await db.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:tenant,0))"),
                {"tenant": str(tenant_id)},
            )
            current_role = (
                await db.execute(
                    text("SELECT role FROM memberships WHERE user_id=:user FOR UPDATE"),
                    {"user": user_id},
                )
            ).scalar_one_or_none()
            if current_role is None:
                return None
            if current_role == "owner" and role != "owner":
                owners = (
                    (
                        await db.execute(
                            text("SELECT user_id FROM memberships WHERE role='owner' FOR UPDATE")
                        )
                    )
                    .scalars()
                    .all()
                )
                if len(owners) == 1:
                    raise LastOwnerError
            changed = await db.execute(
                text(
                    "UPDATE memberships SET role=:role,updated_at=now() WHERE user_id=:user RETURNING user_id"
                ),
                {"user": user_id, "role": role},
            )
            if changed.scalar_one_or_none() is None:
                return None
            row = await db.execute(
                text(
                    "SELECT u.id,u.email,u.name,u.avatar_url,m.role,m.created_at FROM memberships m JOIN users u ON u.id=m.user_id WHERE m.user_id=:user"
                ),
                {"user": user_id},
            )
            return dict(row.mappings().one())

    async def delete_member(self, tenant_id: UUID, user_id: UUID) -> bool:
        async with self.tenant_session(tenant_id) as db:
            await db.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:tenant,0))"),
                {"tenant": str(tenant_id)},
            )
            current_role = (
                await db.execute(
                    text("SELECT role FROM memberships WHERE user_id=:user FOR UPDATE"),
                    {"user": user_id},
                )
            ).scalar_one_or_none()
            if current_role is None:
                return False
            if current_role == "owner":
                owners = (
                    (
                        await db.execute(
                            text("SELECT user_id FROM memberships WHERE role='owner' FOR UPDATE")
                        )
                    )
                    .scalars()
                    .all()
                )
                if len(owners) == 1:
                    raise LastOwnerError
            result = await db.execute(
                text("DELETE FROM memberships WHERE user_id=:user RETURNING user_id"),
                {"user": user_id},
            )
            return result.scalar_one_or_none() is not None

    async def list_api_keys(self, tenant_id: UUID) -> list[dict[str, Any]]:
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(
                text(
                    "SELECT id,tenant_id,name,prefix,scope,allowed_origins,last_used_at,revoked_at,created_at FROM api_keys ORDER BY created_at DESC"
                )
            )
            return [dict(row) for row in rows.mappings()]

    async def create_api_key(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text(
                    "INSERT INTO api_keys(id,tenant_id,name,prefix,hash,scope,allowed_origins) VALUES(:id,:tenant,:name,:prefix,:hash,:scope,:origins) RETURNING id,tenant_id,name,prefix,scope,allowed_origins,last_used_at,revoked_at,created_at"
                ),
                {"id": uuid4(), "tenant": tenant_id, **data, "origins": data["allowed_origins"]},
            )
            return dict(row.mappings().one())

    async def revoke_api_key(self, tenant_id: UUID, key_id: UUID) -> bool:
        async with self.tenant_session(tenant_id) as db:
            result = await db.execute(
                text(
                    "UPDATE api_keys SET revoked_at=now(),updated_at=now() WHERE id=:id AND revoked_at IS NULL RETURNING id"
                ),
                {"id": key_id},
            )
            return result.scalar_one_or_none() is not None

    async def get_api_key_by_hash(
        self, tenant_id: UUID, prefix: str, hash_value: str
    ) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text(
                    "SELECT id,tenant_id,name,prefix,scope,allowed_origins,last_used_at,revoked_at,created_at "
                    "FROM api_keys WHERE prefix=:prefix AND hash=:hash AND revoked_at IS NULL LIMIT 1"
                ),
                {"prefix": prefix, "hash": hash_value},
            )
            item = row.mappings().first()
            return dict(item) if item else None

    async def list_agents(self, tenant_id: UUID) -> list[dict[str, Any]]:
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(
                text("SELECT * FROM agents WHERE deleted_at IS NULL ORDER BY created_at DESC")
            )
            return [dict(row) for row in rows.mappings()]

    async def create_agent(self, tenant_id: UUID, name: str, user_id: str) -> dict[str, Any]:
        agent_id, draft_id = uuid4(), uuid4()
        async with self.tenant_session(tenant_id) as db:
            await db.execute(
                text(
                    "INSERT INTO agents(id,tenant_id,name,status,draft_version_id) VALUES(:id,:tenant,:name,'draft',:draft)"
                ),
                {"id": agent_id, "tenant": tenant_id, "name": name, "draft": draft_id},
            )
            await db.execute(
                text(
                    "INSERT INTO agent_versions(id,tenant_id,agent_id,version,system_prompt,greeting,llm,stt,tts,turn_config,behavior,rag,variables,created_by) VALUES(:id,:tenant,:agent,1,:prompt,:greeting,:llm,:stt,:tts,:turn,:behavior,:rag,'{}'::jsonb,:user)"
                ),
                {
                    "id": draft_id,
                    "tenant": tenant_id,
                    "agent": agent_id,
                    "prompt": "Você é um agente de voz cordial e objetivo.",
                    "greeting": f"Olá! Aqui é {name}. Como posso ajudar?",
                    "llm": '{"provider":"anthropic","temperature":0.3,"max_tokens":350}',
                    "stt": '{"provider":"deepgram","model":"nova-3"}',
                    "tts": '{"provider":"elevenlabs","model":"eleven_flash_v2_5"}',
                    "turn": '{"allow_interruptions":true}',
                    "behavior": '{"max_call_duration_s":900}',
                    "rag": '{"enabled":false}',
                    "user": user_id,
                },
            )
        return (await self.get_agent(tenant_id, agent_id)) or {}

    async def get_agent(self, tenant_id: UUID, agent_id: UUID) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text("SELECT * FROM agents WHERE id=:id AND deleted_at IS NULL"), {"id": agent_id}
            )
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

    async def update_agent(
        self, tenant_id: UUID, agent_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
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
                text(
                    f"UPDATE agents SET {', '.join(assignments)},updated_at=now() WHERE id=:id AND deleted_at IS NULL RETURNING id"
                ),
                params,
            )
            if not result.scalar_one_or_none():
                return None
        return await self.get_agent(tenant_id, agent_id)

    async def delete_agent(self, tenant_id: UUID, agent_id: UUID) -> bool:
        async with self.tenant_session(tenant_id) as db:
            result = await db.execute(
                text(
                    "UPDATE agents SET deleted_at=now(),updated_at=now() WHERE id=:id AND deleted_at IS NULL RETURNING id"
                ),
                {"id": agent_id},
            )
            return result.scalar_one_or_none() is not None

    async def list_versions(self, tenant_id: UUID, agent_id: UUID) -> list[dict[str, Any]]:
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(
                text(
                    "SELECT * FROM agent_versions WHERE agent_id=:agent ORDER BY version DESC,created_at DESC"
                ),
                {"agent": agent_id},
            )
            return [dict(row) for row in rows.mappings()]

    async def get_version(
        self, tenant_id: UUID, agent_id: UUID, version_id: UUID
    ) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text("SELECT * FROM agent_versions WHERE id=:id AND agent_id=:agent"),
                {"id": version_id, "agent": agent_id},
            )
            mapping = row.mappings().first()
            return dict(mapping) if mapping else None

    async def update_draft(
        self, tenant_id: UUID, agent_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        json_fields = {"llm", "stt", "tts", "turn_config", "behavior", "rag", "variables"}
        allowed = {
            "system_prompt",
            "greeting",
            "language",
            "extra_languages",
            "llm",
            "stt",
            "tts",
            "turn_config",
            "behavior",
            "knowledge_base_id",
            "rag",
            "variables",
        }
        assignments: list[str] = []
        params: dict[str, Any] = {"agent": agent_id}
        for field, value in data.items():
            if field not in allowed:
                continue
            params[field] = __import__("json").dumps(value) if field in json_fields else value
            assignments.append(
                f"{field}=CAST(:{field} AS jsonb)" if field in json_fields else f"{field}=:{field}"
            )
        if not assignments:
            agent = await self.get_agent(tenant_id, agent_id)
            return (
                await self.get_version(tenant_id, agent_id, agent["draft_version_id"])
                if agent
                else None
            )
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text(
                    f"UPDATE agent_versions SET {', '.join(assignments)},updated_at=now() WHERE id=(SELECT draft_version_id FROM agents WHERE id=:agent AND deleted_at IS NULL) AND published_at IS NULL RETURNING *"
                ),
                params,
            )
            mapping = row.mappings().first()
            return dict(mapping) if mapping else None

    async def rollback_agent(
        self, tenant_id: UUID, agent_id: UUID, version_id: UUID
    ) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            target = await db.execute(
                text(
                    "SELECT id FROM agent_versions WHERE id=:version AND agent_id=:agent AND published_at IS NOT NULL"
                ),
                {"version": version_id, "agent": agent_id},
            )
            if target.scalar_one_or_none() is None:
                return None
            await db.execute(
                text(
                    "UPDATE agents SET current_version_id=:version,status='active',updated_at=now() WHERE id=:agent AND deleted_at IS NULL"
                ),
                {"version": version_id, "agent": agent_id},
            )
        return await self.get_agent_detail(tenant_id, agent_id)

    async def publish_agent(self, tenant_id: UUID, agent_id: UUID) -> dict[str, Any] | None:
        new_draft = uuid4()
        async with self.tenant_session(tenant_id) as db:
            current = (
                await db.execute(
                    text("SELECT draft_version_id FROM agents WHERE id=:id FOR UPDATE"),
                    {"id": agent_id},
                )
            ).scalar_one_or_none()
            if current is None:
                return None
            await db.execute(
                text("UPDATE agent_versions SET published_at=now() WHERE id=:version"),
                {"version": current},
            )
            await db.execute(
                text(
                    "INSERT INTO agent_versions(id,tenant_id,agent_id,version,system_prompt,greeting,llm,stt,tts,turn_config,behavior,rag,variables,created_by) SELECT :new,tenant_id,agent_id,version+1,system_prompt,greeting,llm,stt,tts,turn_config,behavior,rag,variables,created_by FROM agent_versions WHERE id=:current"
                ),
                {"new": new_draft, "current": current},
            )
            await db.execute(
                text(
                    "INSERT INTO agent_tools(tenant_id,agent_version_id,tool_id,enabled) SELECT tenant_id,:new,tool_id,enabled FROM agent_tools WHERE agent_version_id=:current"
                ),
                {"new": new_draft, "current": current},
            )
            await db.execute(
                text(
                    "UPDATE agents SET current_version_id=:current,draft_version_id=:draft,status='active',updated_at=now() WHERE id=:id"
                ),
                {"current": current, "draft": new_draft, "id": agent_id},
            )
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
                {
                    "external_id": data.get("external_id"),
                    "phone": data.get("phone"),
                    "email": data.get("email"),
                },
            )
            existing_id = existing.scalar_one_or_none()
            if existing_id:
                row = await db.execute(
                    text(
                        """UPDATE end_users SET external_id=COALESCE(:external_id,external_id),phone=COALESCE(:phone,phone),email=COALESCE(:email,email),name=COALESCE(:name,name),metadata=metadata || CAST(:metadata AS jsonb),last_seen_at=now(),updated_at=now() WHERE id=:id RETURNING *"""
                    ),
                    {
                        "id": existing_id,
                        "external_id": data.get("external_id"),
                        "phone": data.get("phone"),
                        "email": data.get("email"),
                        "name": data.get("name"),
                        "metadata": json.dumps(data.get("metadata", {})),
                    },
                )
                return dict(row.mappings().one())
            row = await db.execute(
                text(
                    "INSERT INTO end_users(id,tenant_id,external_id,phone,email,name,metadata,first_seen_at,last_seen_at) VALUES(:id,:tenant,:external_id,:phone,:email,:name,CAST(:metadata AS jsonb),now(),now()) RETURNING *"
                ),
                {
                    "id": uuid4(),
                    "tenant": tenant_id,
                    "external_id": data.get("external_id"),
                    "phone": data.get("phone"),
                    "email": data.get("email"),
                    "name": data.get("name"),
                    "metadata": json.dumps(data.get("metadata", {})),
                },
            )
            return dict(row.mappings().one())

    async def list_end_users(
        self, tenant_id: UUID, query: str | None = None
    ) -> list[dict[str, Any]]:
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(
                text(
                    "SELECT eu.*,count(c.id)::int AS calls_count FROM end_users eu "
                    "LEFT JOIN calls c ON c.end_user_id=eu.id "
                    "WHERE (CAST(:query AS text) IS NULL OR concat_ws(' ',eu.external_id,eu.phone,eu.email,eu.name) ILIKE '%' || CAST(:query AS text) || '%') "
                    "GROUP BY eu.id ORDER BY eu.last_seen_at DESC NULLS LAST LIMIT 200"
                ),
                {"query": query},
            )
            return [dict(item) for item in rows.mappings()]

    async def get_end_user(
        self, tenant_id: UUID, end_user_id: UUID
    ) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(text("SELECT * FROM end_users WHERE id=:id"), {"id": end_user_id})
            item = row.mappings().first()
            if not item:
                return None
            result = dict(item)
            calls = await db.execute(
                text("SELECT id,agent_id,channel,status,duration_s,summary,started_at FROM calls WHERE end_user_id=:id ORDER BY started_at DESC LIMIT 20"),
                {"id": end_user_id},
            )
            result["calls"] = [dict(call) for call in calls.mappings()]
            return result

    async def update_end_user(
        self, tenant_id: UUID, end_user_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        fields = [field for field in ("external_id", "phone", "email", "name") if field in data]
        assignments = [f"{field}=:{field}" for field in fields]
        params: dict[str, Any] = {"id": end_user_id, **{field: data[field] for field in fields}}
        if "metadata" in data:
            assignments.append("metadata=CAST(:metadata AS jsonb)")
            params["metadata"] = json.dumps(data["metadata"] or {})
        if not assignments:
            return await self.get_end_user(tenant_id, end_user_id)
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text(f"UPDATE end_users SET {', '.join(assignments)},updated_at=now() WHERE id=:id RETURNING *"),
                params,
            )
            item = row.mappings().first()
            return dict(item) if item else None

    async def anonymize_end_user(self, tenant_id: UUID, end_user_id: UUID) -> bool:
        async with self.tenant_session(tenant_id) as db:
            found = (
                await db.execute(text("SELECT 1 FROM end_users WHERE id=:id"), {"id": end_user_id})
            ).scalar_one_or_none()
            if not found:
                return False
            await db.execute(
                text("UPDATE call_turns SET text='[deleted]',updated_at=now() WHERE call_id IN (SELECT id FROM calls WHERE end_user_id=:id)") ,
                {"id": end_user_id},
            )
            await db.execute(
                text("UPDATE calls SET end_user_id=NULL,from_number=NULL,to_number=NULL,summary=NULL,variables='{}'::jsonb,metadata='{}'::jsonb,updated_at=now() WHERE end_user_id=:id"),
                {"id": end_user_id},
            )
            await db.execute(text("DELETE FROM end_users WHERE id=:id"), {"id": end_user_id})
            return True

    async def create_call(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        variables: dict[str, Any],
        metadata: dict[str, Any],
        *,
        agent_version_id: UUID | None = None,
        end_user_id: UUID | None = None,
        channel: str = "web",
        status: str = "queued",
        from_number: str | None = None,
        to_number: str | None = None,
        campaign_id: UUID | None = None,
    ) -> dict[str, Any]:
        call_id = uuid4()
        async with self.tenant_session(tenant_id) as db:
            await db.execute(
                text(
                    "INSERT INTO calls(id,tenant_id,agent_id,agent_version_id,end_user_id,channel,status,from_number,to_number,campaign_id,variables,metadata,started_at) "
                    "VALUES(:id,:tenant,:agent,:version,:end_user,:channel,:status,:from_number,:to_number,:campaign_id,CAST(:variables AS jsonb),CAST(:metadata AS jsonb),now())"
                ),
                {
                    "id": call_id,
                    "tenant": tenant_id,
                    "agent": agent_id,
                    "version": agent_version_id,
                    "end_user": end_user_id,
                    "channel": channel,
                    "status": status,
                    "from_number": from_number,
                    "to_number": to_number,
                    "campaign_id": campaign_id,
                    "variables": __import__("json").dumps(variables),
                    "metadata": __import__("json").dumps(metadata),
                },
            )
        return {
            "id": call_id,
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "agent_version_id": agent_version_id,
            "end_user_id": end_user_id,
            "channel": channel,
            "status": status,
            "from_number": from_number,
            "to_number": to_number,
            "campaign_id": campaign_id,
            "variables": variables,
            "metadata": metadata,
        }

    async def list_calls(
        self, tenant_id: UUID, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        filters = filters or {}
        clauses, params = [], {}
        for field in ("agent_id", "channel", "status", "end_user_id", "campaign_id"):
            if filters.get(field) is not None:
                clauses.append(f"{field}=:{field}")
                params[field] = filters[field]
        if filters.get("from") is not None:
            clauses.append("started_at >= CAST(:from_date AS date)")
            params["from_date"] = filters["from"]
        if filters.get("to") is not None:
            clauses.append("started_at < (CAST(:to_date AS date) + INTERVAL '1 day')")
            params["to_date"] = filters["to"]
        if filters.get("q"):
            clauses.append(
                "(calls.id::text ILIKE :q OR summary ILIKE :q "
                "OR EXISTS (SELECT 1 FROM call_turns ct WHERE ct.call_id=calls.id AND ct.text ILIKE :q) "
                "OR EXISTS (SELECT 1 FROM end_users eu WHERE eu.id=calls.end_user_id "
                "AND (eu.phone ILIKE :q OR eu.email ILIKE :q OR eu.name ILIKE :q)))"
            )
            params["q"] = f"%{filters['q']}%"
        async with self.tenant_session(tenant_id) as db:
            where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = await db.execute(
                text(f"SELECT * FROM calls{where} ORDER BY created_at DESC"), params
            )
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
            turns = await db.execute(
                text("SELECT * FROM call_turns WHERE call_id=:id ORDER BY ordinal"), {"id": call_id}
            )
            tools = await db.execute(
                text("SELECT * FROM call_tool_calls WHERE call_id=:id ORDER BY started_at,id"),
                {"id": call_id},
            )
            events = await db.execute(
                text("SELECT * FROM call_events WHERE call_id=:id ORDER BY at,id"), {"id": call_id}
            )
            recording = await db.execute(
                text("SELECT * FROM call_recordings WHERE call_id=:id"), {"id": call_id}
            )
            qa = await db.execute(text("SELECT * FROM call_qa WHERE call_id=:id"), {"id": call_id})
            return {
                **call,
                "turns": [dict(row) for row in turns.mappings()],
                "tool_calls": [dict(row) for row in tools.mappings()],
                "events": [dict(row) for row in events.mappings()],
                "recording": dict(item) if (item := recording.mappings().first()) else None,
                "qa": dict(item) if (item := qa.mappings().first()) else None,
            }

    async def upsert_call_qa(self, tenant_id: UUID, call_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        if not await self.get_call(tenant_id, call_id):
            return None
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text("INSERT INTO call_qa(id,tenant_id,call_id,score,rubric,issues,model) VALUES(:id,:tenant,:call,:score,CAST(:rubric AS jsonb),:issues,:model) ON CONFLICT(call_id) DO UPDATE SET score=excluded.score,rubric=excluded.rubric,issues=excluded.issues,model=excluded.model,updated_at=now() RETURNING *"),
                {"id": uuid4(), "tenant": tenant_id, "call": call_id, "score": int(data["score"]), "rubric": json.dumps(data.get("rubric", {})), "issues": list(data.get("issues", [])), "model": data.get("model", "manual")},
            )
            return dict(row.mappings().one())

    async def update_call(
        self, tenant_id: UUID, call_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        return await self._update_call(tenant_id, call_id, data, internal=False)

    async def expire_stale_calls(self) -> int:
        """Close calls that lost their signaling or worker heartbeat."""
        async with self._internal_session() as db:
            rows = await db.execute(
                text(
                    "SELECT id FROM calls WHERE status IN ('queued','ringing','in_progress') "
                    "AND COALESCE(updated_at,started_at,created_at) < "
                    "CASE status WHEN 'in_progress' THEN now()-interval '2 hours' "
                    "ELSE now()-interval '5 minutes' END"
                )
            )
            call_ids = [row[0] for row in rows]
        for call_id in call_ids:
            await self.update_internal_call(
                call_id,
                {"status": "failed", "end_reason": "runtime_timeout", "ended_at": datetime.now(UTC)},
            )
        return len(call_ids)

    async def _update_call(
        self, tenant_id: UUID, call_id: UUID, data: dict[str, Any], *, internal: bool
    ) -> dict[str, Any] | None:
        allowed = {
            "status",
            "end_reason",
            "livekit_room",
            "answered_at",
            "ended_at",
            "duration_s",
            "billable_seconds",
            "cost",
            "latency",
            "summary",
            "outcome",
            "variables",
            "metadata",
            "provider_call_sid",
        }
        json_fields = {"cost", "latency", "outcome", "variables", "metadata"}
        assignments: list[str] = []
        params: dict[str, Any] = {"id": call_id}
        for field, value in data.items():
            if field not in allowed:
                continue
            params[field] = __import__("json").dumps(value) if field in json_fields else value
            assignments.append(
                f"{field}=CAST(:{field} AS jsonb)" if field in json_fields else f"{field}=:{field}"
            )
        if not assignments:
            return await self.get_call(tenant_id, call_id)
        context = self._internal_session() if internal else self.tenant_session(tenant_id)
        async with context as db:
            row = await db.execute(
                text(
                    f"UPDATE calls SET {', '.join(assignments)},updated_at=now() WHERE id=:id RETURNING *"
                ),
                params,
            )
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
                text(
                    "INSERT INTO calls(id,tenant_id,agent_id,agent_version_id,channel,status,livekit_room,variables,metadata,started_at) VALUES(:id,:tenant_id,:agent_id,:agent_version_id,:channel,'queued',:livekit_room,CAST(:variables AS jsonb),CAST(:metadata AS jsonb),now()) RETURNING *"
                ),
                {
                    **data,
                    "id": call_id,
                    "variables": __import__("json").dumps(data.get("variables", {})),
                    "metadata": __import__("json").dumps(data.get("metadata", {})),
                },
            )
            return dict(row.mappings().one())

    async def update_internal_call(
        self, call_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        async with self._internal_session() as db:
            tenant_id = (
                await db.execute(text("SELECT tenant_id FROM calls WHERE id=:id"), {"id": call_id})
            ).scalar_one_or_none()
        call = (
            await self._update_call(tenant_id, call_id, data, internal=True) if tenant_id else None
        )
        if call and call.get("status") in {
            "completed",
            "no_answer",
            "busy",
            "failed",
            "cancelled",
        }:
            async with self._internal_session() as db:
                await db.execute(
                    text(
                        "INSERT INTO usage_records(id,tenant_id,call_id,period,billable_seconds,channel,cost_usd) "
                        "SELECT gen_random_uuid(),tenant_id,id,date_trunc('month',COALESCE(ended_at,now()))::date,"
                        "GREATEST(0,EXTRACT(EPOCH FROM (COALESCE(ended_at,now())-CASE WHEN channel LIKE 'phone%' THEN COALESCE(answered_at,started_at) ELSE started_at END)))::int,"
                        "channel,COALESCE((cost->>'total_usd')::numeric,0) FROM calls WHERE id=:id "
                        "ON CONFLICT(call_id) DO UPDATE SET billable_seconds=EXCLUDED.billable_seconds,cost_usd=EXCLUDED.cost_usd,updated_at=now()"
                    ),
                    {"id": call_id},
                )
        if (
            call
            and call.get("campaign_id")
            and call.get("status") in {"completed", "no_answer", "busy", "failed", "cancelled"}
        ):
            async with self._internal_session() as db:
                row = await db.execute(
                    text(
                        "SELECT cc.id,cc.attempts,c.schedule FROM campaign_contacts cc "
                        "JOIN campaigns c ON c.id=cc.campaign_id WHERE cc.last_call_id=:call_id"
                    ),
                    {"call_id": call_id},
                )
                contact = row.mappings().first()
            if contact:
                status = str(call["status"])
                policy = dict(contact["schedule"] or {}).get("retry_policy", {})
                next_attempt = retry_at(
                    status, int(contact["attempts"]), policy, now=datetime.now(UTC)
                )
                await self.update_campaign_contact_internal(
                    contact["id"],
                    {
                        "status": "retry"
                        if next_attempt
                        else ("done" if status == "completed" else status),
                        "next_attempt_at": next_attempt,
                    },
                )
                async with self._internal_session() as db:
                    totals = (
                        (
                            await db.execute(
                                text(
                                    "SELECT campaign_id,count(*) AS total,count(*) FILTER (WHERE status IN ('pending','retry','calling')) AS remaining,"
                                    "count(*) FILTER (WHERE status='done') AS done,count(*) FILTER (WHERE status NOT IN ('pending','retry','calling','done')) AS failed "
                                    "FROM campaign_contacts WHERE campaign_id=(SELECT campaign_id FROM campaign_contacts WHERE id=:id) GROUP BY campaign_id"
                                ),
                                {"id": contact["id"]},
                            )
                        )
                        .mappings()
                        .first()
                    )
                    if totals:
                        await db.execute(
                            text(
                                "UPDATE campaigns SET stats=CAST(:stats AS jsonb),status=CASE WHEN :remaining=0 THEN 'completed' ELSE status END,updated_at=now() WHERE id=:id"
                            ),
                            {
                                "id": totals["campaign_id"],
                                "remaining": totals["remaining"],
                                "stats": json.dumps(
                                    {
                                        "total": totals["total"],
                                        "done": totals["done"],
                                        "failed": totals["failed"],
                                        "remaining": totals["remaining"],
                                    }
                                ),
                            },
                        )
        return call

    async def _call_tenant(self, db: AsyncSession, call_id: UUID) -> UUID | None:
        return (
            await db.execute(text("SELECT tenant_id FROM calls WHERE id=:id"), {"id": call_id})
        ).scalar_one_or_none()

    async def get_call_tenant(self, call_id: UUID) -> UUID | None:
        async with self._internal_session() as db:
            return await self._call_tenant(db, call_id)

    async def upsert_call_recording(
        self, call_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
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
                {
                    "id": uuid4(),
                    "tenant": tenant_id,
                    "call": call_id,
                    "s3_key": data["s3_key"],
                    "format": data.get("format", "ogg"),
                    "duration_s": data.get("duration_s"),
                    "size_bytes": data.get("size_bytes"),
                    "status": data["status"],
                },
            )
            return dict(row.mappings().one())

    async def append_call_events(self, call_id: UUID, events: list[dict[str, Any]]) -> int:
        async with self._internal_session() as db:
            tenant_id = await self._call_tenant(db, call_id)
            if not tenant_id:
                return 0
            for event in events:
                await db.execute(
                    text(
                        "INSERT INTO call_events(tenant_id,call_id,type,payload,at) VALUES(:tenant,:call,:type,CAST(:payload AS jsonb),:at)"
                    ),
                    {
                        "tenant": tenant_id,
                        "call": call_id,
                        "type": event["type"],
                        "payload": __import__("json").dumps(event.get("payload", {})),
                        "at": event["at"],
                    },
                )
            return len(events)

    async def append_call_turns(self, call_id: UUID, turns: list[dict[str, Any]]) -> int:
        async with self._internal_session() as db:
            tenant_id = await self._call_tenant(db, call_id)
            if not tenant_id:
                return 0
            for turn in turns:
                values = {
                    "id": turn.get("id") or uuid4(),
                    "tenant": tenant_id,
                    "call": call_id,
                    "ordinal": turn["ordinal"],
                    "role": turn["role"],
                    "text": turn.get("text"),
                    "started_at": turn.get("started_at"),
                    "ended_at": turn.get("ended_at"),
                    "interrupted": bool(turn.get("interrupted", False)),
                    "ttfb_ms": turn.get("ttfb_ms"),
                    "stt_confidence": turn.get("stt_confidence"),
                    "audio_offset_ms": int(turn.get("audio_offset_ms", 0)),
                }
                await db.execute(
                    text(
                        "INSERT INTO call_turns(id,tenant_id,call_id,ordinal,role,text,started_at,ended_at,interrupted,ttfb_ms,stt_confidence,audio_offset_ms) VALUES(:id,:tenant,:call,:ordinal,:role,:text,:started_at,:ended_at,:interrupted,:ttfb_ms,:stt_confidence,:audio_offset_ms)"
                    ),
                    values,
                )
            return len(turns)

    async def append_call_tool_call(
        self, call_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        async with self._internal_session() as db:
            tenant_id = await self._call_tenant(db, call_id)
            if not tenant_id:
                return None
            values = {
                **data,
                "id": data.get("id") or uuid4(),
                "tenant": tenant_id,
                "call": call_id,
                "arguments": __import__("json").dumps(data["arguments"]),
                "result": __import__("json").dumps(data.get("result")),
            }
            row = await db.execute(
                text(
                    "INSERT INTO call_tool_calls(id,tenant_id,call_id,turn_id,tool_id,name,arguments,result,status,duration_ms,started_at) VALUES(:id,:tenant,:call,:turn_id,:tool_id,:name,CAST(:arguments AS jsonb),CAST(:result AS jsonb),:status,:duration_ms,:started_at) RETURNING *"
                ),
                values,
            )
            return dict(row.mappings().one())

    async def create_tool(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        import json

        tool_id = uuid4()
        async with self.tenant_session(tenant_id) as db:
            await db.execute(
                text(
                    "INSERT INTO tools(id,tenant_id,name,description,type,native_kind,parameters_schema,webhook,mcp,speak_before,is_async) VALUES(:id,:tenant,:name,:description,:type,:native_kind,CAST(:schema AS jsonb),CAST(:webhook AS jsonb),CAST(:mcp AS jsonb),:speak_before,:is_async)"
                ),
                {
                    "id": tool_id,
                    "tenant": tenant_id,
                    "name": data["name"],
                    "description": data["description"],
                    "type": data["type"],
                    "native_kind": data.get("native_kind"),
                    "schema": json.dumps(data["parameters_schema"]),
                    "webhook": json.dumps(data.get("webhook")),
                    "mcp": json.dumps(data.get("mcp")),
                    "speak_before": data.get("speak_before"),
                    "is_async": data.get("async", False),
                },
            )
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

    async def update_tool(
        self, tenant_id: UUID, tool_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        json_fields = {"parameters_schema", "webhook", "mcp"}
        column_names = {"async": "is_async"}
        assignments, params = [], {"id": tool_id}
        for field, value in data.items():
            column = column_names.get(field, field)
            params[field] = __import__("json").dumps(value) if field in json_fields else value
            assignments.append(
                f"{column}=CAST(:{field} AS jsonb)"
                if field in json_fields
                else f"{column}=:{field}"
            )
        if not assignments:
            return await self.get_tool(tenant_id, tool_id)
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text(
                    f"UPDATE tools SET {', '.join(assignments)},updated_at=now() WHERE id=:id RETURNING *"
                ),
                params,
            )
            mapping = row.mappings().first()
            return dict(mapping) if mapping else None

    async def delete_tool(self, tenant_id: UUID, tool_id: UUID) -> bool:
        async with self.tenant_session(tenant_id) as db:
            result = await db.execute(
                text("DELETE FROM tools WHERE id=:id RETURNING id"), {"id": tool_id}
            )
            return result.scalar_one_or_none() is not None

    async def set_draft_tools(
        self, tenant_id: UUID, agent_id: UUID, tool_ids: list[UUID]
    ) -> list[dict[str, Any]] | None:
        async with self.tenant_session(tenant_id) as db:
            draft_id = (
                await db.execute(
                    text("SELECT draft_version_id FROM agents WHERE id=:id AND deleted_at IS NULL"),
                    {"id": agent_id},
                )
            ).scalar_one_or_none()
            if draft_id is None:
                return None
            if tool_ids:
                count = (
                    await db.execute(
                        text("SELECT count(*) FROM tools WHERE id = ANY(:ids)"), {"ids": tool_ids}
                    )
                ).scalar_one()
                if count != len(set(tool_ids)):
                    raise ValueError("one or more tools do not belong to tenant")
            await db.execute(
                text("DELETE FROM agent_tools WHERE agent_version_id=:version"),
                {"version": draft_id},
            )
            for tool_id in dict.fromkeys(tool_ids):
                await db.execute(
                    text(
                        "INSERT INTO agent_tools(tenant_id,agent_version_id,tool_id,enabled) VALUES(:tenant,:version,:tool,true)"
                    ),
                    {"tenant": tenant_id, "version": draft_id, "tool": tool_id},
                )
        return [tool for tool_id in tool_ids if (tool := await self.get_tool(tenant_id, tool_id))]

    async def get_runtime(self, agent_id: UUID, version: str = "current") -> dict[str, Any] | None:
        async with SessionFactory() as db, db.begin():
            await db.execute(text("SET LOCAL row_security = off"))
            agent_row = await db.execute(
                text(
                    "SELECT tenant_id,current_version_id,draft_version_id FROM agents WHERE id=:id AND deleted_at IS NULL"
                ),
                {"id": agent_id},
            )
            agent = agent_row.mappings().first()
            if not agent:
                return None
            try:
                version_id = (
                    agent["current_version_id"]
                    if version == "current"
                    else agent["draft_version_id"]
                    if version == "draft"
                    else UUID(version)
                )
            except ValueError:
                return None
            if version_id is None:
                return None
            row = await db.execute(
                text(
                    "SELECT a.id agent_id,a.tenant_id,a.name,t.name tenant_name,t.settings tenant_settings,v.id version_id,v.system_prompt,"
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
            tools = await db.execute(
                text(
                    "SELECT t.* FROM tools t JOIN agent_tools at ON at.tool_id=t.id WHERE at.agent_version_id=:version AND at.enabled ORDER BY t.name"
                ),
                {"version": version_id},
            )
            visible_tools = []
            for tool in tools.mappings():
                item = dict(tool)
                mcp = item.get("mcp") or {}
                if item.get("type") == "mcp" and not (mcp.get("enabled") and mcp.get("approved")):
                    continue
                visible_tools.append(item)
            return {**dict(mapping), "tools": visible_tools}

    async def list_knowledge_bases(self, tenant_id: UUID) -> list[dict[str, Any]]:
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(text("SELECT * FROM knowledge_bases ORDER BY created_at DESC"))
            return [dict(row) for row in rows.mappings()]

    async def create_knowledge_base(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        kb_id = uuid4()
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text(
                    "INSERT INTO knowledge_bases(id,tenant_id,name,embedding_model,chunk_size,chunk_overlap,status) VALUES(:id,:tenant,:name,:embedding_model,:chunk_size,:chunk_overlap,'ready') RETURNING *"
                ),
                {"id": kb_id, "tenant": tenant_id, **data},
            )
            return dict(row.mappings().one())

    async def get_knowledge_base(self, tenant_id: UUID, kb_id: UUID) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text("SELECT * FROM knowledge_bases WHERE id=:id"), {"id": kb_id}
            )
            mapping = row.mappings().first()
            return dict(mapping) if mapping else None

    async def update_knowledge_base(
        self, tenant_id: UUID, kb_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        if not data:
            return await self.get_knowledge_base(tenant_id, kb_id)
        assignments = [f"{field}=:{field}" for field in data]
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text(
                    f"UPDATE knowledge_bases SET {', '.join(assignments)},updated_at=now() WHERE id=:id RETURNING *"
                ),
                {"id": kb_id, **data},
            )
            mapping = row.mappings().first()
            return dict(mapping) if mapping else None

    async def delete_knowledge_base(self, tenant_id: UUID, kb_id: UUID) -> bool:
        async with self.tenant_session(tenant_id) as db:
            result = await db.execute(
                text("DELETE FROM knowledge_bases WHERE id=:id RETURNING id"), {"id": kb_id}
            )
            return result.scalar_one_or_none() is not None

    async def list_documents(self, tenant_id: UUID, kb_id: UUID) -> list[dict[str, Any]]:
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(
                text(
                    "SELECT * FROM documents WHERE knowledge_base_id=:kb AND deleted_at IS NULL ORDER BY created_at DESC"
                ),
                {"kb": kb_id},
            )
            return [dict(row) for row in rows.mappings()]

    async def create_document(
        self, tenant_id: UUID, kb_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        if not await self.get_knowledge_base(tenant_id, kb_id):
            return None
        document_id = uuid4()
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text(
                    "INSERT INTO documents(id,tenant_id,knowledge_base_id,name,source_type,source_uri,mime,size_bytes,status) VALUES(:id,:tenant,:kb,:name,:source_type,:source_uri,:mime,:size_bytes,'pending') RETURNING *"
                ),
                {
                    "id": document_id,
                    "tenant": tenant_id,
                    "kb": kb_id,
                    "name": data["name"],
                    "source_type": data["source_type"],
                    "source_uri": data.get("source_uri"),
                    "mime": data.get("mime"),
                    "size_bytes": data.get("size_bytes"),
                },
            )
            return dict(row.mappings().one())

    async def delete_document(self, tenant_id: UUID, kb_id: UUID, document_id: UUID) -> bool:
        async with self.tenant_session(tenant_id) as db:
            result = await db.execute(
                text(
                    "UPDATE documents SET deleted_at=now(),updated_at=now() WHERE id=:id AND knowledge_base_id=:kb AND deleted_at IS NULL RETURNING id"
                ),
                {"id": document_id, "kb": kb_id},
            )
            return result.scalar_one_or_none() is not None

    async def complete_document(
        self, tenant_id: UUID, document_id: UUID, chunks: list[dict[str, Any]]
    ) -> None:
        import json

        async with self.tenant_session(tenant_id) as db:
            document = (
                await db.execute(
                    text("SELECT knowledge_base_id FROM documents WHERE id=:id FOR UPDATE"),
                    {"id": document_id},
                )
            ).scalar_one()
            await db.execute(text("DELETE FROM chunks WHERE document_id=:id"), {"id": document_id})
            for ordinal, chunk in enumerate(chunks):
                vector = "[" + ",".join(str(value) for value in chunk["embedding"]) + "]"
                await db.execute(
                    text(
                        "INSERT INTO chunks(id,tenant_id,document_id,knowledge_base_id,ordinal,content,embedding,metadata,token_count) VALUES(:id,:tenant,:document,:kb,:ordinal,:content,CAST(:embedding AS vector),CAST(:metadata AS jsonb),:tokens)"
                    ),
                    {
                        "id": uuid4(),
                        "tenant": tenant_id,
                        "document": document_id,
                        "kb": document,
                        "ordinal": ordinal,
                        "content": chunk["content"],
                        "embedding": vector,
                        "metadata": json.dumps(chunk.get("metadata", {})),
                        "tokens": chunk["token_count"],
                    },
                )
            await db.execute(
                text(
                    "UPDATE documents SET status='ready',error=NULL,chunk_count=:count,updated_at=now() WHERE id=:id"
                ),
                {"id": document_id, "count": len(chunks)},
            )

    async def fail_document(self, tenant_id: UUID, document_id: UUID, error: str) -> None:
        async with self.tenant_session(tenant_id) as db:
            await db.execute(
                text(
                    "UPDATE documents SET status='error',error=:error,updated_at=now() WHERE id=:id"
                ),
                {"id": document_id, "error": error[:1000]},
            )

    async def query_chunks(
        self, tenant_id: UUID, kb_id: UUID, embedding: list[float], top_k: int, min_score: float
    ) -> list[dict[str, Any]]:
        vector = "[" + ",".join(str(value) for value in embedding) + "]"
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(
                text(
                    "SELECT id,document_id,ordinal,content,metadata,token_count,1-(embedding <=> CAST(:embedding AS vector)) AS score FROM chunks WHERE knowledge_base_id=:kb AND 1-(embedding <=> CAST(:embedding AS vector)) >= :score ORDER BY embedding <=> CAST(:embedding AS vector) LIMIT :limit"
                ),
                {"embedding": vector, "kb": kb_id, "score": min_score, "limit": top_k},
            )
            return [dict(row) for row in rows.mappings()]

    async def get_knowledge_base_tenant(self, kb_id: UUID) -> UUID | None:
        async with self._internal_session() as db:
            return (
                await db.execute(
                    text("SELECT tenant_id FROM knowledge_bases WHERE id=:id"), {"id": kb_id}
                )
            ).scalar_one_or_none()

    async def create_secret(
        self, tenant_id: UUID, name: str, ciphertext: bytes, key_id: str
    ) -> dict[str, Any]:
        secret_id = uuid4()
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text(
                    "INSERT INTO secrets(id,tenant_id,name,ciphertext,kms_key_id) VALUES(:id,:tenant,:name,:ciphertext,:key) RETURNING id,tenant_id,name,kms_key_id,created_at,rotated_at"
                ),
                {
                    "id": secret_id,
                    "tenant": tenant_id,
                    "name": name,
                    "ciphertext": ciphertext,
                    "key": key_id,
                },
            )
            return dict(row.mappings().one())

    async def list_secrets(self, tenant_id: UUID) -> list[dict[str, Any]]:
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(
                text(
                    "SELECT id,tenant_id,name,kms_key_id,created_at,rotated_at FROM secrets ORDER BY created_at DESC"
                )
            )
            return [dict(row) for row in rows.mappings()]

    async def get_secret(self, tenant_id: UUID, secret_id: UUID) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(text("SELECT * FROM secrets WHERE id=:id"), {"id": secret_id})
            mapping = row.mappings().first()
            return dict(mapping) if mapping else None

    async def delete_secret(self, tenant_id: UUID, secret_id: UUID) -> bool:
        async with self.tenant_session(tenant_id) as db:
            result = await db.execute(
                text("DELETE FROM secrets WHERE id=:id RETURNING id"), {"id": secret_id}
            )
            return result.scalar_one_or_none() is not None

    async def get_integration(self, tenant_id: UUID, provider: str) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text(
                    "SELECT * FROM integrations WHERE provider=:provider ORDER BY updated_at DESC LIMIT 1"
                ),
                {"provider": provider},
            )
            mapping = row.mappings().first()
            return dict(mapping) if mapping else None

    async def upsert_integration(
        self, tenant_id: UUID, provider: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        async with self.tenant_session(tenant_id) as db:
            existing = (
                await db.execute(
                    text(
                        "SELECT id FROM integrations WHERE provider=:provider ORDER BY updated_at DESC LIMIT 1 FOR UPDATE"
                    ),
                    {"provider": provider},
                )
            ).scalar_one_or_none()
            if existing:
                row = await db.execute(
                    text(
                        "UPDATE integrations SET scopes=:scopes,refresh_token_secret_id=:secret,account_email=:email,status=:status,config=CAST(:config AS jsonb),updated_at=now() WHERE id=:id RETURNING *"
                    ),
                    {
                        "id": existing,
                        "scopes": data["scopes"],
                        "secret": data.get("refresh_token_secret_id"),
                        "email": data.get("account_email"),
                        "status": data["status"],
                        "config": json.dumps(data.get("config", {})),
                    },
                )
            else:
                row = await db.execute(
                    text(
                        "INSERT INTO integrations(id,tenant_id,provider,scopes,refresh_token_secret_id,account_email,status,config) VALUES(:id,:tenant,:provider,:scopes,:secret,:email,:status,CAST(:config AS jsonb)) RETURNING *"
                    ),
                    {
                        "id": uuid4(),
                        "tenant": tenant_id,
                        "provider": provider,
                        "scopes": data["scopes"],
                        "secret": data.get("refresh_token_secret_id"),
                        "email": data.get("account_email"),
                        "status": data["status"],
                        "config": json.dumps(data.get("config", {})),
                    },
                )
            return dict(row.mappings().one())

    async def list_campaigns(self, tenant_id: UUID) -> list[dict[str, Any]]:
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(text("SELECT * FROM campaigns ORDER BY created_at DESC"))
            return [dict(row) for row in rows.mappings()]

    async def create_campaign(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text(
                    "INSERT INTO campaigns(id,tenant_id,agent_id,name,status,schedule,stats) VALUES(:id,:tenant,:agent,:name,'draft',CAST(:schedule AS jsonb),'{}'::jsonb) RETURNING *"
                ),
                {
                    "id": uuid4(),
                    "tenant": tenant_id,
                    "agent": data["agent_id"],
                    "name": data["name"],
                    "schedule": json.dumps(data["schedule"]),
                },
            )
            return dict(row.mappings().one())

    async def get_campaign(self, tenant_id: UUID, campaign_id: UUID) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text("SELECT * FROM campaigns WHERE id=:id"), {"id": campaign_id}
            )
            item = row.mappings().first()
            return dict(item) if item else None

    async def update_campaign(
        self, tenant_id: UUID, campaign_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        allowed = {"name", "status", "schedule", "stats"}
        values = {key: value for key, value in data.items() if key in allowed}
        if not values:
            return await self.get_campaign(tenant_id, campaign_id)
        assignments: list[str] = []
        params: dict[str, Any] = {"id": campaign_id}
        for key, value in values.items():
            if key in {"schedule", "stats"}:
                assignments.append(f"{key}=CAST(:{key} AS jsonb)")
                params[key] = json.dumps(value)
            else:
                assignments.append(f"{key}=:{key}")
                params[key] = value
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text(
                    f"UPDATE campaigns SET {','.join(assignments)},updated_at=now() WHERE id=:id RETURNING *"
                ),
                params,
            )
            item = row.mappings().first()
            return dict(item) if item else None

    async def add_campaign_contacts(
        self, tenant_id: UUID, campaign_id: UUID, contacts: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        created: list[dict[str, Any]] = []
        async with self.tenant_session(tenant_id) as db:
            for contact in contacts:
                row = await db.execute(
                    text(
                        "INSERT INTO campaign_contacts(id,tenant_id,campaign_id,phone,name,variables,status,attempts) VALUES(:id,:tenant,:campaign,:phone,:name,CAST(:variables AS jsonb),'pending',0) RETURNING *"
                    ),
                    {
                        "id": uuid4(),
                        "tenant": tenant_id,
                        "campaign": campaign_id,
                        "phone": contact["phone"],
                        "name": contact.get("name"),
                        "variables": json.dumps(contact.get("variables", {})),
                    },
                )
                created.append(dict(row.mappings().one()))
        return created

    async def list_campaign_contacts(
        self, tenant_id: UUID, campaign_id: UUID, status: str | None = None
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM campaign_contacts WHERE campaign_id=:id"
        params: dict[str, Any] = {"id": campaign_id}
        if status:
            query += " AND status=:status"
            params["status"] = status
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(text(query + " ORDER BY created_at,id"), params)
            return [dict(row) for row in rows.mappings()]

    async def list_do_not_call(self, tenant_id: UUID) -> list[dict[str, Any]]:
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(text("SELECT * FROM do_not_call ORDER BY created_at DESC"))
            return [dict(row) for row in rows.mappings()]

    async def add_do_not_call(
        self, tenant_id: UUID, phone: str, reason: str | None
    ) -> dict[str, Any]:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text(
                    "INSERT INTO do_not_call(id,tenant_id,phone,reason) VALUES(:id,:tenant,:phone,:reason) ON CONFLICT(tenant_id,phone) DO UPDATE SET reason=EXCLUDED.reason RETURNING *"
                ),
                {"id": uuid4(), "tenant": tenant_id, "phone": phone, "reason": reason},
            )
            return dict(row.mappings().one())

    async def remove_do_not_call(self, tenant_id: UUID, phone: str) -> bool:
        async with self.tenant_session(tenant_id) as db:
            result = await db.execute(
                text("DELETE FROM do_not_call WHERE phone=:phone RETURNING id"), {"phone": phone}
            )
            return result.first() is not None

    async def claim_campaign_contacts(self, limit: int = 100) -> list[dict[str, Any]]:
        async with self._internal_session() as db:
            rows = await db.execute(
                text(
                    "WITH candidates AS ("
                    " SELECT cc.id FROM campaign_contacts cc JOIN campaigns c ON c.id=cc.campaign_id"
                    " WHERE c.status='running' AND cc.status IN ('pending','retry')"
                    " AND (cc.next_attempt_at IS NULL OR cc.next_attempt_at<=now())"
                    " AND NOT EXISTS (SELECT 1 FROM do_not_call d WHERE d.tenant_id=cc.tenant_id AND d.phone=cc.phone)"
                    " ORDER BY cc.next_attempt_at NULLS FIRST,cc.created_at FOR UPDATE OF cc SKIP LOCKED LIMIT :limit"
                    ") UPDATE campaign_contacts cc SET status='calling',attempts=attempts+1,updated_at=now()"
                    " FROM candidates x,campaigns c WHERE cc.id=x.id AND c.id=cc.campaign_id"
                    " RETURNING cc.*,c.agent_id,c.schedule,c.stats"
                ),
                {"limit": limit},
            )
            return [dict(row) for row in rows.mappings()]

    async def update_campaign_contact_internal(
        self, contact_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        allowed = {"status", "last_call_id", "next_attempt_at"}
        values = {key: value for key, value in data.items() if key in allowed}
        if not values:
            return None
        params: dict[str, Any] = {"id": contact_id, **values}
        assignments = ",".join(f"{key}=:{key}" for key in values)
        async with self._internal_session() as db:
            row = await db.execute(
                text(
                    f"UPDATE campaign_contacts SET {assignments},updated_at=now() WHERE id=:id RETURNING *"
                ),
                params,
            )
            item = row.mappings().first()
            return dict(item) if item else None

    async def get_plan_concurrency(self, tenant_id: UUID) -> int:
        async with self._internal_session() as db:
            value = await db.execute(
                text(
                    "SELECT COALESCE(p.max_concurrent_calls,1) FROM subscriptions s "
                    "JOIN plans p ON p.id=s.plan_id WHERE s.tenant_id=:tenant "
                    "AND s.status IN ('active','trialing') ORDER BY s.created_at DESC LIMIT 1"
                ),
                {"tenant": tenant_id},
            )
            return int(value.scalar_one_or_none() or 1)

    async def get_billing_plan(self, tenant_id: UUID) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text(
                    "SELECT p.*,s.id AS subscription_id,s.status AS subscription_status,s.current_period_start,s.current_period_end,"
                    "t.status AS tenant_status,t.stripe_customer_id,t.created_at AS tenant_created_at FROM tenants t "
                    "LEFT JOIN LATERAL (SELECT * FROM subscriptions sx WHERE sx.tenant_id=t.id ORDER BY sx.created_at DESC LIMIT 1) s ON true "
                    "JOIN plans p ON p.id=COALESCE(s.plan_id,(SELECT id FROM plans WHERE code='trial')) WHERE t.id=:tenant"
                ),
                {"tenant": tenant_id},
            )
            item = row.mappings().first()
            return dict(item) if item else None

    async def get_plan_by_code(self, code: str) -> dict[str, Any] | None:
        async with self._internal_session() as db:
            row = await db.execute(text("SELECT * FROM plans WHERE code=:code"), {"code": code})
            item = row.mappings().first()
            return dict(item) if item else None

    async def get_billing_usage(self, tenant_id: UUID, period: date) -> dict[str, Any]:
        plan = await self.get_billing_plan(tenant_id)
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text(
                    "SELECT COALESCE(sum(CEIL(billable_seconds/60.0)),0)::int AS minutes,COALESCE(sum(cost_usd),0) AS cost_usd,count(*) AS calls "
                    "FROM usage_records WHERE period=:period"
                ),
                {"period": period},
            )
            usage = dict(row.mappings().one())
        included = int((plan or {}).get("included_minutes") or 0)
        used = int(usage["minutes"])
        overage = max(0, used - included)
        return {
            **usage,
            "period": period.isoformat()[:7],
            "included_minutes": included,
            "overage_minutes": overage,
            "estimated_overage_cents": overage
            * int((plan or {}).get("overage_cents_per_min") or 0),
        }

    async def list_invoices(self, tenant_id: UUID) -> list[dict[str, Any]]:
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(
                text("SELECT * FROM invoices ORDER BY period_start DESC NULLS LAST,created_at DESC")
            )
            return [dict(row) for row in rows.mappings()]

    async def upsert_invoice(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        async with self._internal_session() as db:
            row = await db.execute(
                text(
                    "INSERT INTO invoices(id,tenant_id,stripe_invoice_id,period_start,period_end,amount_cents,status,pdf_url) "
                    "VALUES(:id,:tenant,:stripe_id,:start,:end,:amount,:status,:pdf) "
                    "ON CONFLICT(stripe_invoice_id) DO UPDATE SET period_start=EXCLUDED.period_start,period_end=EXCLUDED.period_end,amount_cents=EXCLUDED.amount_cents,status=EXCLUDED.status,pdf_url=EXCLUDED.pdf_url,updated_at=now() RETURNING *"
                ),
                {
                    "id": uuid4(),
                    "tenant": tenant_id,
                    "stripe_id": data["stripe_invoice_id"],
                    "start": data.get("period_start"),
                    "end": data.get("period_end"),
                    "amount": data.get("amount_cents", 0),
                    "status": data["status"],
                    "pdf": data.get("pdf_url"),
                },
            )
            return dict(row.mappings().one())

    async def upsert_subscription(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        async with self._internal_session() as db:
            plan_id = (
                await db.execute(
                    text("SELECT id FROM plans WHERE code=:code"), {"code": data["plan_code"]}
                )
            ).scalar_one()
            row = await db.execute(
                text(
                    "INSERT INTO subscriptions(id,tenant_id,plan_id,stripe_subscription_id,status,current_period_start,current_period_end,cancel_at,stripe_overage_item_id,stripe_phone_item_id,past_due_since) "
                    "VALUES(:id,:tenant,:plan,:stripe_id,:status,:start,:end,:cancel_at,:overage_item,:phone_item,:past_due_since) "
                    "ON CONFLICT(stripe_subscription_id) DO UPDATE SET plan_id=EXCLUDED.plan_id,status=EXCLUDED.status,current_period_start=EXCLUDED.current_period_start,current_period_end=EXCLUDED.current_period_end,cancel_at=EXCLUDED.cancel_at,stripe_overage_item_id=COALESCE(EXCLUDED.stripe_overage_item_id,subscriptions.stripe_overage_item_id),stripe_phone_item_id=COALESCE(EXCLUDED.stripe_phone_item_id,subscriptions.stripe_phone_item_id),past_due_since=EXCLUDED.past_due_since,updated_at=now() RETURNING *"
                ),
                {
                    "id": uuid4(),
                    "tenant": tenant_id,
                    "plan": plan_id,
                    "stripe_id": data.get("stripe_subscription_id"),
                    "status": data["status"],
                    "start": data.get("current_period_start"),
                    "end": data.get("current_period_end"),
                    "cancel_at": data.get("cancel_at"),
                    "overage_item": data.get("stripe_overage_item_id"),
                    "phone_item": data.get("stripe_phone_item_id"),
                    "past_due_since": data.get("past_due_since"),
                },
            )
            return dict(row.mappings().one())

    async def update_billing_tenant(
        self, tenant_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        allowed = {"status", "stripe_customer_id"}
        values = {key: value for key, value in data.items() if key in allowed}
        if not values:
            return await self.get_tenant(tenant_id)
        params: dict[str, Any] = {"id": tenant_id, **values}
        assignments = ",".join(f"{key}=:{key}" for key in values)
        async with self._internal_session() as db:
            row = await db.execute(
                text(f"UPDATE tenants SET {assignments},updated_at=now() WHERE id=:id RETURNING *"),
                params,
            )
            item = row.mappings().first()
            return dict(item) if item else None

    async def billing_meter_batches(self) -> list[dict[str, Any]]:
        async with self._internal_session() as db:
            await db.execute(
                text(
                    "UPDATE tenants t SET status='suspended',updated_at=now() FROM subscriptions s "
                    "WHERE s.tenant_id=t.id AND s.status='past_due' AND s.past_due_since<=now()-interval '7 days'"
                )
            )
            rows = await db.execute(
                text(
                    "SELECT s.tenant_id,s.stripe_overage_item_id,s.stripe_phone_item_id,p.included_minutes,"
                    "COALESCE((SELECT sum(CEIL(u.billable_seconds/60.0)) FROM usage_records u WHERE u.tenant_id=s.tenant_id AND u.period=date_trunc('month',now())::date),0)::int total_minutes,"
                    "COALESCE((SELECT sum(CEIL(u.billable_seconds/60.0)) FROM usage_records u WHERE u.tenant_id=s.tenant_id AND u.period=date_trunc('month',now())::date AND u.stripe_usage_record_id IS NOT NULL),0)::int reported_minutes,"
                    "ARRAY(SELECT u.id FROM usage_records u WHERE u.tenant_id=s.tenant_id AND u.period=date_trunc('month',now())::date AND u.stripe_usage_record_id IS NULL) record_ids,"
                    "(SELECT count(*) FROM phone_numbers n WHERE n.tenant_id=s.tenant_id AND n.status='active')::int phone_quantity "
                    "FROM subscriptions s JOIN plans p ON p.id=s.plan_id WHERE s.status IN ('active','trialing')"
                )
            )
        batches = []
        for row in rows.mappings():
            item = dict(row)
            included = int(item["included_minutes"])
            item["overage_delta"] = max(0, int(item["total_minutes"]) - included) - max(
                0, int(item["reported_minutes"]) - included
            )
            batches.append(item)
        return batches

    async def mark_usage_reported(
        self, tenant_id: UUID, record_ids: list[UUID], stripe_id: str
    ) -> None:
        if not record_ids:
            return
        async with self._internal_session() as db:
            await db.execute(
                text(
                    "UPDATE usage_records SET stripe_usage_record_id=:stripe,updated_at=now() WHERE tenant_id=:tenant AND id=ANY(:ids)"
                ),
                {"stripe": stripe_id, "tenant": tenant_id, "ids": record_ids},
            )

    async def billing_threshold_events(self) -> list[dict[str, Any]]:
        period = datetime.now(UTC).date().replace(day=1)
        async with self._internal_session() as db:
            rows = await db.execute(
                text(
                    "WITH usage AS (SELECT s.tenant_id,p.included_minutes,COALESCE(sum(ceil(u.billable_seconds/60.0)),0)::int minutes FROM subscriptions s JOIN plans p ON p.id=s.plan_id LEFT JOIN usage_records u ON u.tenant_id=s.tenant_id AND u.period=:period WHERE s.status IN ('active','trialing') GROUP BY s.tenant_id,p.included_minutes), crossed AS (SELECT usage.*,v.threshold FROM usage CROSS JOIN (VALUES (80),(100)) v(threshold) WHERE included_minutes>0 AND minutes*100>=included_minutes*v.threshold) INSERT INTO billing_usage_alerts(tenant_id,period,threshold,minutes) SELECT tenant_id,:period,threshold,minutes FROM crossed ON CONFLICT DO NOTHING RETURNING tenant_id,period,threshold,minutes"
                ),
                {"period": period},
            )
            return [dict(row) for row in rows.mappings()]
    async def list_webhooks(self, tenant_id: UUID) -> list[dict[str, Any]]:
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(text("SELECT id,url,events,enabled,created_at,updated_at FROM webhooks_out ORDER BY created_at"))
            return [dict(row) for row in rows.mappings()]

    async def create_webhook(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text("INSERT INTO webhooks_out(id,tenant_id,url,events,secret_id,enabled) VALUES(:id,:tenant,:url,:events,:secret,:enabled) RETURNING id,url,events,enabled,created_at,updated_at"),
                {"id": uuid4(), "tenant": tenant_id, "url": data["url"], "events": data["events"], "secret": data["secret_id"], "enabled": data.get("enabled", True)},
            )
            return dict(row.mappings().one())

    async def update_webhook(self, tenant_id: UUID, webhook_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        fields = [field for field in ("url", "events", "enabled") if field in data]
        if not fields:
            return next((item for item in await self.list_webhooks(tenant_id) if item["id"] == webhook_id), None)
        params: dict[str, Any] = {"id": webhook_id, **{field: data[field] for field in fields}}
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text(f"UPDATE webhooks_out SET {', '.join(f'{field}=:{field}' for field in fields)},updated_at=now() WHERE id=:id RETURNING id,url,events,enabled,created_at,updated_at"),
                params,
            )
            item = row.mappings().first()
            return dict(item) if item else None

    async def delete_webhook(self, tenant_id: UUID, webhook_id: UUID) -> bool:
        async with self.tenant_session(tenant_id) as db:
            result = await db.execute(text("DELETE FROM webhooks_out WHERE id=:id RETURNING id"), {"id": webhook_id})
            return bool(result.scalar_one_or_none())

    async def list_webhook_deliveries(self, tenant_id: UUID, webhook_id: UUID) -> list[dict[str, Any]]:
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(text("SELECT * FROM webhook_deliveries WHERE webhook_id=:id ORDER BY created_at DESC LIMIT 200"), {"id": webhook_id})
            return [dict(row) for row in rows.mappings()]

    async def queue_webhook_event(self, tenant_id: UUID, event: str, data: dict[str, Any]) -> int:
        payload = {"id": f"evt_{uuid4().hex}", "type": event, "created_at": datetime.now(UTC).isoformat(), "tenant_id": str(tenant_id), "data": data}
        async with self.tenant_session(tenant_id) as db:
            result = await db.execute(
                text("INSERT INTO webhook_deliveries(id,tenant_id,webhook_id,event,payload,status,next_retry_at) SELECT gen_random_uuid(),tenant_id,id,:event,CAST(:payload AS jsonb),'pending',now() FROM webhooks_out WHERE enabled AND (:event=ANY(events) OR '*'=ANY(events)) RETURNING id"),
                {"event": event, "payload": json.dumps(payload, default=str)},
            )
            return len(result.scalars().all())

    async def claim_webhook_deliveries(self, limit: int = 100) -> list[dict[str, Any]]:
        async with self._internal_session() as db:
            rows = await db.execute(
                text("WITH picked AS (SELECT id FROM webhook_deliveries WHERE status IN ('pending','retrying') AND next_retry_at<=now() ORDER BY next_retry_at FOR UPDATE SKIP LOCKED LIMIT :limit) UPDATE webhook_deliveries d SET status='processing',attempts=attempts+1,updated_at=now() FROM picked WHERE d.id=picked.id RETURNING d.*"),
                {"limit": limit},
            )
            deliveries = [dict(row) for row in rows.mappings()]
            for item in deliveries:
                endpoint = (await db.execute(text("SELECT w.url,s.ciphertext,s.kms_key_id FROM webhooks_out w JOIN secrets s ON s.id=w.secret_id WHERE w.id=:id AND w.enabled"), {"id": item["webhook_id"]})).mappings().first()
                if endpoint:
                    item.update(dict(endpoint))
            return [item for item in deliveries if item.get("url")]

    async def update_webhook_delivery(self, delivery_id: UUID, data: dict[str, Any]) -> None:
        async with self._internal_session() as db:
            await db.execute(
                text("UPDATE webhook_deliveries SET status=:status,last_status_code=:code,next_retry_at=:retry,updated_at=now() WHERE id=:id"),
                {"id": delivery_id, "status": data["status"], "code": data.get("last_status_code"), "retry": data.get("next_retry_at")},
            )

    async def retry_webhook_delivery(self, tenant_id: UUID, webhook_id: UUID, delivery_id: UUID) -> bool:
        async with self.tenant_session(tenant_id) as db:
            result = await db.execute(
                text("UPDATE webhook_deliveries SET status='pending',attempts=0,next_retry_at=now(),updated_at=now() WHERE id=:id AND webhook_id=:webhook RETURNING id"),
                {"id": delivery_id, "webhook": webhook_id},
            )
            return bool(result.scalar_one_or_none())

    async def create_export(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text("INSERT INTO exports(id,tenant_id,type,filters,status,expires_at) VALUES(:id,:tenant,:type,CAST(:filters AS jsonb),'pending',now()+interval '7 days') RETURNING *"),
                {"id": uuid4(), "tenant": tenant_id, "type": data["type"], "filters": json.dumps(data.get("filters", {}))},
            )
            return dict(row.mappings().one())

    async def get_export(self, tenant_id: UUID, export_id: UUID) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(text("SELECT * FROM exports WHERE id=:id"), {"id": export_id})
            item = row.mappings().first()
            return dict(item) if item else None

    async def claim_exports(self, limit: int = 20) -> list[dict[str, Any]]:
        async with self._internal_session() as db:
            rows = await db.execute(
                text("WITH picked AS (SELECT id FROM exports WHERE status='pending' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT :limit) UPDATE exports e SET status='processing',updated_at=now() FROM picked WHERE e.id=picked.id RETURNING e.*"),
                {"limit": limit},
            )
            exports = [dict(row) for row in rows.mappings()]
            for item in exports:
                if item["type"] == "calls":
                    data = await db.execute(
                        text("SELECT id,agent_id,end_user_id,channel,status,end_reason,started_at,ended_at,duration_s,billable_seconds,summary,outcome,variables,metadata FROM calls WHERE tenant_id=:tenant ORDER BY started_at DESC LIMIT 10000"),
                        {"tenant": item["tenant_id"]},
                    )
                else:
                    filters = dict(item.get("filters") or {})
                    end_user_id = filters.get("id")
                    data = await db.execute(
                        text("SELECT id,external_id,phone,email,name,metadata,first_seen_at,last_seen_at FROM end_users WHERE tenant_id=:tenant AND (CAST(:id AS uuid) IS NULL OR id=CAST(:id AS uuid)) ORDER BY last_seen_at DESC LIMIT 10000"),
                        {"tenant": item["tenant_id"], "id": end_user_id},
                    )
                item["rows"] = [dict(row) for row in data.mappings()]
            return exports

    async def complete_export(self, export_id: UUID, s3_key: str | None, error: bool = False) -> None:
        async with self._internal_session() as db:
            await db.execute(
                text("UPDATE exports SET status=:status,s3_key=:key,updated_at=now() WHERE id=:id"),
                {"id": export_id, "status": "failed" if error else "ready", "key": s3_key},
            )

    async def purge_retention(self) -> dict[str, Any]:
        async with self._internal_session() as db:
            recordings = await db.execute(text("DELETE FROM call_recordings WHERE expires_at<now() RETURNING s3_key"))
            recording_keys = list(recordings.scalars())
            turns = await db.execute(
                text("UPDATE call_turns ct SET text='[retained-anonymized]',updated_at=now() FROM calls c JOIN tenants t ON t.id=c.tenant_id WHERE ct.call_id=c.id AND COALESCE((t.settings->>'anonymize_transcripts')::boolean,false) AND c.started_at<now()-make_interval(days=>COALESCE((t.settings->>'retention_days')::int,90)) AND ct.text<>'[retained-anonymized]' RETURNING ct.id")
            )
            document_rows = await db.execute(text("SELECT id,s3_key FROM documents WHERE deleted_at<now()-interval '30 days' FOR UPDATE"))
            documents = [dict(row) for row in document_rows.mappings()]
            if documents:
                ids = [item["id"] for item in documents]
                await db.execute(text("DELETE FROM chunks WHERE document_id=ANY(:ids)"), {"ids": ids})
                await db.execute(text("DELETE FROM documents WHERE id=ANY(:ids)"), {"ids": ids})
            return {"recording_keys": recording_keys, "document_keys": [item["s3_key"] for item in documents if item.get("s3_key")], "turns_anonymized": len(turns.scalars().all()), "documents_deleted": len(documents)}

    async def analytics_overview(self, tenant_id: UUID, start: date, end: date, agent_id: UUID | None = None) -> dict[str, Any]:
        params = {"start": start, "end": end + timedelta(days=1), "agent": agent_id}
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(
                text("SELECT count(*)::int calls,COALESCE(sum(COALESCE(billable_seconds,duration_s,0))/60.0,0)::float minutes,COALESCE(avg(duration_s),0)::float avg_duration,COALESCE(avg(CASE WHEN outcome->>'resolved'='true' THEN 1.0 ELSE 0.0 END),0)::float resolution_rate,COALESCE(avg(CASE WHEN end_reason='transferred' THEN 1.0 ELSE 0.0 END),0)::float transfer_rate,COALESCE(avg(CASE WHEN status IN ('no_answer','busy','cancelled') THEN 1.0 ELSE 0.0 END),0)::float abandon_rate,COALESCE(avg((latency->>'ttfb_p50_ms')::float),0)::float latency_p50,COALESCE(percentile_cont(0.95) WITHIN GROUP (ORDER BY (latency->>'ttfb_p95_ms')::float) FILTER (WHERE latency?'ttfb_p95_ms'),0)::float latency_p95,COALESCE(sum((cost->>'total')::numeric),0)::float cost,COALESCE(avg(q.score)/20.0,0)::float csat FROM calls c LEFT JOIN call_qa q ON q.call_id=c.id WHERE c.started_at>=:start AND c.started_at<:end AND (CAST(:agent AS uuid) IS NULL OR c.agent_id=CAST(:agent AS uuid))"),
                params,
            )
            result = dict(row.mappings().one())
            daily = await db.execute(
                text("SELECT date_trunc('day',started_at)::date date,count(*)::int calls,COALESCE(sum(COALESCE(billable_seconds,duration_s,0))/60.0,0)::float minutes FROM calls WHERE started_at>=:start AND started_at<:end AND (CAST(:agent AS uuid) IS NULL OR agent_id=CAST(:agent AS uuid)) GROUP BY 1 ORDER BY 1"),
                params,
            )
            result["series"] = [dict(item) for item in daily.mappings()]
            return result

    async def analytics_tools(self, tenant_id: UUID, start: date, end: date) -> list[dict[str, Any]]:
        async with self.tenant_session(tenant_id) as db:
            rows = await db.execute(
                text("SELECT name,count(*)::int calls,count(*) FILTER (WHERE status<>'ok')::int errors,COALESCE(avg(duration_ms),0)::float avg_duration_ms FROM call_tool_calls WHERE started_at>=:start AND started_at<:end GROUP BY name ORDER BY calls DESC,name"),
                {"start": start, "end": end + timedelta(days=1)},
            )
            return [dict(item) for item in rows.mappings()]

    async def admin_list_tenants(self) -> list[dict[str, Any]]:
        async with self._internal_session() as db:
            rows = await db.execute(
                text("SELECT t.id,t.slug,t.name,t.status,t.settings,t.created_at,p.code plan_code,s.status subscription_status,count(DISTINCT a.id)::int agents_count,count(DISTINCT c.id)::int calls_count FROM tenants t LEFT JOIN subscriptions s ON s.tenant_id=t.id LEFT JOIN plans p ON p.id=s.plan_id LEFT JOIN agents a ON a.tenant_id=t.id AND a.deleted_at IS NULL LEFT JOIN calls c ON c.tenant_id=t.id WHERE t.deleted_at IS NULL GROUP BY t.id,p.code,s.status ORDER BY t.created_at DESC")
            )
            return [dict(item) for item in rows.mappings()]

    async def admin_update_tenant(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        async with self._internal_session() as db:
            if "status" in data:
                updated = await db.execute(text("UPDATE tenants SET status=:status,updated_at=now() WHERE id=:id AND deleted_at IS NULL RETURNING id"), {"id": tenant_id, "status": data["status"]})
                if not updated.scalar_one_or_none():
                    return None
            if plan_code := data.get("plan_code"):
                plan_id = (await db.execute(text("SELECT id FROM plans WHERE code=:code"), {"code": plan_code})).scalar_one_or_none()
                if not plan_id:
                    return None
                await db.execute(text("INSERT INTO subscriptions(id,tenant_id,plan_id,status) VALUES(gen_random_uuid(),:tenant,:plan,'active') ON CONFLICT(tenant_id) DO UPDATE SET plan_id=excluded.plan_id,updated_at=now()"), {"tenant": tenant_id, "plan": plan_id})
            await db.execute(text("INSERT INTO events(id,tenant_id,actor_type,type,entity_type,entity_id,payload) VALUES(gen_random_uuid(),:tenant,'system','admin.tenant_updated','tenant',:tenant,CAST(:payload AS jsonb))"), {"tenant": tenant_id, "payload": json.dumps(data)})
        return next((item for item in await self.admin_list_tenants() if item["id"] == tenant_id), None)

    async def admin_metrics(self) -> dict[str, Any]:
        async with self._internal_session() as db:
            row = await db.execute(text("SELECT (SELECT count(*) FROM tenants WHERE deleted_at IS NULL)::int tenants,(SELECT count(*) FROM calls)::int calls,(SELECT COALESCE(sum(COALESCE(billable_seconds,duration_s,0))/60.0,0) FROM calls)::float minutes,(SELECT COALESCE(sum((cost->>'total')::numeric),0) FROM calls)::float cost,(SELECT count(*) FROM calls WHERE status IN ('queued','ringing','in_progress'))::int active_rooms"))
            return dict(row.mappings().one())

    async def ingest_whatsapp_message(self, data: dict[str, Any]) -> bool:
        async with self._internal_session() as db:
            integration = (await db.execute(text("SELECT * FROM integrations WHERE provider='whatsapp' AND status='active' AND config->>'phone_number_id'=:phone LIMIT 1"), {"phone": data["phone_number_id"]})).mappings().first()
            if not integration:
                return False
            tenant_id = integration["tenant_id"]
            end_user_id = (await db.execute(text("SELECT id FROM end_users WHERE tenant_id=:tenant AND phone=:phone LIMIT 1"), {"tenant": tenant_id, "phone": data["from"]})).scalar_one_or_none()
            if not end_user_id:
                end_user_id = uuid4()
                await db.execute(text("INSERT INTO end_users(id,tenant_id,phone,metadata,first_seen_at,last_seen_at) VALUES(:id,:tenant,:phone,'{}'::jsonb,now(),now())"), {"id": end_user_id, "tenant": tenant_id, "phone": data["from"]})
            call_id = (await db.execute(text("SELECT id FROM calls WHERE tenant_id=:tenant AND channel='whatsapp' AND end_user_id=:user AND started_at>=now()-interval '24 hours' AND status='in_progress' ORDER BY started_at DESC LIMIT 1"), {"tenant": tenant_id, "user": end_user_id})).scalar_one_or_none()
            if not call_id:
                call_id = uuid4()
                await db.execute(text("INSERT INTO calls(id,tenant_id,agent_id,end_user_id,channel,status,from_number,started_at,metadata) VALUES(:id,:tenant,CAST(:agent AS uuid),:user,'whatsapp','in_progress',:phone,now(),CAST(:metadata AS jsonb))"), {"id": call_id, "tenant": tenant_id, "agent": integration["config"]["agent_id"], "user": end_user_id, "phone": data["from"], "metadata": json.dumps({"phone_number_id": data["phone_number_id"]})})
            result = await db.execute(text("INSERT INTO whatsapp_messages(id,tenant_id,call_id,provider_message_id,direction,type,text,media_id,status,payload) VALUES(:id,:tenant,:call,:provider,'inbound',:type,:text,:media,'pending',CAST(:payload AS jsonb)) ON CONFLICT(provider_message_id) DO NOTHING RETURNING id"), {"id": uuid4(), "tenant": tenant_id, "call": call_id, "provider": data["provider_message_id"], "type": data["type"], "text": data.get("text"), "media": data.get("media_id"), "payload": json.dumps(data)})
            return bool(result.scalar_one_or_none())

    async def claim_whatsapp_messages(self, limit: int = 100) -> list[dict[str, Any]]:
        async with self._internal_session() as db:
            rows = await db.execute(text("WITH picked AS (SELECT id FROM whatsapp_messages WHERE status='pending' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT :limit) UPDATE whatsapp_messages m SET status='processing',updated_at=now() FROM picked WHERE m.id=picked.id RETURNING m.*"), {"limit": limit})
            messages = [dict(row) for row in rows.mappings()]
            for item in messages:
                integration = (await db.execute(text("SELECT i.config,s.ciphertext,s.kms_key_id FROM integrations i JOIN secrets s ON s.id=i.refresh_token_secret_id WHERE i.tenant_id=:tenant AND i.provider='whatsapp' AND i.status='active' LIMIT 1"), {"tenant": item["tenant_id"]})).mappings().first()
                call = (await db.execute(text("SELECT c.*,av.system_prompt,av.behavior FROM calls c LEFT JOIN agents a ON a.id=c.agent_id LEFT JOIN agent_versions av ON av.id=a.current_version_id WHERE c.id=:id"), {"id": item["call_id"]})).mappings().first()
                if integration and call:
                    item.update(dict(integration))
                    item["call"] = dict(call)
            return [item for item in messages if item.get("ciphertext")]

    async def complete_whatsapp_message(self, message_id: UUID, data: dict[str, Any]) -> None:
        async with self._internal_session() as db:
            message = (await db.execute(text("SELECT * FROM whatsapp_messages WHERE id=:id"), {"id": message_id})).mappings().first()
            if not message:
                return
            ordinal = int((await db.execute(text("SELECT COALESCE(max(ordinal),-1)+1 FROM call_turns WHERE call_id=:call"), {"call": message["call_id"]})).scalar_one())
            for offset, (role, value) in enumerate((("user", data.get("user_text")), ("agent", data.get("agent_text")))):
                if value:
                    await db.execute(text("INSERT INTO call_turns(id,tenant_id,call_id,ordinal,role,text,started_at,ended_at) VALUES(gen_random_uuid(),:tenant,:call,:ordinal,:role,:text,now(),now())"), {"tenant": message["tenant_id"], "call": message["call_id"], "ordinal": ordinal + offset, "role": role, "text": value})
            await db.execute(text("UPDATE whatsapp_messages SET status=:status,error=:error,updated_at=now() WHERE id=:id"), {"id": message_id, "status": data.get("status", "done"), "error": data.get("error")})
            if data.get("handoff"):
                await db.execute(text("UPDATE calls SET metadata=metadata || '{\"human_handoff\":true}'::jsonb,updated_at=now() WHERE id=:id"), {"id": message["call_id"]})

    async def create_simulation(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(text("INSERT INTO simulations(id,tenant_id,agent_id,persona,objective,conversation_count,status) VALUES(:id,:tenant,:agent,:persona,:objective,:count,'pending') RETURNING *"), {"id": uuid4(), "tenant": tenant_id, "agent": data["agent_id"], "persona": data["persona"], "objective": data["objective"], "count": data["conversation_count"]})
            return dict(row.mappings().one())

    async def get_simulation(self, tenant_id: UUID, simulation_id: UUID) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(text("SELECT * FROM simulations WHERE id=:id"), {"id": simulation_id})
            item = row.mappings().first()
            return dict(item) if item else None

    async def complete_simulation(self, tenant_id: UUID, simulation_id: UUID, report: dict[str, Any]) -> dict[str, Any] | None:
        async with self.tenant_session(tenant_id) as db:
            row = await db.execute(text("UPDATE simulations SET status='completed',report=CAST(:report AS jsonb),updated_at=now() WHERE id=:id RETURNING *"), {"id": simulation_id, "report": json.dumps(report)})
            item = row.mappings().first()
            return dict(item) if item else None


class MemoryRepository:
    def __init__(self, memory: MemoryStore = store) -> None:
        self.memory = memory

    async def get_tenant(self, tenant_id: UUID) -> dict[str, Any] | None:
        if tenant_id not in self.memory.tenants:
            now = datetime.now(UTC)
            self.memory.tenants[tenant_id] = {
                "id": tenant_id,
                "slug": f"tenant-{str(tenant_id)[:8]}",
                "name": "Workspace",
                "status": "trial",
                "settings": {
                    "timezone": "America/Sao_Paulo",
                    "locale": "pt-BR",
                    "recording_enabled": True,
                    "retention_days": 90,
                },
                "created_at": now,
                "updated_at": now,
            }
        return dict(self.memory.tenants[tenant_id])

    async def update_tenant(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        tenant = await self.get_tenant(tenant_id)
        if tenant is None:
            return None
        tenant.update({key: value for key, value in data.items() if key != "settings"})
        tenant["settings"] = {**tenant["settings"], **data.get("settings", {})}
        tenant["updated_at"] = datetime.now(UTC)
        self.memory.tenants[tenant_id] = tenant
        return dict(tenant)

    async def list_members(self, tenant_id: UUID) -> list[dict[str, Any]]:
        return [
            {**self.memory.users[user_id], **membership}
            for (member_tenant, user_id), membership in self.memory.memberships.items()
            if member_tenant == tenant_id
        ]

    async def create_member(self, tenant_id: UUID, email: str, role: str) -> dict[str, Any]:
        user = next(
            (item for item in self.memory.users.values() if item["email"] == email.casefold()), None
        )
        if user is None:
            user = {"id": uuid4(), "email": email.casefold(), "name": None, "avatar_url": None}
            self.memory.users[user["id"]] = user
        membership = {
            "tenant_id": tenant_id,
            "user_id": user["id"],
            "role": role,
            "created_at": datetime.now(UTC),
        }
        self.memory.memberships[(tenant_id, user["id"])] = membership
        return {**user, **membership, "id": user["id"]}

    async def update_member(
        self, tenant_id: UUID, user_id: UUID, role: str
    ) -> dict[str, Any] | None:
        membership = self.memory.memberships.get((tenant_id, user_id))
        if not membership:
            return None
        if membership["role"] == "owner" and role != "owner":
            owner_count = sum(
                item["role"] == "owner"
                for (member_tenant, _), item in self.memory.memberships.items()
                if member_tenant == tenant_id
            )
            if owner_count == 1:
                raise LastOwnerError
        membership["role"] = role
        return {**self.memory.users[user_id], **membership, "id": user_id}

    async def delete_member(self, tenant_id: UUID, user_id: UUID) -> bool:
        membership = self.memory.memberships.get((tenant_id, user_id))
        if membership and membership["role"] == "owner":
            owner_count = sum(
                item["role"] == "owner"
                for (member_tenant, _), item in self.memory.memberships.items()
                if member_tenant == tenant_id
            )
            if owner_count == 1:
                raise LastOwnerError
        return self.memory.memberships.pop((tenant_id, user_id), None) is not None

    async def list_api_keys(self, tenant_id: UUID) -> list[dict[str, Any]]:
        return [
            {key: value for key, value in item.items() if key != "hash"}
            for item in self.memory.api_keys.values()
            if item["tenant_id"] == tenant_id
        ]

    async def create_api_key(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        item = {
            "id": uuid4(),
            "tenant_id": tenant_id,
            **data,
            "last_used_at": None,
            "revoked_at": None,
            "created_at": now,
        }
        self.memory.api_keys[item["id"]] = item
        return {key: value for key, value in item.items() if key != "hash"}

    async def revoke_api_key(self, tenant_id: UUID, key_id: UUID) -> bool:
        item = self.memory.api_keys.get(key_id)
        if not item or item["tenant_id"] != tenant_id or item["revoked_at"] is not None:
            return False
        item["revoked_at"] = datetime.now(UTC)
        return True

    async def get_api_key_by_hash(
        self, tenant_id: UUID, prefix: str, hash_value: str
    ) -> dict[str, Any] | None:
        for item in self.memory.api_keys.values():
            if (
                item["tenant_id"] == tenant_id
                and item["prefix"] == prefix
                and item["hash"] == hash_value
                and item["revoked_at"] is None
            ):
                return {key: value for key, value in item.items() if key != "hash"}
        return None

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

    async def update_agent(
        self, tenant_id: UUID, agent_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
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
            [
                v
                for v in self.memory.agent_versions.values()
                if v["tenant_id"] == tenant_id and v["agent_id"] == agent_id
            ],
            key=lambda version: (version["version"], version["created_at"]),
            reverse=True,
        )

    async def get_version(
        self, tenant_id: UUID, agent_id: UUID, version_id: UUID
    ) -> dict[str, Any] | None:
        version = self.memory.agent_versions.get(version_id)
        return (
            version
            if version and version["tenant_id"] == tenant_id and version["agent_id"] == agent_id
            else None
        )

    async def update_draft(
        self, tenant_id: UUID, agent_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        agent = await self.get_agent(tenant_id, agent_id)
        if not agent:
            return None
        draft = self.memory.agent_versions[agent["draft_version_id"]]
        if draft["published_at"] is not None:
            return None
        draft.update(data)
        draft["updated_at"] = datetime.now(UTC)
        return draft

    async def rollback_agent(
        self, tenant_id: UUID, agent_id: UUID, version_id: UUID
    ) -> dict[str, Any] | None:
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
            draft = {
                **published,
                "id": new_id,
                "version": published["version"] + 1,
                "published_at": None,
                "created_at": now,
                "updated_at": now,
            }
            self.memory.agent_versions[new_id] = draft
            self.memory.agent_tools[new_id] = set(
                self.memory.agent_tools.get(published["id"], set())
            )
            agent["current_version_id"], agent["draft_version_id"], agent["status"] = (
                published["id"],
                new_id,
                "active",
            )
            agent["updated_at"] = now
        return await self.get_agent_detail(tenant_id, agent_id)

    async def upsert_end_user(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        if not any(data.get(field) for field in ("external_id", "phone", "email")):
            raise ValueError("end_user requires external_id, phone, or email")
        match = next(
            (
                item
                for item in self.memory.end_users.values()
                if item["tenant_id"] == tenant_id
                and any(
                    data.get(field) and item.get(field) == data[field]
                    for field in ("external_id", "phone", "email")
                )
            ),
            None,
        )
        now = datetime.now(UTC)
        if match:
            match.update({key: value for key, value in data.items() if value is not None})
            match["last_seen_at"] = now
            return match
        item = {
            "id": uuid4(),
            "tenant_id": tenant_id,
            **data,
            "metadata": data.get("metadata", {}),
            "first_seen_at": now,
            "last_seen_at": now,
        }
        self.memory.end_users[item["id"]] = item
        return item

    async def list_end_users(self, tenant_id: UUID, query: str | None = None) -> list[dict[str, Any]]:
        needle = (query or "").lower()
        result: list[dict[str, Any]] = []
        for item in self.memory.end_users.values():
            if item["tenant_id"] != tenant_id:
                continue
            if needle and needle not in " ".join(str(item.get(field) or "") for field in ("external_id", "phone", "email", "name")).lower():
                continue
            value = dict(item)
            value["calls_count"] = sum(call.get("end_user_id") == item["id"] for call in self.memory.calls.values())
            result.append(value)
        return sorted(result, key=lambda item: item.get("last_seen_at") or item["created_at"], reverse=True)

    async def get_end_user(self, tenant_id: UUID, end_user_id: UUID) -> dict[str, Any] | None:
        item = self.memory.end_users.get(end_user_id)
        if not item or item["tenant_id"] != tenant_id:
            return None
        result = dict(item)
        result["calls"] = [dict(call) for call in self.memory.calls.values() if call.get("end_user_id") == end_user_id][-20:]
        return result

    async def update_end_user(self, tenant_id: UUID, end_user_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        item = self.memory.end_users.get(end_user_id)
        if not item or item["tenant_id"] != tenant_id:
            return None
        item.update(data)
        item["updated_at"] = datetime.now(UTC)
        return dict(item)

    async def anonymize_end_user(self, tenant_id: UUID, end_user_id: UUID) -> bool:
        item = self.memory.end_users.get(end_user_id)
        if not item or item["tenant_id"] != tenant_id:
            return False
        for call in self.memory.calls.values():
            if call.get("end_user_id") == end_user_id:
                call.update({"end_user_id": None, "from_number": None, "to_number": None, "summary": None, "variables": {}, "metadata": {}})
                for turn in call.get("turns", []):
                    turn["text"] = "[deleted]"
        del self.memory.end_users[end_user_id]
        return True

    async def create_call(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        variables: dict[str, Any],
        metadata: dict[str, Any],
        *,
        agent_version_id: UUID | None = None,
        end_user_id: UUID | None = None,
        channel: str = "web",
        status: str = "queued",
        from_number: str | None = None,
        to_number: str | None = None,
        campaign_id: UUID | None = None,
    ) -> dict[str, Any]:
        call_id = uuid4()
        result = {
            "id": call_id,
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "agent_version_id": agent_version_id,
            "end_user_id": end_user_id,
            "channel": channel,
            "status": status,
            "from_number": from_number,
            "to_number": to_number,
            "campaign_id": campaign_id,
            "metadata": metadata,
            "variables": variables,
            "created_at": datetime.now(UTC),
        }
        self.memory.calls[call_id] = result
        return result

    async def list_calls(
        self, tenant_id: UUID, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        filters = filters or {}
        calls = [c for c in self.memory.calls.values() if c["tenant_id"] == tenant_id]

        def occurred_on(call: dict[str, Any]) -> date:
            timestamp = call.get("started_at") or call.get("created_at")
            if isinstance(timestamp, datetime):
                return timestamp.date()
            return timestamp if isinstance(timestamp, date) else date.min

        for field in ("agent_id", "channel", "status", "end_user_id", "campaign_id"):
            if filters.get(field) is not None:
                calls = [call for call in calls if call.get(field) == filters[field]]
        if filters.get("from") is not None:
            calls = [call for call in calls if occurred_on(call) >= filters["from"]]
        if filters.get("to") is not None:
            calls = [call for call in calls if occurred_on(call) <= filters["to"]]
        if filters.get("q"):
            query = filters["q"].casefold()
            calls = [
                call
                for call in calls
                if query in str(call["id"]).casefold()
                or query in (call.get("summary") or "").casefold()
                or (
                    bool(call.get("end_user_id"))
                    and (end_user := self.memory.end_users.get(call["end_user_id"])) is not None
                    and any(
                        query in str(end_user.get(field) or "").casefold()
                        for field in ("phone", "email", "name")
                    )
                )
                or any(
                    query in turn.get("text", "").casefold()
                    for turn in self.memory.call_turns.get(call["id"], [])
                )
            ]
        return calls

    async def get_call(self, tenant_id: UUID, call_id: UUID) -> dict[str, Any] | None:
        call = self.memory.calls.get(call_id)
        return call if call and call["tenant_id"] == tenant_id else None

    async def get_call_detail(self, tenant_id: UUID, call_id: UUID) -> dict[str, Any] | None:
        call = await self.get_call(tenant_id, call_id)
        if not call:
            return None
        return {
            **call,
            "turns": self.memory.call_turns.get(call_id, []),
            "tool_calls": self.memory.call_tool_calls.get(call_id, []),
            "events": self.memory.call_events.get(call_id, []),
            "recording": self.memory.call_recordings.get(call_id),
            "qa": self.memory.call_qa.get(call_id),
        }

    async def upsert_call_qa(self, tenant_id: UUID, call_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        if not await self.get_call(tenant_id, call_id):
            return None
        now = datetime.now(UTC)
        item = self.memory.call_qa.get(call_id, {"id": uuid4(), "tenant_id": tenant_id, "call_id": call_id, "created_at": now})
        item.update(data)
        item["updated_at"] = now
        self.memory.call_qa[call_id] = item
        return dict(item)

    async def update_call(
        self, tenant_id: UUID, call_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        call = await self.get_call(tenant_id, call_id)
        if not call:
            return None
        call.update(data)
        call["updated_at"] = datetime.now(UTC)
        return call

    async def expire_stale_calls(self) -> int:
        now = datetime.now(UTC)
        expired: list[UUID] = []
        for call_id, call in self.memory.calls.items():
            if call.get("status") not in {"queued", "ringing", "in_progress"}:
                continue
            reference = call.get("updated_at") or call.get("started_at") or call.get("created_at")
            if not isinstance(reference, datetime):
                continue
            age = (now - reference).total_seconds()
            limit = 2 * 60 * 60 if call.get("status") == "in_progress" else 5 * 60
            if age >= limit:
                expired.append(call_id)
        for call_id in expired:
            await self.update_internal_call(
                call_id,
                {"status": "failed", "end_reason": "runtime_timeout", "ended_at": now},
            )
        return len(expired)

    async def create_internal_call(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self.create_call(
            data["tenant_id"],
            data["agent_id"],
            data.get("variables", {}),
            data.get("metadata", {}),
            agent_version_id=data.get("agent_version_id"),
            end_user_id=data.get("end_user_id"),
            channel=data.get("channel", "web"),
            status=data.get("status", "queued"),
            from_number=data.get("from_number"),
            to_number=data.get("to_number"),
            campaign_id=data.get("campaign_id"),
        )

    async def update_internal_call(
        self, call_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        call = self.memory.calls.get(call_id)
        updated = await self.update_call(call["tenant_id"], call_id, data) if call else None
        if updated and updated.get("status") in {
            "completed",
            "no_answer",
            "busy",
            "failed",
            "cancelled",
        }:
            ended = updated.get("ended_at") or datetime.now(UTC)
            if str(updated.get("channel", "")).startswith("phone"):
                started = (
                    updated.get("answered_at")
                    or updated.get("started_at")
                    or updated.get("created_at")
                )
            else:
                started = updated.get("started_at") or updated.get("created_at")
            seconds = max(0, int((ended - started).total_seconds())) if started else 0
            self.memory.usage_records[call_id] = {
                "id": self.memory.usage_records.get(call_id, {}).get("id", uuid4()),
                "tenant_id": updated["tenant_id"],
                "call_id": call_id,
                "period": ended.date().replace(day=1),
                "billable_seconds": seconds,
                "channel": updated.get("channel", "web"),
                "cost_usd": float((updated.get("cost") or {}).get("total_usd", 0)),
            }
        if (
            updated
            and updated.get("campaign_id")
            and updated.get("status") in {"completed", "no_answer", "busy", "failed", "cancelled"}
        ):
            contact = next(
                (
                    item
                    for item in self.memory.campaign_contacts.values()
                    if item.get("last_call_id") == call_id
                ),
                None,
            )
            if contact:
                status = str(updated["status"])
                campaign = self.memory.campaigns[contact["campaign_id"]]
                next_attempt = retry_at(
                    status,
                    int(contact["attempts"]),
                    campaign["schedule"].get("retry_policy", {}),
                    now=datetime.now(UTC),
                )
                await self.update_campaign_contact_internal(
                    contact["id"],
                    {
                        "status": "retry"
                        if next_attempt
                        else ("done" if status == "completed" else status),
                        "next_attempt_at": next_attempt,
                    },
                )
                contacts = [
                    item
                    for item in self.memory.campaign_contacts.values()
                    if item["campaign_id"] == contact["campaign_id"]
                ]
                remaining = sum(
                    item["status"] in {"pending", "retry", "calling"} for item in contacts
                )
                campaign["stats"] = {
                    "total": len(contacts),
                    "done": sum(item["status"] == "done" for item in contacts),
                    "failed": sum(
                        item["status"] not in {"pending", "retry", "calling", "done"}
                        for item in contacts
                    ),
                    "remaining": remaining,
                }
                if not remaining:
                    campaign["status"] = "completed"
        return updated

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

    async def append_call_tool_call(
        self, call_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        if call_id not in self.memory.calls:
            return None
        item = {**data, "id": data.get("id") or uuid4()}
        self.memory.call_tool_calls.setdefault(call_id, []).append(item)
        return item

    async def get_call_tenant(self, call_id: UUID) -> UUID | None:
        call = self.memory.calls.get(call_id)
        return call["tenant_id"] if call else None

    async def upsert_call_recording(
        self, call_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        call = self.memory.calls.get(call_id)
        if not call:
            return None
        now = datetime.now(UTC)
        item = {
            "id": self.memory.call_recordings.get(call_id, {}).get("id", uuid4()),
            "tenant_id": call["tenant_id"],
            "call_id": call_id,
            **data,
            "updated_at": now,
        }
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

    async def update_tool(
        self, tenant_id: UUID, tool_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
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

    async def set_draft_tools(
        self, tenant_id: UUID, agent_id: UUID, tool_ids: list[UUID]
    ) -> list[dict[str, Any]] | None:
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
            version_id = (
                agent["current_version_id"]
                if version == "current"
                else agent["draft_version_id"]
                if version == "draft"
                else UUID(version)
            )
        except ValueError:
            return None
        selected = self.memory.agent_versions.get(version_id)
        if not selected or selected["agent_id"] != agent_id:
            return None
        tools = [
            self.memory.tools[tool_id]
            for tool_id in self.memory.agent_tools.get(version_id, set())
            if tool_id in self.memory.tools
        ]
        tools = [
            tool for tool in tools
            if tool.get("type") != "mcp"
            or ((tool.get("mcp") or {}).get("enabled") and (tool.get("mcp") or {}).get("approved"))
        ]
        return {
            **agent,
            **selected,
            "version_id": selected["id"],
            "tenant_settings": {},
            "tools": sorted(tools, key=lambda tool: tool["name"]),
        }

    async def list_knowledge_bases(self, tenant_id: UUID) -> list[dict[str, Any]]:
        return [kb for kb in self.memory.knowledge_bases.values() if kb["tenant_id"] == tenant_id]

    async def create_knowledge_base(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        item = {
            "id": uuid4(),
            "tenant_id": tenant_id,
            **data,
            "status": "ready",
            "created_at": now,
            "updated_at": now,
        }
        self.memory.knowledge_bases[item["id"]] = item
        return item

    async def get_knowledge_base(self, tenant_id: UUID, kb_id: UUID) -> dict[str, Any] | None:
        item = self.memory.knowledge_bases.get(kb_id)
        return item if item and item["tenant_id"] == tenant_id else None

    async def update_knowledge_base(
        self, tenant_id: UUID, kb_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        item = await self.get_knowledge_base(tenant_id, kb_id)
        if not item:
            return None
        item.update(data)
        item["updated_at"] = datetime.now(UTC)
        return item

    async def list_campaigns(self, tenant_id: UUID) -> list[dict[str, Any]]:
        return sorted(
            [item for item in self.memory.campaigns.values() if item["tenant_id"] == tenant_id],
            key=lambda item: item["created_at"],
            reverse=True,
        )

    async def create_campaign(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        item = {
            "id": uuid4(),
            "tenant_id": tenant_id,
            **data,
            "status": "draft",
            "stats": {},
            "created_at": now,
            "updated_at": now,
        }
        self.memory.campaigns[item["id"]] = item
        return item

    async def get_campaign(self, tenant_id: UUID, campaign_id: UUID) -> dict[str, Any] | None:
        item = self.memory.campaigns.get(campaign_id)
        return item if item and item["tenant_id"] == tenant_id else None

    async def update_campaign(
        self, tenant_id: UUID, campaign_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        item = await self.get_campaign(tenant_id, campaign_id)
        if not item:
            return None
        item.update(data)
        item["updated_at"] = datetime.now(UTC)
        return item

    async def add_campaign_contacts(
        self, tenant_id: UUID, campaign_id: UUID, contacts: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        now = datetime.now(UTC)
        created = []
        for contact in contacts:
            item = {
                "id": uuid4(),
                "tenant_id": tenant_id,
                "campaign_id": campaign_id,
                **contact,
                "status": "pending",
                "attempts": 0,
                "last_call_id": None,
                "next_attempt_at": None,
                "created_at": now,
                "updated_at": now,
            }
            self.memory.campaign_contacts[item["id"]] = item
            created.append(item)
        return created

    async def list_campaign_contacts(
        self, tenant_id: UUID, campaign_id: UUID, status: str | None = None
    ) -> list[dict[str, Any]]:
        return [
            item
            for item in self.memory.campaign_contacts.values()
            if item["tenant_id"] == tenant_id
            and item["campaign_id"] == campaign_id
            and (not status or item["status"] == status)
        ]

    async def list_do_not_call(self, tenant_id: UUID) -> list[dict[str, Any]]:
        return [item for item in self.memory.do_not_call.values() if item["tenant_id"] == tenant_id]

    async def add_do_not_call(
        self, tenant_id: UUID, phone: str, reason: str | None
    ) -> dict[str, Any]:
        key = (tenant_id, phone)
        item = self.memory.do_not_call.get(key)
        if item:
            item["reason"] = reason
            return item
        item = {
            "id": uuid4(),
            "tenant_id": tenant_id,
            "phone": phone,
            "reason": reason,
            "created_at": datetime.now(UTC),
        }
        self.memory.do_not_call[key] = item
        return item

    async def remove_do_not_call(self, tenant_id: UUID, phone: str) -> bool:
        return self.memory.do_not_call.pop((tenant_id, phone), None) is not None

    async def claim_campaign_contacts(self, limit: int = 100) -> list[dict[str, Any]]:
        now = datetime.now(UTC)
        claimed: list[dict[str, Any]] = []
        for contact in self.memory.campaign_contacts.values():
            campaign = self.memory.campaigns.get(contact["campaign_id"])
            if not campaign or campaign["status"] != "running":
                continue
            if contact["status"] not in {"pending", "retry"}:
                continue
            if contact.get("next_attempt_at") and contact["next_attempt_at"] > now:
                continue
            if (contact["tenant_id"], contact["phone"]) in self.memory.do_not_call:
                continue
            contact["status"] = "calling"
            contact["attempts"] += 1
            contact["updated_at"] = now
            claimed.append(
                {
                    **contact,
                    "agent_id": campaign["agent_id"],
                    "schedule": campaign["schedule"],
                    "stats": campaign["stats"],
                }
            )
            if len(claimed) >= limit:
                break
        return claimed

    async def update_campaign_contact_internal(
        self, contact_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        contact = self.memory.campaign_contacts.get(contact_id)
        if not contact:
            return None
        contact.update(data)
        contact["updated_at"] = datetime.now(UTC)
        return contact

    async def get_plan_concurrency(self, tenant_id: UUID) -> int:
        tenant = self.memory.tenants.get(tenant_id) or {}
        return int((tenant.get("plan") or {}).get("max_concurrent_calls", 50))

    async def get_billing_plan(self, tenant_id: UUID) -> dict[str, Any] | None:
        tenant = self.memory.tenants.get(tenant_id)
        if tenant is None:
            return None
        subscription = next(
            (item for item in self.memory.subscriptions.values() if item["tenant_id"] == tenant_id),
            None,
        )
        plan_code = str((subscription or {}).get("plan_code", "trial"))
        return {
            **PLANS[plan_code],
            "subscription_id": (subscription or {}).get("id"),
            "subscription_status": (subscription or {}).get("status", "trialing"),
            "tenant_status": (tenant or {}).get("status", "trial"),
            "stripe_customer_id": (tenant or {}).get("stripe_customer_id"),
            "tenant_created_at": (tenant or {}).get("created_at"),
        }

    async def get_plan_by_code(self, code: str) -> dict[str, Any] | None:
        plan = PLANS.get(code)
        return dict(plan) if plan else None

    async def get_billing_usage(self, tenant_id: UUID, period: date) -> dict[str, Any]:
        plan = await self.get_billing_plan(tenant_id) or PLANS["trial"]
        records = [
            item
            for item in self.memory.usage_records.values()
            if item["tenant_id"] == tenant_id and item["period"] == period
        ]
        minutes = sum((int(item["billable_seconds"]) + 59) // 60 for item in records)
        included = int(plan["included_minutes"])
        overage = max(0, minutes - included)
        return {
            "period": period.isoformat()[:7],
            "minutes": minutes,
            "calls": len(records),
            "cost_usd": round(sum(float(item["cost_usd"]) for item in records), 4),
            "included_minutes": included,
            "overage_minutes": overage,
            "estimated_overage_cents": overage * int(plan["overage_cents_per_min"]),
        }

    async def list_invoices(self, tenant_id: UUID) -> list[dict[str, Any]]:
        return [item for item in self.memory.invoices.values() if item["tenant_id"] == tenant_id]

    async def upsert_invoice(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        item = next(
            (
                value
                for value in self.memory.invoices.values()
                if value.get("stripe_invoice_id") == data["stripe_invoice_id"]
            ),
            None,
        )
        if item:
            item.update(data)
            return item
        item = {"id": uuid4(), "tenant_id": tenant_id, **data, "created_at": datetime.now(UTC)}
        self.memory.invoices[item["id"]] = item
        return item

    async def upsert_subscription(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        item = next(
            (
                value
                for value in self.memory.subscriptions.values()
                if value.get("stripe_subscription_id") == data.get("stripe_subscription_id")
            ),
            None,
        )
        if item:
            item.update(data)
            return item
        item = {"id": uuid4(), "tenant_id": tenant_id, **data, "created_at": datetime.now(UTC)}
        self.memory.subscriptions[item["id"]] = item
        return item

    async def update_billing_tenant(
        self, tenant_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        tenant = self.memory.tenants.setdefault(
            tenant_id, {"id": tenant_id, "status": "trial", "settings": {}}
        )
        tenant.update(data)
        return tenant

    async def billing_meter_batches(self) -> list[dict[str, Any]]:
        batches: list[dict[str, Any]] = []
        period = datetime.now(UTC).date().replace(day=1)
        for subscription in self.memory.subscriptions.values():
            if subscription.get("status") not in {"active", "trialing"}:
                continue
            tenant_id = subscription["tenant_id"]
            plan = PLANS[str(subscription.get("plan_code", "trial"))]
            records = [
                item
                for item in self.memory.usage_records.values()
                if item["tenant_id"] == tenant_id and item["period"] == period
            ]
            total = sum((int(item["billable_seconds"]) + 59) // 60 for item in records)
            reported = sum(
                (int(item["billable_seconds"]) + 59) // 60
                for item in records
                if item.get("stripe_usage_record_id")
            )
            included = int(plan["included_minutes"])
            batches.append(
                {
                    "tenant_id": tenant_id,
                    "stripe_overage_item_id": subscription.get("stripe_overage_item_id"),
                    "stripe_phone_item_id": subscription.get("stripe_phone_item_id"),
                    "record_ids": [
                        item["id"] for item in records if not item.get("stripe_usage_record_id")
                    ],
                    "overage_delta": max(0, total - included) - max(0, reported - included),
                    "phone_quantity": sum(
                        item["tenant_id"] == tenant_id and item["status"] == "active"
                        for item in self.memory.phone_numbers.values()
                    ),
                }
            )
        return batches

    async def mark_usage_reported(
        self, tenant_id: UUID, record_ids: list[UUID], stripe_id: str
    ) -> None:
        selected = set(record_ids)
        for record in self.memory.usage_records.values():
            if record["tenant_id"] == tenant_id and record["id"] in selected:
                record["stripe_usage_record_id"] = stripe_id

    async def billing_threshold_events(self) -> list[dict[str, Any]]:
        period = datetime.now(UTC).date().replace(day=1)
        events: list[dict[str, Any]] = []
        for subscription in self.memory.subscriptions.values():
            if subscription.get("status") not in {"active", "trialing"}:
                continue
            tenant_id = subscription["tenant_id"]
            included = int(PLANS[str(subscription.get("plan_code", "trial"))]["included_minutes"])
            minutes = sum(
                (int(item["billable_seconds"]) + 59) // 60
                for item in self.memory.usage_records.values()
                if item["tenant_id"] == tenant_id and item["period"] == period
            )
            for threshold in (80, 100):
                key = (tenant_id, period.isoformat(), threshold)
                if included and minutes * 100 >= included * threshold and key not in self.memory.billing_usage_alerts:
                    value = {"tenant_id": tenant_id, "period": period, "threshold": threshold, "minutes": minutes}
                    self.memory.billing_usage_alerts[key] = value
                    events.append(value)
        return events

    async def list_webhooks(self, tenant_id: UUID) -> list[dict[str, Any]]:
        return [dict(item) for item in self.memory.webhooks.values() if item["tenant_id"] == tenant_id]

    async def create_webhook(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        item = {"id": uuid4(), "tenant_id": tenant_id, **data, "created_at": now, "updated_at": now}
        self.memory.webhooks[item["id"]] = item
        return {key: value for key, value in item.items() if key != "secret_id"}

    async def update_webhook(self, tenant_id: UUID, webhook_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        item = self.memory.webhooks.get(webhook_id)
        if not item or item["tenant_id"] != tenant_id:
            return None
        item.update(data)
        item["updated_at"] = datetime.now(UTC)
        return dict(item)

    async def delete_webhook(self, tenant_id: UUID, webhook_id: UUID) -> bool:
        item = self.memory.webhooks.get(webhook_id)
        if not item or item["tenant_id"] != tenant_id:
            return False
        del self.memory.webhooks[webhook_id]
        return True

    async def list_webhook_deliveries(self, tenant_id: UUID, webhook_id: UUID) -> list[dict[str, Any]]:
        return [dict(item) for item in self.memory.webhook_deliveries.values() if item["tenant_id"] == tenant_id and item["webhook_id"] == webhook_id]

    async def queue_webhook_event(self, tenant_id: UUID, event: str, data: dict[str, Any]) -> int:
        count = 0
        for endpoint in self.memory.webhooks.values():
            if endpoint["tenant_id"] != tenant_id or not endpoint.get("enabled", True) or event not in endpoint["events"] and "*" not in endpoint["events"]:
                continue
            now = datetime.now(UTC)
            item = {"id": uuid4(), "tenant_id": tenant_id, "webhook_id": endpoint["id"], "event": event, "payload": {"id": f"evt_{uuid4().hex}", "type": event, "created_at": now.isoformat(), "tenant_id": str(tenant_id), "data": data}, "status": "pending", "attempts": 0, "last_status_code": None, "next_retry_at": now, "created_at": now, "updated_at": now}
            self.memory.webhook_deliveries[item["id"]] = item
            count += 1
        return count

    async def claim_webhook_deliveries(self, limit: int = 100) -> list[dict[str, Any]]:
        now = datetime.now(UTC)
        result: list[dict[str, Any]] = []
        for item in self.memory.webhook_deliveries.values():
            if len(result) >= limit or item["status"] not in {"pending", "retrying"} or item["next_retry_at"] > now:
                continue
            endpoint = self.memory.webhooks.get(item["webhook_id"])
            secret_id = endpoint.get("secret_id") if endpoint else None
            secret = self.memory.secrets.get(secret_id) if isinstance(secret_id, UUID) else None
            if not endpoint or not secret or not endpoint.get("enabled", True):
                continue
            item["status"] = "processing"
            item["attempts"] += 1
            result.append({**item, "url": endpoint["url"], "ciphertext": secret["ciphertext"], "kms_key_id": secret["kms_key_id"]})
        return result

    async def update_webhook_delivery(self, delivery_id: UUID, data: dict[str, Any]) -> None:
        if item := self.memory.webhook_deliveries.get(delivery_id):
            item.update(data)
            item["updated_at"] = datetime.now(UTC)

    async def retry_webhook_delivery(self, tenant_id: UUID, webhook_id: UUID, delivery_id: UUID) -> bool:
        item = self.memory.webhook_deliveries.get(delivery_id)
        if not item or item["tenant_id"] != tenant_id or item["webhook_id"] != webhook_id:
            return False
        item.update({"status": "pending", "attempts": 0, "next_retry_at": datetime.now(UTC)})
        return True

    async def create_export(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        item = {"id": uuid4(), "tenant_id": tenant_id, **data, "status": "pending", "s3_key": None, "expires_at": now + timedelta(days=7), "created_at": now, "updated_at": now}
        self.memory.exports[item["id"]] = item
        return dict(item)

    async def get_export(self, tenant_id: UUID, export_id: UUID) -> dict[str, Any] | None:
        item = self.memory.exports.get(export_id)
        return dict(item) if item and item["tenant_id"] == tenant_id else None

    async def claim_exports(self, limit: int = 20) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for item in self.memory.exports.values():
            if len(result) >= limit or item["status"] != "pending":
                continue
            item["status"] = "processing"
            rows = (
                [dict(call) for call in self.memory.calls.values() if call["tenant_id"] == item["tenant_id"]]
                if item["type"] == "calls"
                else [dict(end_user) for end_user in self.memory.end_users.values() if end_user["tenant_id"] == item["tenant_id"] and (not item["filters"].get("id") or str(end_user["id"]) == str(item["filters"]["id"]))]
            )
            result.append({**item, "rows": rows})
        return result

    async def complete_export(self, export_id: UUID, s3_key: str | None, error: bool = False) -> None:
        if item := self.memory.exports.get(export_id):
            item.update({"status": "failed" if error else "ready", "s3_key": s3_key, "updated_at": datetime.now(UTC)})

    async def purge_retention(self) -> dict[str, Any]:
        now = datetime.now(UTC)
        recording_keys: list[str] = []
        for call_id, recording in list(self.memory.call_recordings.items()):
            if recording.get("expires_at") and recording["expires_at"] < now:
                recording_keys.append(str(recording["s3_key"]))
                del self.memory.call_recordings[call_id]
        anonymized = 0
        for call_id, turns in self.memory.call_turns.items():
            call = self.memory.calls.get(call_id)
            tenant_id = call.get("tenant_id") if call else None
            tenant = self.memory.tenants.get(tenant_id) if isinstance(tenant_id, UUID) else None
            settings = dict((tenant or {}).get("settings") or {})
            cutoff = now - timedelta(days=int(settings.get("retention_days", 90)))
            if settings.get("anonymize_transcripts") and call and call.get("started_at") and call["started_at"] < cutoff:
                for turn in turns:
                    if turn.get("text") != "[retained-anonymized]":
                        turn["text"] = "[retained-anonymized]"
                        anonymized += 1
        documents = [doc_id for doc_id, doc in self.memory.documents.items() if doc.get("deleted_at") and doc["deleted_at"] < now - timedelta(days=30)]
        document_keys = [str(self.memory.documents[doc_id]["s3_key"]) for doc_id in documents if self.memory.documents[doc_id].get("s3_key")]
        for doc_id in documents:
            del self.memory.documents[doc_id]
            self.memory.chunks.pop(doc_id, None)
        return {"recording_keys": recording_keys, "document_keys": document_keys, "turns_anonymized": anonymized, "documents_deleted": len(documents)}

    async def analytics_overview(self, tenant_id: UUID, start: date, end: date, agent_id: UUID | None = None) -> dict[str, Any]:
        calls = [call for call in self.memory.calls.values() if call["tenant_id"] == tenant_id and start <= (call.get("started_at") or call["created_at"]).date() <= end and (agent_id is None or call["agent_id"] == agent_id)]
        count = len(calls)
        daily: dict[str, dict[str, Any]] = {}
        for call in calls:
            day = (call.get("started_at") or call["created_at"]).date().isoformat()
            point = daily.setdefault(day, {"date": day, "calls": 0, "minutes": 0.0})
            point["calls"] += 1
            point["minutes"] += float(call.get("billable_seconds") or call.get("duration_s") or 0) / 60
        qa_scores = [float(self.memory.call_qa[call["id"]]["score"]) for call in calls if call["id"] in self.memory.call_qa]
        return {
            "calls": count,
            "minutes": sum(float(call.get("billable_seconds") or call.get("duration_s") or 0) for call in calls) / 60,
            "avg_duration": sum(float(call.get("duration_s") or 0) for call in calls) / count if count else 0,
            "resolution_rate": sum(bool((call.get("outcome") or {}).get("resolved")) for call in calls) / count if count else 0,
            "transfer_rate": sum(call.get("end_reason") == "transferred" for call in calls) / count if count else 0,
            "abandon_rate": sum(call.get("status") in {"no_answer", "busy", "cancelled"} for call in calls) / count if count else 0,
            "csat": sum(qa_scores) / len(qa_scores) / 20 if qa_scores else 0,
            "latency_p50": sum(float((call.get("latency") or {}).get("ttfb_p50_ms", 0)) for call in calls) / count if count else 0,
            "latency_p95": max((float((call.get("latency") or {}).get("ttfb_p95_ms", 0)) for call in calls), default=0),
            "cost": sum(float((call.get("cost") or {}).get("total", 0)) for call in calls),
            "series": [daily[key] for key in sorted(daily)],
        }

    async def analytics_tools(self, tenant_id: UUID, start: date, end: date) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for call_id, tools in self.memory.call_tool_calls.items():
            call = self.memory.calls.get(call_id)
            if not call or call["tenant_id"] != tenant_id or not start <= (call.get("started_at") or call["created_at"]).date() <= end:
                continue
            for tool in tools:
                item = grouped.setdefault(str(tool["name"]), {"name": tool["name"], "calls": 0, "errors": 0, "total_duration_ms": 0})
                item["calls"] += 1
                item["errors"] += tool.get("status") != "ok"
                item["total_duration_ms"] += int(tool.get("duration_ms") or 0)
        return [{**item, "avg_duration_ms": item.pop("total_duration_ms") / item["calls"]} for item in grouped.values()]

    async def admin_list_tenants(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for tenant in self.memory.tenants.values():
            subscription = next((item for item in self.memory.subscriptions.values() if item["tenant_id"] == tenant["id"]), None)
            result.append({**tenant, "plan_code": (subscription or {}).get("plan_code", "trial"), "subscription_status": (subscription or {}).get("status", "trialing"), "agents_count": sum(item["tenant_id"] == tenant["id"] for item in self.memory.agents.values()), "calls_count": sum(item["tenant_id"] == tenant["id"] for item in self.memory.calls.values())})
        return result

    async def admin_update_tenant(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        tenant = self.memory.tenants.get(tenant_id)
        if not tenant:
            return None
        if "status" in data:
            tenant["status"] = data["status"]
        if plan_code := data.get("plan_code"):
            subscription = next((item for item in self.memory.subscriptions.values() if item["tenant_id"] == tenant_id), None)
            if subscription:
                subscription["plan_code"] = plan_code
            else:
                item = {"id": uuid4(), "tenant_id": tenant_id, "plan_code": plan_code, "status": "active", "created_at": datetime.now(UTC)}
                self.memory.subscriptions[item["id"]] = item
        return next((item for item in await self.admin_list_tenants() if item["id"] == tenant_id), None)

    async def admin_metrics(self) -> dict[str, Any]:
        return {"tenants": len(self.memory.tenants), "calls": len(self.memory.calls), "minutes": sum(float(item.get("billable_seconds") or item.get("duration_s") or 0) for item in self.memory.calls.values()) / 60, "cost": sum(float((item.get("cost") or {}).get("total", 0)) for item in self.memory.calls.values()), "active_rooms": sum(item.get("status") in {"queued", "ringing", "in_progress"} for item in self.memory.calls.values())}

    async def ingest_whatsapp_message(self, data: dict[str, Any]) -> bool:
        if any(item["provider_message_id"] == data["provider_message_id"] for item in self.memory.whatsapp_messages.values()):
            return False
        integration = next((item for item in self.memory.integrations.values() if item["provider"] == "whatsapp" and item.get("status") == "active" and (item.get("config") or {}).get("phone_number_id") == data["phone_number_id"]), None)
        if not integration:
            return False
        tenant_id = integration["tenant_id"]
        end_user = await self.upsert_end_user(tenant_id, {"phone": data["from"]})
        call = next((item for item in self.memory.calls.values() if item["tenant_id"] == tenant_id and item["channel"] == "whatsapp" and item.get("end_user_id") == end_user["id"] and item["status"] == "in_progress" and item["created_at"] >= datetime.now(UTC) - timedelta(hours=24)), None)
        if not call:
            call = await self.create_call(tenant_id, UUID(str(integration["config"]["agent_id"])), {}, {"phone_number_id": data["phone_number_id"]}, end_user_id=end_user["id"], channel="whatsapp", status="in_progress", from_number=data["from"])
        now = datetime.now(UTC)
        item = {"id": uuid4(), "tenant_id": tenant_id, "call_id": call["id"], **data, "direction": "inbound", "status": "pending", "created_at": now, "updated_at": now}
        self.memory.whatsapp_messages[item["id"]] = item
        return True

    async def claim_whatsapp_messages(self, limit: int = 100) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for item in self.memory.whatsapp_messages.values():
            if len(result) >= limit or item["status"] != "pending":
                continue
            integration = next((value for value in self.memory.integrations.values() if value["tenant_id"] == item["tenant_id"] and value["provider"] == "whatsapp"), None)
            secret_id = integration.get("refresh_token_secret_id") if integration else None
            secret = self.memory.secrets.get(secret_id) if isinstance(secret_id, UUID) else None
            call = self.memory.calls.get(item["call_id"])
            if integration and secret and call:
                item["status"] = "processing"
                result.append({**item, "config": integration["config"], "ciphertext": secret["ciphertext"], "kms_key_id": secret["kms_key_id"], "call": call})
        return result

    async def complete_whatsapp_message(self, message_id: UUID, data: dict[str, Any]) -> None:
        item = self.memory.whatsapp_messages.get(message_id)
        if not item:
            return
        turns = self.memory.call_turns.setdefault(item["call_id"], [])
        for role, text_value in (("user", data.get("user_text")), ("agent", data.get("agent_text"))):
            if text_value:
                turns.append({"id": uuid4(), "tenant_id": item["tenant_id"], "call_id": item["call_id"], "ordinal": len(turns), "role": role, "text": text_value})
        item.update({"status": data.get("status", "done"), "error": data.get("error")})
        if data.get("handoff"):
            self.memory.calls[item["call_id"]]["metadata"]["human_handoff"] = True

    async def create_simulation(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        item = {"id": uuid4(), "tenant_id": tenant_id, **data, "status": "pending", "report": {}, "created_at": now, "updated_at": now}
        self.memory.simulations[item["id"]] = item
        return dict(item)

    async def get_simulation(self, tenant_id: UUID, simulation_id: UUID) -> dict[str, Any] | None:
        item = self.memory.simulations.get(simulation_id)
        return dict(item) if item and item["tenant_id"] == tenant_id else None

    async def complete_simulation(self, tenant_id: UUID, simulation_id: UUID, report: dict[str, Any]) -> dict[str, Any] | None:
        item = self.memory.simulations.get(simulation_id)
        if not item or item["tenant_id"] != tenant_id:
            return None
        item.update({"status": "completed", "report": report, "updated_at": datetime.now(UTC)})
        return dict(item)

    async def delete_knowledge_base(self, tenant_id: UUID, kb_id: UUID) -> bool:
        if not await self.get_knowledge_base(tenant_id, kb_id):
            return False
        self.memory.knowledge_bases.pop(kb_id)
        for document_id in [
            doc_id
            for doc_id, doc in self.memory.documents.items()
            if doc["knowledge_base_id"] == kb_id
        ]:
            self.memory.documents.pop(document_id)
            self.memory.chunks.pop(document_id, None)
        return True

    async def list_documents(self, tenant_id: UUID, kb_id: UUID) -> list[dict[str, Any]]:
        return [
            doc
            for doc in self.memory.documents.values()
            if doc["tenant_id"] == tenant_id
            and doc["knowledge_base_id"] == kb_id
            and not doc.get("deleted_at")
        ]

    async def create_document(
        self, tenant_id: UUID, kb_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        if not await self.get_knowledge_base(tenant_id, kb_id):
            return None
        now = datetime.now(UTC)
        item = {
            "id": uuid4(),
            "tenant_id": tenant_id,
            "knowledge_base_id": kb_id,
            **data,
            "status": "pending",
            "chunk_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        self.memory.documents[item["id"]] = item
        return item

    async def delete_document(self, tenant_id: UUID, kb_id: UUID, document_id: UUID) -> bool:
        item = self.memory.documents.get(document_id)
        if (
            not item
            or item["tenant_id"] != tenant_id
            or item["knowledge_base_id"] != kb_id
            or item.get("deleted_at")
        ):
            return False
        item["deleted_at"] = datetime.now(UTC)
        self.memory.chunks.pop(document_id, None)
        return True

    async def complete_document(
        self, tenant_id: UUID, document_id: UUID, chunks: list[dict[str, Any]]
    ) -> None:
        document = self.memory.documents[document_id]
        if document["tenant_id"] != tenant_id:
            return
        self.memory.chunks[document_id] = [
            {
                **chunk,
                "id": uuid4(),
                "document_id": document_id,
                "knowledge_base_id": document["knowledge_base_id"],
                "ordinal": ordinal,
            }
            for ordinal, chunk in enumerate(chunks)
        ]
        document.update(
            {
                "status": "ready",
                "error": None,
                "chunk_count": len(chunks),
                "updated_at": datetime.now(UTC),
            }
        )

    async def fail_document(self, tenant_id: UUID, document_id: UUID, error: str) -> None:
        document = self.memory.documents.get(document_id)
        if document and document["tenant_id"] == tenant_id:
            document.update(
                {"status": "error", "error": error[:1000], "updated_at": datetime.now(UTC)}
            )

    async def query_chunks(
        self, tenant_id: UUID, kb_id: UUID, embedding: list[float], top_k: int, min_score: float
    ) -> list[dict[str, Any]]:
        from .knowledge import cosine_similarity

        candidates = [
            {**chunk, "score": cosine_similarity(embedding, chunk["embedding"])}
            for document_id, chunks in self.memory.chunks.items()
            if self.memory.documents[document_id]["tenant_id"] == tenant_id
            and self.memory.documents[document_id]["knowledge_base_id"] == kb_id
            for chunk in chunks
        ]
        return sorted(
            [chunk for chunk in candidates if chunk["score"] >= min_score],
            key=lambda chunk: chunk["score"],
            reverse=True,
        )[:top_k]

    async def get_knowledge_base_tenant(self, kb_id: UUID) -> UUID | None:
        item = self.memory.knowledge_bases.get(kb_id)
        return item["tenant_id"] if item else None

    async def create_secret(
        self, tenant_id: UUID, name: str, ciphertext: bytes, key_id: str
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        secret_id = uuid4()
        item = {
            "id": secret_id,
            "tenant_id": tenant_id,
            "name": name,
            "ciphertext": ciphertext,
            "kms_key_id": key_id,
            "created_at": now,
            "rotated_at": None,
        }
        self.memory.secrets[secret_id] = item
        return {key: value for key, value in item.items() if key != "ciphertext"}

    async def list_secrets(self, tenant_id: UUID) -> list[dict[str, Any]]:
        return [
            {key: value for key, value in item.items() if key != "ciphertext"}
            for item in self.memory.secrets.values()
            if item["tenant_id"] == tenant_id
        ]

    async def get_secret(self, tenant_id: UUID, secret_id: UUID) -> dict[str, Any] | None:
        item = self.memory.secrets.get(secret_id)
        return item if item and item["tenant_id"] == tenant_id else None

    async def delete_secret(self, tenant_id: UUID, secret_id: UUID) -> bool:
        if not await self.get_secret(tenant_id, secret_id):
            return False
        self.memory.secrets.pop(secret_id)
        return True

    async def get_integration(self, tenant_id: UUID, provider: str) -> dict[str, Any] | None:
        return next(
            (
                item
                for item in self.memory.integrations.values()
                if item["tenant_id"] == tenant_id and item["provider"] == provider
            ),
            None,
        )

    async def upsert_integration(
        self, tenant_id: UUID, provider: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        item = await self.get_integration(tenant_id, provider)
        now = datetime.now(UTC)
        if item:
            item.update(data)
            item["updated_at"] = now
            return item
        item = {
            "id": uuid4(),
            "tenant_id": tenant_id,
            "provider": provider,
            **data,
            "created_at": now,
            "updated_at": now,
        }
        self.memory.integrations[item["id"]] = item
        return item

    async def list_phone_numbers(self, tenant_id: UUID) -> list[dict[str, Any]]:
        return sorted(
            [item for item in self.memory.phone_numbers.values() if item["tenant_id"] == tenant_id],
            key=lambda item: item["created_at"],
            reverse=True,
        )

    async def get_phone_number(self, tenant_id: UUID, number_id: UUID) -> dict[str, Any] | None:
        item = self.memory.phone_numbers.get(number_id)
        return item if item and item["tenant_id"] == tenant_id else None

    async def create_phone_number(self, tenant_id: UUID, data: dict[str, Any]) -> dict[str, Any]:
        if any(
            item["e164"] == data["e164"] and item["status"] == "active"
            for item in self.memory.phone_numbers.values()
        ):
            raise ValueError("phone number already exists")
        now = datetime.now(UTC)
        item = {
            "id": uuid4(),
            "tenant_id": tenant_id,
            **data,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        self.memory.phone_numbers[item["id"]] = item
        return item

    async def update_phone_number(
        self, tenant_id: UUID, number_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        item = await self.get_phone_number(tenant_id, number_id)
        if not item:
            return None
        item.update(data)
        item["updated_at"] = datetime.now(UTC)
        return item


postgres_repository = PostgresRepository()


async def get_repository() -> Repository:
    return postgres_repository
