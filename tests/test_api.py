from uuid import uuid4

import jwt
from fastapi.testclient import TestClient
from voiceos_api.config import get_settings
from voiceos_api.health import get_health_checker
from voiceos_api.live import get_event_bus
from voiceos_api.main import app
from voiceos_api.repository import MemoryRepository, get_repository
from voiceos_api.store import store

client = TestClient(app)
app.dependency_overrides[get_repository] = lambda: MemoryRepository(store)


class HealthyChecker:
    async def check(self) -> dict[str, object]:
        return {"status": "ok", "service": "api", "components": {"database": True, "redis": True, "s3": True, "livekit_token": True}}


app.dependency_overrides[get_health_checker] = HealthyChecker


class FakeEventBus:
    def __init__(self) -> None:
        self.events: list[tuple[object, object, dict[str, object]]] = []

    async def publish(self, tenant_id: object, call_id: object, event: dict[str, object]) -> None:
        self.events.append((tenant_id, call_id, event))

    async def subscribe(self, tenant_id: object, call_id: object):  # type: ignore[no-untyped-def]
        if False:
            yield {}


event_bus = FakeEventBus()
app.dependency_overrides[get_event_bus] = lambda: event_bus


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
    store.end_users.clear()
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


def test_session_end_user_filters_and_draft_test_session() -> None:
    store.agents.clear()
    store.agent_versions.clear()
    store.end_users.clear()
    store.calls.clear()
    tenant = str(uuid4())
    auth = headers(tenant)
    agent = client.post("/v1/agents", json={"name": "Sessions"}, headers=auth).json()
    published = client.post(f"/v1/agents/{agent['id']}/publish", headers=auth).json()
    session = client.post(
        "/v1/sessions",
        json={"agent_id": agent["id"], "end_user": {"external_id": "customer-42", "name": "Cliente"}},
        headers=auth,
    ).json()
    call = client.get(f"/v1/calls/{session['call_id']}", headers=auth).json()
    assert call["agent_version_id"] == published["current_version_id"]
    assert call["end_user_id"]
    assert len(client.get(f"/v1/calls?agent_id={agent['id']}&channel=web&status=queued", headers=auth).json()["data"]) == 1

    detail = client.get(f"/v1/agents/{agent['id']}", headers=auth).json()
    test_session = client.post(
        f"/v1/agents/{agent['id']}/test-session",
        json={"agent_id": agent["id"], "end_user": {"external_id": "customer-42", "phone": "+5511999999999"}},
        headers=auth,
    ).json()
    test_call = client.get(f"/v1/calls/{test_session['call_id']}", headers=auth).json()
    assert test_call["agent_version_id"] == detail["draft"]["id"]
    assert len(store.end_users) == 1


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
    store.agent_tools.clear()
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
    tool_id = tool.json()["id"]
    assert client.get("/v1/tools", headers=headers(tenant)).json()["data"][0]["id"] == tool_id
    assert client.patch(f"/v1/tools/{tool_id}", json={"speak_before": "Consultando"}, headers=headers(tenant)).json()["speak_before"] == "Consultando"
    assert client.put(f"/v1/agents/{agent['id']}/draft/tools", json={"tool_ids": [tool_id]}, headers=headers(tenant)).status_code == 200
    runtime = client.get(
        f"/internal/agents/{agent['id']}/runtime?version=draft",
        headers={"X-Internal-Token": get_settings().internal_api_token},
    )
    assert runtime.status_code == 200
    assert runtime.json()["language"] == "pt-BR"
    assert runtime.json()["tools"][0]["name"] == "consultar_pedido"
    published = client.post(f"/v1/agents/{agent['id']}/publish", headers=headers(tenant)).json()
    current = client.get(f"/internal/agents/{agent['id']}/runtime?version=current", headers={"X-Internal-Token": get_settings().internal_api_token}).json()
    assert current["version_id"] == published["current_version_id"]
    assert current["tools"][0]["id"] == tool_id
    next_draft = client.get(f"/internal/agents/{agent['id']}/runtime?version=draft", headers={"X-Internal-Token": get_settings().internal_api_token}).json()
    assert next_draft["tools"][0]["id"] == tool_id
    assert client.get(f"/internal/agents/{agent['id']}/runtime?version=invalid", headers={"X-Internal-Token": get_settings().internal_api_token}).status_code == 404
    assert client.delete(f"/v1/tools/{tool_id}", headers=headers(tenant)).status_code == 204


def test_call_lifecycle_internal_batches_and_detail() -> None:
    store.agents.clear()
    store.agent_versions.clear()
    store.calls.clear()
    store.call_events.clear()
    store.call_turns.clear()
    store.call_tool_calls.clear()
    event_bus.events.clear()
    tenant = str(uuid4())
    auth = headers(tenant)
    internal = {"X-Internal-Token": get_settings().internal_api_token}
    agent = client.post("/v1/agents", json={"name": "Call lifecycle"}, headers=auth).json()
    client.post(f"/v1/agents/{agent['id']}/publish", headers=auth)
    session = client.post("/v1/sessions", json={"agent_id": agent["id"]}, headers=auth).json()
    call_id = session["call_id"]
    assert session["session_id"] == call_id

    patched = client.patch(
        f"/internal/calls/{call_id}",
        json={"status": "in_progress", "latency": {"ttfb_p50_ms": 720}},
        headers=internal,
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "in_progress"

    events = client.post(
        f"/internal/calls/{call_id}/events",
        json={"events": [{"type": "call.answered", "payload": {}, "at": "2026-08-19T12:00:00Z"}]},
        headers=internal,
    )
    assert events.json() == {"accepted": 1}
    turns = client.post(
        f"/internal/calls/{call_id}/turns",
        json={"turns": [{"ordinal": 0, "role": "user", "text": "Olá"}, {"ordinal": 1, "role": "agent", "text": "Como posso ajudar?", "ttfb_ms": 720}]},
        headers=internal,
    )
    assert turns.json() == {"accepted": 2}
    tool_call = client.post(
        f"/internal/calls/{call_id}/tool-calls",
        json={"name": "consultar_pedido", "arguments": {"id": "42"}, "result": {"status": "enviado"}, "status": "ok", "duration_ms": 25},
        headers=internal,
    )
    assert tool_call.status_code == 201
    assert [event[2]["type"] for event in event_bus.events] == ["call.answered", "turn.user", "turn.agent", "tool.called"]

    detail = client.get(f"/v1/calls/{call_id}", headers=auth).json()
    assert [turn["role"] for turn in detail["turns"]] == ["user", "agent"]
    assert detail["events"][0]["type"] == "call.answered"
    assert detail["tool_calls"][0]["name"] == "consultar_pedido"

    ended = client.post(f"/v1/calls/{call_id}/hangup", headers=auth)
    assert ended.json()["end_reason"] == "agent_hangup"
    assert client.delete(f"/v1/sessions/{call_id}", headers=auth).status_code == 204
    assert client.get(f"/v1/calls/{uuid4()}/live", headers=auth).status_code == 404


def test_invalid_token_and_wrong_tenant() -> None:
    tenant = str(uuid4())
    assert client.get("/v1/me", headers={"Authorization": "Bearer invalid", "X-Tenant-Id": tenant}).status_code == 401
    settings = get_settings()
    token = jwt.encode({"sub": "u", "iss": settings.jwt_issuer, "aud": settings.jwt_audience, "tenants": []}, settings.auth_secret, algorithm="HS256")
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant}).status_code == 403
