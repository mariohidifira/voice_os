"""Real PostgreSQL RLS acceptance check for tenants, agents and calls."""

import asyncio
from uuid import UUID

from sqlalchemy import text
from voiceos_api.db import SessionFactory

TENANT_A = UUID("00000000-0000-0000-0000-000000000001")
TENANT_B = UUID("00000000-0000-0000-0000-0000000000b0")
AGENT_B = UUID("00000000-0000-0000-0000-0000000000b1")
CALL_B = UUID("00000000-0000-0000-0000-0000000000b2")


async def visible_count(table: str, tenant_id: UUID) -> int:
    async with SessionFactory() as db, db.begin():
        await db.execute(text("SET LOCAL ROLE voiceos_app"))
        await db.execute(text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": str(tenant_id)})
        return int((await db.execute(text(f'SELECT count(*) FROM "{table}"'))).scalar_one())


async def main() -> None:
    async with SessionFactory() as db, db.begin():
        await db.execute(text("SET LOCAL row_security = off"))
        await db.execute(text("DELETE FROM calls WHERE tenant_id=:id"), {"id": TENANT_B})
        await db.execute(text("DELETE FROM agents WHERE tenant_id=:id"), {"id": TENANT_B})
        await db.execute(text("INSERT INTO tenants(id,slug,name,status) VALUES(:id,'rls-b','RLS B','trial') ON CONFLICT(id) DO NOTHING"), {"id": TENANT_B})
        await db.execute(text("INSERT INTO agents(id,tenant_id,name,status) VALUES(:agent,:tenant,'RLS B Agent','draft')"), {"agent": AGENT_B, "tenant": TENANT_B})
        await db.execute(text("INSERT INTO calls(id,tenant_id,agent_id,channel,status) VALUES(:call,:tenant,:agent,'web','completed')"), {"call": CALL_B, "tenant": TENANT_B, "agent": AGENT_B})

    results = {
        "tenant_a": await visible_count("tenants", TENANT_A),
        "tenant_b": await visible_count("tenants", TENANT_B),
        "agents_a": await visible_count("agents", TENANT_A),
        "agents_b": await visible_count("agents", TENANT_B),
        "calls_a": await visible_count("calls", TENANT_A),
        "calls_b": await visible_count("calls", TENANT_B),
    }
    assert results == {"tenant_a": 1, "tenant_b": 1, "agents_a": 1, "agents_b": 1, "calls_a": 20, "calls_b": 1}, results
    print(f"RLS isolation passed: {results}")


if __name__ == "__main__":
    asyncio.run(main())
