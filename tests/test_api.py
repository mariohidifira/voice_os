from uuid import uuid4

import jwt
from fastapi.testclient import TestClient
from voiceos_api.config import get_settings
from voiceos_api.health import get_health_checker
from voiceos_api.main import app
from voiceos_api.repository import MemoryRepository, get_repository
from voiceos_api.store import store

client = TestClient(app)
app.dependency_overrides[get_repository] = lambda: MemoryRepository(store)


class HealthyChecker:
    async def check(self) -> dict[str, object]:
        return {"status": "ok", "service": "api", "components": {"database": True, "redis": True, "s3": True, "livekit_token": True}}


app.dependency_overrides[get_health_checker] = HealthyChecker


def headers(tenant: str, role: str = "owner") -> dict[str, str]:
    settings = get_settings()
    token = jwt.encode({"sub": "user-1", "iss": settings.jwt_issuer, "aud": settings.jwt_audience, "tenants": [{"id": tenant, "role": role}]}, settings.auth_secret, algorithm="HS256")
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant}


def test_health_and_error_contract() -> None:
    assert client.get("/health").json()["status"] == "ok"
    response = client.get("/v1/me")
    assert response.status_code == 401
    assert set(response.json()["error"]) == {"code", "message", "details", "request_id"}


def test_agent_publish_session_and_isolation() -> None:
    store.agents.clear()
    store.agent_versions.clear()
    store.calls.clear()
    tenant_a, tenant_b = str(uuid4()), str(uuid4())
    created = client.post("/v1/agents", json={"name": "Recepcionista"}, headers=headers(tenant_a))
    assert created.status_code == 201
    agent = created.json()
    assert client.get("/v1/agents", headers=headers(tenant_b)).json()["data"] == []
    assert client.post(f"/v1/agents/{agent['id']}/publish", headers=headers(tenant_a)).json()["status"] == "active"
    session = client.post("/v1/sessions", json={"agent_id": agent["id"]}, headers=headers(tenant_a))
    assert session.status_code == 201
    assert client.get("/v1/calls", headers=headers(tenant_b)).json()["data"] == []


def test_agent_draft_versions_and_rollback() -> None:
    store.agents.clear()
    store.agent_versions.clear()
    tenant = str(uuid4())
    auth = headers(tenant)
    created = client.post("/v1/agents", json={"name": "Concierge"}, headers=auth).json()

    detail = client.get(f"/v1/agents/{created['id']}", headers=auth)
    assert detail.status_code == 200
    assert detail.json()["draft"]["version"] == 1
    assert detail.json()["current"] is None

    draft = client.patch(
        f"/v1/agents/{created['id']}/draft",
        json={"system_prompt": "Atenda como concierge.", "llm": {"provider": "anthropic", "temperature": 0.2}},
        headers=auth,
    )
    assert draft.status_code == 200
    assert draft.json()["system_prompt"] == "Atenda como concierge."

    first_publish = client.post(f"/v1/agents/{created['id']}/publish", headers=auth)
    assert first_publish.status_code == 200
    first_version_id = first_publish.json()["current_version_id"]
    assert first_publish.json()["draft"]["version"] == 2

    client.patch(
        f"/v1/agents/{created['id']}/draft",
        json={"system_prompt": "Atenda como concierge versão dois."},
        headers=auth,
    )
    second_publish = client.post(f"/v1/agents/{created['id']}/publish", headers=auth)
    second_version_id = second_publish.json()["current_version_id"]
    assert second_version_id != first_version_id

    versions = client.get(f"/v1/agents/{created['id']}/versions", headers=auth).json()["data"]
    assert [version["version"] for version in versions] == [3, 2, 1]
    assert client.get(f"/v1/agents/{created['id']}/versions/{first_version_id}", headers=auth).status_code == 200

    rolled_back = client.post(
        f"/v1/agents/{created['id']}/rollback",
        json={"version_id": first_version_id},
        headers=auth,
    )
    assert rolled_back.status_code == 200
    assert rolled_back.json()["current_version_id"] == first_version_id

    renamed = client.patch(f"/v1/agents/{created['id']}", json={"name": "Concierge BR"}, headers=auth)
    assert renamed.json()["name"] == "Concierge BR"
    assert client.delete(f"/v1/agents/{created['id']}", headers=auth).status_code == 204
    assert client.get(f"/v1/agents/{created['id']}", headers=auth).status_code == 404


def test_operator_cannot_create_agent() -> None:
    response = client.post("/v1/agents", json={"name": "Blocked"}, headers=headers(str(uuid4()), "operator"))
    assert response.status_code == 403


def test_internal_auth() -> None:
    assert client.get(f"/internal/agents/{uuid4()}/runtime").status_code == 401


def test_tool_and_internal_runtime() -> None:
    store.agents.clear()
    store.tools.clear()
    tenant = str(uuid4())
    agent = client.post("/v1/agents", json={"name": "Runtime"}, headers=headers(tenant)).json()
    tool = client.post(
        "/v1/tools",
        json={
            "name": "consultar_pedido",
            "description": "Use quando consultar um pedido",
            "type": "webhook",
            "parameters_schema": {"type": "object"},
        },
        headers=headers(tenant),
    )
    assert tool.status_code == 201
    runtime = client.get(
        f"/internal/agents/{agent['id']}/runtime",
        headers={"X-Internal-Token": get_settings().internal_api_token},
    )
    assert runtime.status_code == 200
    assert runtime.json()["language"] == "pt-BR"


def test_invalid_token_and_wrong_tenant() -> None:
    tenant = str(uuid4())
    assert client.get("/v1/me", headers={"Authorization": "Bearer invalid", "X-Tenant-Id": tenant}).status_code == 401
    settings = get_settings()
    token = jwt.encode({"sub": "u", "iss": settings.jwt_issuer, "aud": settings.jwt_audience, "tenants": []}, settings.auth_secret, algorithm="HS256")
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant}).status_code == 403
