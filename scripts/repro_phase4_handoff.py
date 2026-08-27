import asyncio
import json

import asyncpg
import httpx
import jwt


async def main() -> None:
    conn = await asyncpg.connect("postgresql://voiceos:voiceos@127.0.0.1:5432/voiceos")
    tenant_id = await conn.fetchval("select id::text from tenants where slug='demo' limit 1")
    await conn.close()
    if not tenant_id:
        raise RuntimeError("demo tenant not found")

    token = jwt.encode(
        {
            "sub": "user-1",
            "iss": "voiceos",
            "aud": "voiceos-api",
            "tenants": [{"id": tenant_id, "role": "owner"}],
        },
        "dev-secret-change-me-at-least-32-bytes",
        algorithm="HS256",
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": tenant_id,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8005", timeout=20) as client:
        agents = await client.get("/v1/agents", headers=headers)
        agents.raise_for_status()
        agent_id = agents.json()["data"][0]["id"]

        phone = "phone-repro-1"
        connect = await client.post(
            "/v1/integrations/whatsapp",
            headers=headers,
            json={
                "phone_number_id": phone,
                "business_account_id": "waba-repro-1",
                "access_token": "token-repro-whatsapp-123",
                "agent_id": agent_id,
            },
        )
        print("integration", connect.status_code, connect.text)

        webhook_body = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": phone},
                                "messages": [
                                    {
                                        "id": "wamid-repro-1",
                                        "from": "+551122233344",
                                        "type": "text",
                                        "text": {"body": "preciso de humano"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
        webhook = await client.post(
            "/webhooks/whatsapp",
            content=json.dumps(webhook_body),
            headers={"Content-Type": "application/json"},
        )
        print("webhook", webhook.status_code, webhook.text)

        calls = await client.get("/v1/calls", headers=headers)
        calls.raise_for_status()
        data = calls.json()["data"]
        target = next(
            item
            for item in data
            if item.get("channel") == "whatsapp"
            and item.get("from_number") == "+551122233344"
        )
        handoff = await client.post(
            f"/v1/calls/{target['id']}/whatsapp-handoff",
            headers=headers,
            json={"text": "operador repro"},
        )
        print("handoff", handoff.status_code, handoff.text)


if __name__ == "__main__":
    asyncio.run(main())
