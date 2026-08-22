"""Idempotent PostgreSQL development seed."""

import asyncio
from uuid import UUID

from sqlalchemy import text
from voiceos_api.db import SessionFactory

TENANT = UUID("00000000-0000-0000-0000-000000000001")
USER = UUID("00000000-0000-0000-0000-000000000002")
AGENT = UUID("00000000-0000-0000-0000-000000000003")
VERSION = UUID("00000000-0000-0000-0000-000000000004")
KB = UUID("00000000-0000-0000-0000-000000000005")


async def seed() -> None:
    async with SessionFactory() as db, db.begin():
        await db.execute(text("SET LOCAL row_security = off"))
        await db.execute(
            text(
                "INSERT INTO plans(code,name,monthly_price_cents,included_minutes,overage_cents_per_min,max_agents,max_concurrent_calls,features) VALUES ('trial','Trial',0,60,0,1,2,jsonb_build_object('web',true)),('starter','Starter',29700,500,79,2,5,jsonb_build_object('phone',true)),('pro','Pro',89700,2000,69,10,20,jsonb_build_object('campaigns',true,'api',true)),('business','Business',249700,7000,59,NULL,50,jsonb_build_object('whatsapp',true,'white_label',true)),('enterprise','Enterprise',0,0,0,NULL,NULL,jsonb_build_object('all',true)) ON CONFLICT(code) DO NOTHING"
            )
        )
        await db.execute(
            text(
                "INSERT INTO tenants(id,slug,name,status,settings) VALUES(:id,'demo','VoiceOS Demo','trial',jsonb_build_object('timezone','America/Sao_Paulo','locale','pt-BR','retention_days',90,'recording_enabled',true)) ON CONFLICT(id) DO NOTHING"
            ),
            {"id": TENANT},
        )
        await db.execute(
            text(
                "INSERT INTO users(id,email,name,is_platform_admin) VALUES(:id,'owner@demo.voiceos.local','Demo Owner',false) ON CONFLICT(id) DO NOTHING"
            ),
            {"id": USER},
        )
        await db.execute(
            text(
                "INSERT INTO memberships(tenant_id,user_id,role) VALUES(:tenant,:user,'owner') ON CONFLICT(user_id,tenant_id) DO NOTHING"
            ),
            {"tenant": TENANT, "user": USER},
        )
        await db.execute(
            text(
                "INSERT INTO agents(id,tenant_id,name,status,current_version_id,draft_version_id) VALUES(:id,:tenant,'Recepcionista','active',:version,:version) ON CONFLICT(id) DO NOTHING"
            ),
            {"id": AGENT, "tenant": TENANT, "version": VERSION},
        )
        await db.execute(
            text(
                "INSERT INTO agent_versions(id,tenant_id,agent_id,version,published_at,system_prompt,greeting,llm,stt,tts,turn_config,behavior,rag,variables,created_by) VALUES(:id,:tenant,:agent,1,now(),'Você é uma recepcionista cordial da VoiceOS Demo.','Olá! Aqui é a Recepcionista da VoiceOS Demo. Como posso ajudar?',jsonb_build_object('provider','anthropic','temperature',0.3,'max_tokens',350),jsonb_build_object('provider','deepgram','model','nova-3'),jsonb_build_object('provider','elevenlabs','model','eleven_flash_v2_5'),jsonb_build_object('allow_interruptions',true),jsonb_build_object('max_call_duration_s',900),jsonb_build_object('enabled',true,'top_k',5),'{}'::jsonb,:user) ON CONFLICT(id) DO NOTHING"
            ),
            {"id": VERSION, "tenant": TENANT, "agent": AGENT, "user": USER},
        )
        await db.execute(
            text(
                "INSERT INTO knowledge_bases(id,tenant_id,name,status) VALUES(:id,:tenant,'Base Demo','ready') ON CONFLICT(id) DO NOTHING"
            ),
            {"id": KB, "tenant": TENANT},
        )
        for ordinal in range(3):
            await db.execute(
                text(
                    "INSERT INTO documents(id,tenant_id,knowledge_base_id,name,source_type,status,chunk_count,checksum) VALUES(:id,:tenant,:kb,:name,'text','ready',1,:checksum) ON CONFLICT(id) DO NOTHING"
                ),
                {
                    "id": UUID(int=100 + ordinal),
                    "tenant": TENANT,
                    "kb": KB,
                    "name": f"Documento demo {ordinal + 1}",
                    "checksum": f"demo-{ordinal + 1}",
                },
            )
        tools = [
            (UUID(int=200), "consultar_pedido", "webhook", None),
            (UUID(int=201), "transfer_call", "native", "transfer_call"),
            (UUID(int=202), "lookup_end_user", "native", "lookup_end_user"),
        ]
        for tool_id, name, kind, native in tools:
            await db.execute(
                text(
                    "INSERT INTO tools(id,tenant_id,name,description,type,native_kind,parameters_schema,webhook) VALUES(:id,:tenant,:name,:description,:kind,:native,jsonb_build_object('type','object'),CAST(:webhook AS jsonb)) ON CONFLICT(id) DO NOTHING"
                ),
                {
                    "id": tool_id,
                    "tenant": TENANT,
                    "name": name,
                    "description": f"Use quando precisar {name.replace('_', ' ')}",
                    "kind": kind,
                    "native": native,
                    "webhook": '{"url":"http://mock:9000/tools/consultar_pedido","method":"POST","timeout_ms":8000}'
                    if kind == "webhook"
                    else None,
                },
            )
        for ordinal in range(20):
            await db.execute(
                text(
                    "INSERT INTO calls(id,tenant_id,agent_id,agent_version_id,channel,status,started_at,ended_at,duration_s,billable_seconds,summary) VALUES(:id,:tenant,:agent,:version,'web','completed',now()-(:minutes || ' minutes')::interval,now()-(:minutes || ' minutes')::interval+interval '2 minutes',120,120,:summary) ON CONFLICT(id) DO NOTHING"
                ),
                {
                    "id": UUID(int=1000 + ordinal),
                    "tenant": TENANT,
                    "agent": AGENT,
                    "version": VERSION,
                    "minutes": str(ordinal * 10),
                    "summary": f"Chamada demo {ordinal + 1}",
                },
            )
        demo_turns = [
            (UUID(int=2000), 0, "user", "Olá, quero agendar uma consulta.", 0),
            (UUID(int=2001), 1, "agent", "Claro. Qual é o melhor dia para você?", 3200),
        ]
        for turn_id, ordinal, role, content, offset_ms in demo_turns:
            await db.execute(
                text(
                    "INSERT INTO call_turns(id,tenant_id,call_id,ordinal,role,text,audio_offset_ms) VALUES(:id,:tenant,:call,:ordinal,:role,:content,:offset) ON CONFLICT(id) DO NOTHING"
                ),
                {
                    "id": turn_id,
                    "tenant": TENANT,
                    "call": UUID(int=1000),
                    "ordinal": ordinal,
                    "role": role,
                    "content": content,
                    "offset": offset_ms,
                },
            )
    print("Development seed ready: demo tenant, owner, agent, KB, tools and 20 calls")


if __name__ == "__main__":
    asyncio.run(seed())
