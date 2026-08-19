from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import text
from voiceos_api.db import SessionFactory
from voiceos_api.repository import PostgresRepository

TENANT = UUID("00000000-0000-0000-0000-000000000001")
USER = UUID("00000000-0000-0000-0000-000000000002")


@pytest.mark.asyncio
async def test_postgres_agent_and_call_lifecycle() -> None:
    repo = PostgresRepository()
    agent = await repo.create_agent(TENANT, "Repository coverage", str(USER))
    agent_id = agent["id"]
    call_ids: list[UUID] = []
    tool_id: UUID | None = None
    try:
        assert await repo.get_agent(TENANT, agent_id)
        assert await repo.get_agent_detail(TENANT, agent_id)
        assert (await repo.update_agent(TENANT, agent_id, {"name": "Repository covered"}))["name"] == "Repository covered"  # type: ignore[index]
        assert await repo.update_agent(TENANT, agent_id, {})
        assert await repo.update_agent(TENANT, UUID(int=0), {"name": "missing"}) is None

        draft = await repo.update_draft(TENANT, agent_id, {"system_prompt": "Versão um", "rag": {"enabled": True}})
        assert draft and draft["system_prompt"] == "Versão um"
        first = await repo.publish_agent(TENANT, agent_id)
        assert first
        first_version = first["current_version_id"]
        assert len(await repo.list_versions(TENANT, agent_id)) == 2
        assert await repo.get_version(TENANT, agent_id, first_version)
        assert await repo.get_version(TENANT, agent_id, UUID(int=0)) is None
        assert await repo.update_draft(TENANT, agent_id, {"system_prompt": "Versão dois"})
        assert await repo.publish_agent(TENANT, agent_id)
        rolled_back = await repo.rollback_agent(TENANT, agent_id, first_version)
        assert rolled_back and rolled_back["current_version_id"] == first_version
        assert await repo.rollback_agent(TENANT, agent_id, UUID(int=0)) is None
        runtime = await repo.get_runtime(agent_id)
        assert runtime and runtime["system_prompt"] == "Versão um"

        tool = await repo.create_tool(
            TENANT,
            {"name": f"repo_tool_{str(agent_id)[:8]}", "description": "Teste", "type": "webhook", "native_kind": None, "parameters_schema": {"type": "object"}, "webhook": None, "speak_before": None, "async": False},
        )
        tool_id = tool["id"]

        call = await repo.create_call(TENANT, agent_id, {"name": "Mario"}, {"source": "pytest"})
        call_id = call["id"]
        call_ids.append(call_id)
        assert await repo.get_call(TENANT, call_id)
        assert any(item["id"] == call_id for item in await repo.list_calls(TENANT))
        assert await repo.update_call(TENANT, call_id, {"status": "in_progress", "latency": {"ttfb_p50_ms": 700}})
        assert await repo.update_call(TENANT, call_id, {})

        assert await repo.append_call_events(call_id, [{"type": "call.answered", "payload": {}, "at": datetime.now(UTC)}]) == 1
        assert await repo.append_call_turns(call_id, [{"id": None, "ordinal": 0, "role": "user", "text": "Olá", "started_at": None, "ended_at": None, "interrupted": False, "ttfb_ms": None, "stt_confidence": 0.98, "audio_offset_ms": 0}]) == 1
        tool_call = await repo.append_call_tool_call(call_id, {"id": None, "turn_id": None, "tool_id": tool_id, "name": tool["name"], "arguments": {"id": 42}, "result": {"ok": True}, "status": "ok", "duration_ms": 20, "started_at": datetime.now(UTC)})
        assert tool_call
        detail = await repo.get_call_detail(TENANT, call_id)
        assert detail and len(detail["events"]) == len(detail["turns"]) == len(detail["tool_calls"]) == 1

        internal_call = await repo.create_internal_call({"tenant_id": TENANT, "agent_id": agent_id, "agent_version_id": first_version, "channel": "web", "livekit_room": "room_test", "variables": {}, "metadata": {}})
        call_ids.append(internal_call["id"])
        assert await repo.update_internal_call(internal_call["id"], {"status": "completed", "ended_at": datetime.now(UTC)})
        assert await repo.update_internal_call(UUID(int=0), {"status": "failed"}) is None
        assert await repo.append_call_events(UUID(int=0), [{"type": "error", "payload": {}, "at": datetime.now(UTC)}]) == 0
        assert await repo.append_call_turns(UUID(int=0), []) == 0
        assert await repo.append_call_tool_call(UUID(int=0), {"arguments": {}}) is None
        assert await repo.get_call_detail(TENANT, UUID(int=0)) is None
        assert await repo.delete_agent(TENANT, agent_id)
        assert not await repo.delete_agent(TENANT, agent_id)
    finally:
        async with SessionFactory() as db, db.begin():
            await db.execute(text("SET LOCAL row_security = off"))
            for call_id in call_ids:
                await db.execute(text("DELETE FROM call_events WHERE call_id=:id"), {"id": call_id})
                await db.execute(text("DELETE FROM call_tool_calls WHERE call_id=:id"), {"id": call_id})
                await db.execute(text("DELETE FROM call_turns WHERE call_id=:id"), {"id": call_id})
                await db.execute(text("DELETE FROM calls WHERE id=:id"), {"id": call_id})
            await db.execute(text("DELETE FROM agent_versions WHERE agent_id=:id"), {"id": agent_id})
            await db.execute(text("DELETE FROM agents WHERE id=:id"), {"id": agent_id})
            if tool_id:
                await db.execute(text("DELETE FROM tools WHERE id=:id"), {"id": tool_id})
