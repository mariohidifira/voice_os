from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from voiceos_api.db import SessionFactory
from voiceos_api.repository import LastOwnerError, PostgresRepository

TENANT = UUID("00000000-0000-0000-0000-000000000001")
USER = UUID("00000000-0000-0000-0000-000000000002")


@pytest.mark.asyncio(loop_scope="module")
async def test_postgres_members_and_api_keys_lifecycle() -> None:
    repo = PostgresRepository()
    marker = uuid4().hex
    email = f"member-{marker}@example.com"
    member = await repo.create_member(TENANT, email, "developer")
    key = await repo.create_api_key(
        TENANT,
        {
            "name": f"key-{marker}",
            "prefix": "vos_sk_test",
            "hash": marker,
            "scope": "secret",
            "allowed_origins": [],
        },
    )
    try:
        assert any(item["id"] == member["id"] for item in await repo.list_members(TENANT))
        updated = await repo.update_member(TENANT, member["id"], "operator")
        assert updated and updated["role"] == "operator"
        listed_keys = await repo.list_api_keys(TENANT)
        assert any(item["id"] == key["id"] for item in listed_keys)
        assert all("hash" not in item for item in listed_keys)
        assert await repo.revoke_api_key(TENANT, key["id"])
        assert not await repo.revoke_api_key(TENANT, key["id"])
        assert await repo.delete_member(TENANT, member["id"])
        assert not await repo.delete_member(TENANT, member["id"])
    finally:
        async with SessionFactory() as db, db.begin():
            await db.execute(text("SET LOCAL row_security = off"))
            await db.execute(text("DELETE FROM api_keys WHERE id=:id"), {"id": key["id"]})
            await db.execute(
                text("DELETE FROM memberships WHERE user_id=:id"), {"id": member["id"]}
            )
            await db.execute(text("DELETE FROM users WHERE id=:id"), {"id": member["id"]})


@pytest.mark.asyncio(loop_scope="module")
async def test_postgres_phase3_webhooks_exports_and_lgpd() -> None:
    repo = PostgresRepository()
    marker = uuid4().hex
    secret = await repo.create_secret(TENANT, f"webhook-{marker}", b"encrypted", "test-key")
    webhook = await repo.create_webhook(
        TENANT,
        {"url": "https://example.test/hook", "events": ["call.ended"], "secret_id": secret["id"], "enabled": True},
    )
    end_user = await repo.upsert_end_user(TENANT, {"external_id": f"lgpd-{marker}", "email": f"{marker}@example.com"})
    export = await repo.create_export(TENANT, {"type": "end_user", "filters": {"id": str(end_user["id"])}})
    try:
        assert len(await repo.list_end_users(TENANT, marker)) == 1
        assert (await repo.update_end_user(TENANT, end_user["id"], {"name": "Updated"}))["name"] == "Updated"  # type: ignore[index]
        assert await repo.queue_webhook_event(TENANT, "call.started", {}) == 0
        assert await repo.queue_webhook_event(TENANT, "call.ended", {"call": {"id": marker}}) == 1
        claimed = await repo.claim_webhook_deliveries()
        delivery = next(item for item in claimed if item["webhook_id"] == webhook["id"])
        assert delivery["ciphertext"] == b"encrypted"
        await repo.update_webhook_delivery(delivery["id"], {"status": "failed", "last_status_code": 503, "next_retry_at": None})
        assert await repo.retry_webhook_delivery(TENANT, webhook["id"], delivery["id"])
        assert (await repo.get_export(TENANT, export["id"]))["status"] == "pending"  # type: ignore[index]
        assert await repo.anonymize_end_user(TENANT, end_user["id"])
        assert await repo.get_end_user(TENANT, end_user["id"]) is None
    finally:
        async with SessionFactory() as db, db.begin():
            await db.execute(text("SET LOCAL row_security = off"))
            await db.execute(text("DELETE FROM webhook_deliveries WHERE webhook_id=:id"), {"id": webhook["id"]})
            await db.execute(text("DELETE FROM webhooks_out WHERE id=:id"), {"id": webhook["id"]})
            await db.execute(text("DELETE FROM exports WHERE id=:id"), {"id": export["id"]})
            await db.execute(text("DELETE FROM end_users WHERE id=:id"), {"id": end_user["id"]})
            await db.execute(text("DELETE FROM secrets WHERE id=:id"), {"id": secret["id"]})


@pytest.mark.asyncio(loop_scope="module")
async def test_postgres_serializes_last_owner_protection() -> None:
    repo = PostgresRepository()
    temporary_owner_id: UUID | None = None
    try:
        temporary_owner = await repo.create_member(
            TENANT, f"owner-guard-{uuid4().hex}@example.com", "owner"
        )
        temporary_owner_id = temporary_owner["id"]
        assert await repo.update_member(TENANT, USER, "admin")
        with pytest.raises(LastOwnerError):
            await repo.update_member(TENANT, temporary_owner_id, "admin")
        with pytest.raises(LastOwnerError):
            await repo.delete_member(TENANT, temporary_owner_id)
    finally:
        await repo.update_member(TENANT, USER, "owner")
        if temporary_owner_id:
            await repo.delete_member(TENANT, temporary_owner_id)
            async with SessionFactory() as db, db.begin():
                await db.execute(text("SET LOCAL row_security = off"))
                await db.execute(text("DELETE FROM users WHERE id=:id"), {"id": temporary_owner_id})


@pytest.mark.asyncio(loop_scope="module")
async def test_postgres_phone_numbers_are_tenant_scoped_and_persist_assignment() -> None:
    repo = PostgresRepository()
    agent = await repo.create_agent(TENANT, "Phone repository", str(USER))
    number: dict[str, Any] | None = None
    try:
        number = await repo.create_phone_number(
            TENANT,
            {
                "agent_id": None,
                "e164": f"+5511{uuid4().int % 10_000_000_000:010d}",
                "provider": "twilio",
                "provider_sid": f"PN{uuid4().hex}",
                "capabilities": {"voice": True, "sms": True},
                "livekit_dispatch_rule_id": None,
            },
        )
        updated = await repo.update_phone_number(
            TENANT,
            number["id"],
            {"agent_id": agent["id"], "livekit_dispatch_rule_id": "SDR_test"},
        )
        assert updated and updated["agent_id"] == agent["id"]
        assert updated["capabilities"] == {"voice": True, "sms": True}
        assert await repo.get_phone_number(uuid4(), number["id"]) is None
        listed = await repo.list_phone_numbers(TENANT)
        assert any(item["id"] == number["id"] for item in listed)
        released = await repo.update_phone_number(
            TENANT,
            number["id"],
            {"status": "released", "agent_id": None, "livekit_dispatch_rule_id": None},
        )
        assert released and released["status"] == "released"
    finally:
        async with SessionFactory() as db, db.begin():
            await db.execute(text("SET LOCAL row_security = off"))
            if number:
                await db.execute(
                    text("DELETE FROM phone_numbers WHERE id=:id"), {"id": number["id"]}
                )
            await db.execute(
                text("DELETE FROM agent_versions WHERE agent_id=:id"), {"id": agent["id"]}
            )
            await db.execute(text("DELETE FROM agents WHERE id=:id"), {"id": agent["id"]})


@pytest.mark.asyncio(loop_scope="module")
async def test_postgres_campaign_claim_and_result_reconciliation() -> None:
    repo = PostgresRepository()
    agent = await repo.create_agent(TENANT, "Campaign repository", str(USER))
    campaign: dict[str, Any] | None = None
    contact_id: UUID | None = None
    call_id: UUID | None = None
    try:
        published = await repo.publish_agent(TENANT, agent["id"])
        assert published
        campaign = await repo.create_campaign(
            TENANT,
            {
                "agent_id": agent["id"],
                "name": f"Campaign {uuid4().hex[:8]}",
                "schedule": {
                    "timezone": "UTC",
                    "days": list(range(7)),
                    "window": {"start": "08:00", "end": "20:00"},
                    "retry_policy": {"max_attempts": 2, "delays_s": [60]},
                },
            },
        )
        await repo.update_campaign(TENANT, campaign["id"], {"status": "running"})
        contact = (
            await repo.add_campaign_contacts(
                TENANT, campaign["id"], [{"phone": "+551199990001", "variables": {}}]
            )
        )[0]
        contact_id = contact["id"]
        claimed = await repo.claim_campaign_contacts(10)
        claimed_contact = next(item for item in claimed if item["id"] == contact_id)
        assert claimed_contact["status"] == "calling"
        call = await repo.create_call(
            TENANT,
            agent["id"],
            {},
            {},
            agent_version_id=published["current_version_id"],
            channel="phone_outbound",
            campaign_id=campaign["id"],
            to_number=contact["phone"],
        )
        call_id = call["id"]
        await repo.update_campaign_contact_internal(contact_id, {"last_call_id": call_id})
        await repo.update_internal_call(call_id, {"status": "completed"})
        reconciled = (await repo.list_campaign_contacts(TENANT, campaign["id"]))[0]
        assert reconciled["status"] == "done"
        finished = await repo.get_campaign(TENANT, campaign["id"])
        assert finished and finished["status"] == "completed"
        assert finished["stats"]["done"] == 1
    finally:
        async with SessionFactory() as db, db.begin():
            await db.execute(text("SET LOCAL row_security = off"))
            if call_id:
                await db.execute(text("DELETE FROM calls WHERE id=:id"), {"id": call_id})
            if contact_id:
                await db.execute(
                    text("DELETE FROM campaign_contacts WHERE id=:id"), {"id": contact_id}
                )
            if campaign:
                await db.execute(text("DELETE FROM campaigns WHERE id=:id"), {"id": campaign["id"]})
            await db.execute(
                text("DELETE FROM agent_versions WHERE agent_id=:id"), {"id": agent["id"]}
            )
            await db.execute(text("DELETE FROM agents WHERE id=:id"), {"id": agent["id"]})


@pytest.mark.asyncio(loop_scope="module")
async def test_postgres_billing_usage_subscription_and_invoice_reconcile() -> None:
    repo = PostgresRepository()
    agent = await repo.create_agent(TENANT, "Billing repository", str(USER))
    subscription_id = f"sub_test_{uuid4().hex}"
    invoice_id = f"in_test_{uuid4().hex}"
    call_id: UUID | None = None
    try:
        published = await repo.publish_agent(TENANT, agent["id"])
        assert published
        call = await repo.create_call(
            TENANT,
            agent["id"],
            {},
            {},
            agent_version_id=published["current_version_id"],
        )
        call_id = call["id"]
        async with SessionFactory() as db, db.begin():
            await db.execute(text("SET LOCAL row_security = off"))
            await db.execute(
                text(
                    "UPDATE calls SET started_at=now()-interval '121 seconds',ended_at=now() WHERE id=:id"
                ),
                {"id": call_id},
            )
        await repo.update_internal_call(call_id, {"status": "completed"})
        usage = await repo.get_billing_usage(TENANT, datetime.now(UTC).date().replace(day=1))
        assert usage["minutes"] >= 3
        await repo.upsert_subscription(
            TENANT,
            {"plan_code": "pro", "stripe_subscription_id": subscription_id, "status": "active"},
        )
        assert (await repo.get_billing_plan(TENANT))["code"] == "pro"  # type: ignore[index]
        await repo.upsert_invoice(
            TENANT,
            {"stripe_invoice_id": invoice_id, "amount_cents": 89700, "status": "paid"},
        )
        assert any(
            item["stripe_invoice_id"] == invoice_id for item in await repo.list_invoices(TENANT)
        )
    finally:
        async with SessionFactory() as db, db.begin():
            await db.execute(text("SET LOCAL row_security = off"))
            await db.execute(
                text("DELETE FROM invoices WHERE stripe_invoice_id=:id"), {"id": invoice_id}
            )
            await db.execute(
                text("DELETE FROM subscriptions WHERE stripe_subscription_id=:id"),
                {"id": subscription_id},
            )
            if call_id:
                await db.execute(
                    text("DELETE FROM usage_records WHERE call_id=:id"), {"id": call_id}
                )
                await db.execute(text("DELETE FROM calls WHERE id=:id"), {"id": call_id})
            await db.execute(
                text("DELETE FROM agent_versions WHERE agent_id=:id"), {"id": agent["id"]}
            )
            await db.execute(text("DELETE FROM agents WHERE id=:id"), {"id": agent["id"]})


@pytest.mark.asyncio(loop_scope="module")
async def test_postgres_agent_and_call_lifecycle() -> None:
    repo = PostgresRepository()
    agent = await repo.create_agent(TENANT, "Repository coverage", str(USER))
    agent_id = agent["id"]
    call_ids: list[UUID] = []
    tool_id: UUID | None = None
    end_user_id: UUID | None = None
    kb_id: UUID | None = None
    document_id: UUID | None = None
    secret_id: UUID | None = None
    integration_id: UUID | None = None
    try:
        assert await repo.get_agent(TENANT, agent_id)
        assert await repo.get_agent_detail(TENANT, agent_id)
        assert (await repo.update_agent(TENANT, agent_id, {"name": "Repository covered"}))[
            "name"
        ] == "Repository covered"  # type: ignore[index]
        assert await repo.update_agent(TENANT, agent_id, {})
        assert await repo.update_agent(TENANT, UUID(int=0), {"name": "missing"}) is None

        draft = await repo.update_draft(
            TENANT, agent_id, {"system_prompt": "Versão um", "rag": {"enabled": True}}
        )
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
            {
                "name": f"repo_tool_{str(agent_id)[:8]}",
                "description": "Teste",
                "type": "webhook",
                "native_kind": None,
                "parameters_schema": {"type": "object"},
                "webhook": None,
                "speak_before": None,
                "async": False,
            },
        )
        tool_id = tool["id"]
        assert [item["id"] for item in await repo.list_tools(TENANT) if item["id"] == tool_id] == [
            tool_id
        ]
        assert await repo.get_tool(TENANT, tool_id)
        updated_tool = await repo.update_tool(TENANT, tool_id, {"speak_before": "Consultando"})
        assert updated_tool and updated_tool["speak_before"] == "Consultando"
        linked = await repo.set_draft_tools(TENANT, agent_id, [tool_id])
        assert linked and linked[0]["id"] == tool_id
        draft_runtime = await repo.get_runtime(agent_id, "draft")
        assert draft_runtime and draft_runtime["tools"][0]["id"] == tool_id
        published_with_tool = await repo.publish_agent(TENANT, agent_id)
        assert published_with_tool
        current_runtime = await repo.get_runtime(agent_id, "current")
        assert current_runtime and current_runtime["tools"][0]["id"] == tool_id
        assert await repo.get_runtime(agent_id, str(current_runtime["version_id"]))
        assert await repo.get_runtime(agent_id, "invalid") is None

        kb = await repo.create_knowledge_base(
            TENANT,
            {
                "name": f"KB {str(agent_id)[:8]}",
                "embedding_model": "text-embedding-3-small",
                "chunk_size": 400,
                "chunk_overlap": 50,
            },
        )
        kb_id = kb["id"]
        assert await repo.get_knowledge_base(TENANT, kb_id)
        assert await repo.get_knowledge_base_tenant(kb_id) == TENANT
        assert any(item["id"] == kb_id for item in await repo.list_knowledge_bases(TENANT))
        assert (await repo.update_knowledge_base(TENANT, kb_id, {"name": "KB updated"}))[
            "name"
        ] == "KB updated"  # type: ignore[index]
        document = await repo.create_document(
            TENANT, kb_id, {"name": "FAQ", "source_type": "text", "source_uri": None}
        )
        assert document
        document_id = document["id"]
        vector = [1.0] + [0.0] * 1535
        await repo.complete_document(
            TENANT,
            document_id,
            [{"content": "Prazo dois dias", "embedding": vector, "metadata": {}, "token_count": 4}],
        )
        assert (await repo.list_documents(TENANT, kb_id))[0]["status"] == "ready"
        matches = await repo.query_chunks(TENANT, kb_id, vector, 5, 0.99)
        assert matches[0]["content"] == "Prazo dois dias"
        secret = await repo.create_secret(TENANT, "repo_secret", b"encrypted", "test-key")
        secret_id = secret["id"]
        assert "ciphertext" not in secret
        assert (await repo.get_secret(TENANT, secret_id))["ciphertext"] == b"encrypted"  # type: ignore[index]
        assert any(item["id"] == secret_id for item in await repo.list_secrets(TENANT))
        integration = await repo.upsert_integration(
            TENANT,
            "google",
            {
                "scopes": ["calendar"],
                "refresh_token_secret_id": secret_id,
                "account_email": "owner@example.com",
                "status": "active",
            },
        )
        integration_id = integration["id"]
        assert (await repo.get_integration(TENANT, "google"))[
            "account_email"
        ] == "owner@example.com"  # type: ignore[index]
        updated_integration = await repo.upsert_integration(
            TENANT,
            "google",
            {
                "scopes": ["calendar"],
                "refresh_token_secret_id": secret_id,
                "account_email": "new@example.com",
                "status": "active",
            },
        )
        assert (
            updated_integration["id"] == integration_id
            and updated_integration["account_email"] == "new@example.com"
        )

        end_user = await repo.upsert_end_user(
            TENANT,
            {"external_id": f"repo-{agent_id}", "name": "Mario", "metadata": {"source": "pytest"}},
        )
        end_user_id = end_user["id"]
        updated_end_user = await repo.upsert_end_user(
            TENANT,
            {
                "external_id": f"repo-{agent_id}",
                "phone": "+5511999999999",
                "metadata": {"updated": True},
            },
        )
        assert updated_end_user["id"] == end_user_id
        assert updated_end_user["metadata"] == {"source": "pytest", "updated": True}

        call = await repo.create_call(
            TENANT,
            agent_id,
            {"name": "Mario"},
            {"source": "pytest"},
            agent_version_id=first_version,
            end_user_id=end_user_id,
        )
        call_id = call["id"]
        call_ids.append(call_id)
        assert await repo.get_call(TENANT, call_id)
        assert any(item["id"] == call_id for item in await repo.list_calls(TENANT))
        assert [
            item["id"]
            for item in await repo.list_calls(
                TENANT,
                {
                    "agent_id": agent_id,
                    "channel": "web",
                    "status": "queued",
                    "end_user_id": end_user_id,
                },
            )
        ] == [call_id]
        assert [item["id"] for item in await repo.list_calls(TENANT, {"q": str(call_id)})] == [
            call_id
        ]
        outbound_call = await repo.create_call(
            TENANT,
            agent_id,
            {},
            {"source": "outbound-test"},
            agent_version_id=first_version,
            end_user_id=end_user_id,
            channel="phone_outbound",
            from_number="+551140008888",
            to_number="+5511999990001",
        )
        call_ids.append(outbound_call["id"])
        persisted_outbound = await repo.update_call(
            TENANT,
            outbound_call["id"],
            {"status": "ringing", "provider_call_sid": "SIP_TEST_1"},
        )
        assert persisted_outbound
        assert persisted_outbound["channel"] == "phone_outbound"
        assert persisted_outbound["from_number"] == "+551140008888"
        assert persisted_outbound["to_number"] == "+5511999990001"
        assert persisted_outbound["provider_call_sid"] == "SIP_TEST_1"
        today = datetime.now(UTC).date()
        assert [
            item["id"]
            for item in await repo.list_calls(TENANT, {"from": today, "to": today})
            if item["id"] == call_id
        ] == [call_id]
        assert [
            item["id"]
            for item in await repo.list_calls(TENANT, {"q": "+5511999999999"})
            if item["id"] == call_id
        ] == [call_id]
        assert await repo.update_call(
            TENANT, call_id, {"status": "in_progress", "latency": {"ttfb_p50_ms": 700}}
        )
        assert await repo.update_call(TENANT, call_id, {})

        assert (
            await repo.append_call_events(
                call_id, [{"type": "call.answered", "payload": {}, "at": datetime.now(UTC)}]
            )
            == 1
        )
        assert (
            await repo.append_call_turns(
                call_id,
                [
                    {
                        "id": None,
                        "ordinal": 0,
                        "role": "user",
                        "text": "Olá",
                        "started_at": None,
                        "ended_at": None,
                        "interrupted": False,
                        "ttfb_ms": None,
                        "stt_confidence": 0.98,
                        "audio_offset_ms": 0,
                    }
                ],
            )
            == 1
        )
        tool_call = await repo.append_call_tool_call(
            call_id,
            {
                "id": None,
                "turn_id": None,
                "tool_id": tool_id,
                "name": tool["name"],
                "arguments": {"id": 42},
                "result": {"ok": True},
                "status": "ok",
                "duration_ms": 20,
                "started_at": datetime.now(UTC),
            },
        )
        assert tool_call
        detail = await repo.get_call_detail(TENANT, call_id)
        assert (
            detail
            and len(detail["events"]) == len(detail["turns"]) == len(detail["tool_calls"]) == 1
        )

        internal_call = await repo.create_internal_call(
            {
                "tenant_id": TENANT,
                "agent_id": agent_id,
                "agent_version_id": first_version,
                "channel": "web",
                "livekit_room": "room_test",
                "variables": {},
                "metadata": {},
            }
        )
        call_ids.append(internal_call["id"])
        assert await repo.update_internal_call(
            internal_call["id"], {"status": "completed", "ended_at": datetime.now(UTC)}
        )
        assert await repo.update_internal_call(UUID(int=0), {"status": "failed"}) is None
        assert (
            await repo.append_call_events(
                UUID(int=0), [{"type": "error", "payload": {}, "at": datetime.now(UTC)}]
            )
            == 0
        )
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
                await db.execute(
                    text("DELETE FROM call_tool_calls WHERE call_id=:id"), {"id": call_id}
                )
                await db.execute(text("DELETE FROM call_turns WHERE call_id=:id"), {"id": call_id})
                await db.execute(text("DELETE FROM calls WHERE id=:id"), {"id": call_id})
            if tool_id:
                await db.execute(text("DELETE FROM agent_tools WHERE tool_id=:id"), {"id": tool_id})
            await db.execute(
                text("DELETE FROM agent_versions WHERE agent_id=:id"), {"id": agent_id}
            )
            await db.execute(text("DELETE FROM agents WHERE id=:id"), {"id": agent_id})
            if tool_id:
                await db.execute(text("DELETE FROM tools WHERE id=:id"), {"id": tool_id})
            if end_user_id:
                await db.execute(text("DELETE FROM end_users WHERE id=:id"), {"id": end_user_id})
            if document_id:
                await db.execute(
                    text("DELETE FROM chunks WHERE document_id=:id"), {"id": document_id}
                )
                await db.execute(text("DELETE FROM documents WHERE id=:id"), {"id": document_id})
            if kb_id:
                await db.execute(text("DELETE FROM knowledge_bases WHERE id=:id"), {"id": kb_id})
            if secret_id:
                if integration_id:
                    await db.execute(
                        text("DELETE FROM integrations WHERE id=:id"), {"id": integration_id}
                    )
                await db.execute(text("DELETE FROM secrets WHERE id=:id"), {"id": secret_id})
