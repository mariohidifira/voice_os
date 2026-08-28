import hashlib
import hmac
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import jwt
from fastapi.testclient import TestClient
import voiceos_api.routes as api_routes
from voiceos_api.config import get_settings
from voiceos_api.health import get_health_checker
from voiceos_api.live import get_event_bus
from voiceos_api.main import app
from voiceos_api.prompt_improvement import get_prompt_improver
from voiceos_api.repository import MemoryRepository, get_repository
from voiceos_api.storage import get_recording_storage
from voiceos_api.store import store
from voiceos_api.voice_preview import get_voice_preview

client = TestClient(app)
app.dependency_overrides[get_repository] = lambda: MemoryRepository(store)


class HealthyChecker:
    async def check(self) -> dict[str, object]:
        return {
            "status": "ok",
            "service": "api",
            "components": {"database": True, "redis": True, "s3": True, "livekit_token": True},
        }


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


class FakeRecordingStorage:
    async def playback_url(self, key: str, expires_s: int = 900) -> str:
        assert key.startswith("recordings/") and expires_s == 900
        return "https://signed.example/recording.ogg"


app.dependency_overrides[get_recording_storage] = FakeRecordingStorage


class FakePromptImprover:
    async def improve(self, prompt: str) -> str:
        return prompt + " Responda de forma curta e natural."


app.dependency_overrides[get_prompt_improver] = FakePromptImprover


class FakeVoicePreview:
    configured = True

    async def list_voices(self) -> list[dict[str, object]]:
        return [{"id": "voice-1", "name": "Ana", "labels": {"language": "pt"}}]

    async def synthesize(self, voice_id: str, text: str, speed: float) -> bytes:
        assert voice_id == "voice-1" and text == "Olá!" and speed == 1.1
        return b"ID3audio"


app.dependency_overrides[get_voice_preview] = FakeVoicePreview


def headers(tenant: str, role: str = "owner") -> dict[str, str]:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": "user-1",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "tenants": [{"id": tenant, "role": role}],
        },
        settings.auth_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant}


def meta_signature(secret: str, payload: bytes) -> str:
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_health_and_error_contract() -> None:
    assert client.get("/health").json()["status"] == "ok"
    response = client.get("/v1/me")
    assert response.status_code == 401
    assert set(response.json()["error"]) == {"code", "message", "details", "request_id"}


def test_tenant_general_settings_are_scoped_and_admin_mutable() -> None:
    store.tenants.clear()
    tenant = str(uuid4())
    owner = headers(tenant)
    initial = client.get(f"/v1/tenants/{tenant}", headers=owner)
    assert initial.status_code == 200
    changed = client.patch(
        f"/v1/tenants/{tenant}",
        json={
            "name": "Clínica Voz",
            "settings": {
                "timezone": "America/Fortaleza",
                "recording_enabled": False,
                "retention_days": 180,
                "branding": {
                    "product_name": "ClÃ­nica Voz",
                    "primary_color": "#123456",
                    "custom_domain": "voz.clinicavoz.example",
                },
                "widget": {
                    "button_label": "Falar com a clÃ­nica",
                    "theme": "dark",
                    "position": "bottom-left",
                    "livekit_module_url": "https://cdn.example.com/livekit.esm.js",
                },
            },
        },
        headers=owner,
    )
    assert changed.status_code == 200
    assert changed.json()["name"] == "Clínica Voz"
    assert changed.json()["settings"]["locale"] == "pt-BR"
    assert changed.json()["settings"]["retention_days"] == 180
    assert changed.json()["settings"]["branding"]["primary_color"] == "#123456"
    assert changed.json()["settings"]["widget"]["position"] == "bottom-left"
    assert changed.json()["settings"]["widget"]["livekit_module_url"] == (
        "https://cdn.example.com/livekit.esm.js"
    )
    viewer = headers(tenant, "viewer")
    assert client.get(f"/v1/tenants/{tenant}", headers=viewer).status_code == 200
    assert (
        client.patch(f"/v1/tenants/{tenant}", json={"name": "Nope"}, headers=viewer).status_code
        == 403
    )
    assert client.get(f"/v1/tenants/{uuid4()}", headers=owner).status_code == 404


def test_members_and_api_keys_are_tenant_scoped_and_admin_only() -> None:
    store.memberships.clear()
    store.users.clear()
    store.api_keys.clear()
    tenant_a, tenant_b = str(uuid4()), str(uuid4())
    owner = headers(tenant_a)
    viewer = headers(tenant_a, "viewer")

    created = client.post(
        f"/v1/tenants/{tenant_a}/members",
        json={"email": "DEV@EXAMPLE.COM", "role": "developer"},
        headers=owner,
    )
    assert created.status_code == 201
    member = created.json()
    assert member["email"] == "dev@example.com" and member["role"] == "developer"
    assert (
        client.get(f"/v1/tenants/{tenant_a}/members", headers=owner).json()["data"][0]["id"]
        == member["id"]
    )
    assert client.get(f"/v1/tenants/{tenant_b}/members", headers=owner).status_code == 404
    assert (
        client.post(
            f"/v1/tenants/{tenant_a}/members", json={"email": "x@y.dev"}, headers=viewer
        ).status_code
        == 403
    )
    changed = client.patch(
        f"/v1/tenants/{tenant_a}/members/{member['id']}", json={"role": "operator"}, headers=owner
    )
    assert changed.json()["role"] == "operator"

    public_without_origin = client.post(
        "/v1/api-keys", json={"name": "widget", "scope": "public"}, headers=owner
    )
    assert public_without_origin.status_code == 422
    key_response = client.post(
        "/v1/api-keys",
        json={"name": "widget", "scope": "public", "allowed_origins": ["https://app.example.com"]},
        headers=owner,
    )
    assert key_response.status_code == 201
    key = key_response.json()
    assert key["key"].startswith("vos_pk_") and "hash" not in key
    listed = client.get("/v1/api-keys", headers=owner).json()["data"]
    assert (
        listed[0]["prefix"] == key["prefix"] and "key" not in listed[0] and "hash" not in listed[0]
    )
    assert client.get("/v1/api-keys", headers=viewer).status_code == 403
    assert client.delete(f"/v1/api-keys/{key['id']}", headers=owner).status_code == 204
    assert (
        client.delete(f"/v1/tenants/{tenant_a}/members/{member['id']}", headers=owner).status_code
        == 204
    )


def test_tenant_must_always_keep_an_owner() -> None:
    store.memberships.clear()
    store.users.clear()
    tenant = str(uuid4())
    auth = headers(tenant)
    first = client.post(
        f"/v1/tenants/{tenant}/members",
        json={"email": "owner-one@example.com", "role": "owner"},
        headers=auth,
    ).json()
    demote_last = client.patch(
        f"/v1/tenants/{tenant}/members/{first['id']}",
        json={"role": "admin"},
        headers=auth,
    )
    assert demote_last.status_code == 409
    assert demote_last.json()["error"]["code"] == "last_owner_required"
    assert (
        client.delete(f"/v1/tenants/{tenant}/members/{first['id']}", headers=auth).status_code
        == 409
    )

    second = client.post(
        f"/v1/tenants/{tenant}/members",
        json={"email": "owner-two@example.com", "role": "owner"},
        headers=auth,
    ).json()
    assert (
        client.patch(
            f"/v1/tenants/{tenant}/members/{first['id']}",
            json={"role": "admin"},
            headers=auth,
        ).status_code
        == 200
    )
    assert (
        client.delete(f"/v1/tenants/{tenant}/members/{second['id']}", headers=auth).status_code
        == 409
    )
    assert (
        client.patch(
            f"/v1/tenants/{tenant}/members/{first['id']}",
            json={"role": "owner"},
            headers=auth,
        ).status_code
        == 200
    )
    assert (
        client.delete(f"/v1/tenants/{tenant}/members/{second['id']}", headers=auth).status_code
        == 204
    )


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
    assert (
        client.post(f"/v1/agents/{agent['id']}/publish", headers=headers(tenant_a)).json()["status"]
        == "active"
    )
    session = client.post("/v1/sessions", json={"agent_id": agent["id"]}, headers=headers(tenant_a))
    assert session.status_code == 201
    assert client.get("/v1/calls", headers=headers(tenant_b)).json()["data"] == []


def test_required_agent_templates_create_configured_drafts() -> None:
    store.agents.clear()
    store.agent_versions.clear()
    auth = headers(str(uuid4()))
    templates = client.get("/v1/agent-templates", headers=auth)
    assert templates.status_code == 200
    by_id = {item["id"]: item for item in templates.json()["data"]}
    assert set(by_id) == {
        "receptionist",
        "scheduling",
        "lead_qualification",
        "order_support",
        "satisfaction_survey",
        "friendly_collections",
    }
    assert by_id["scheduling"]["suggested_tools"] == [
        "set_variable",
        "google_calendar_check",
        "google_calendar_book",
        "end_call",
    ]

    for template_id in by_id:
        created = client.post(
            "/v1/agents",
            json={"name": f"Template {template_id}", "template_id": template_id},
            headers=auth,
        )
        assert created.status_code == 201
        draft = client.get(f"/v1/agents/{created.json()['id']}", headers=auth).json()["draft"]
        assert draft["system_prompt"] == by_id[template_id]["system_prompt"]
        assert draft["greeting"] == by_id[template_id]["greeting"]
        assert draft["variables"] == by_id[template_id]["variables"]

    invalid = client.post(
        "/v1/agents", json={"name": "Inválido", "template_id": "missing"}, headers=auth
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "template_not_found"


def test_process_draft_can_be_simulated_without_livekit() -> None:
    store.agents.clear()
    store.agent_versions.clear()
    auth = headers(str(uuid4()))
    agent = client.post("/v1/agents", json={"name": "Fluxo"}, headers=auth).json()
    process = {
        "initial_state": "start",
        "states": [
            {"id": "start", "transitions": [{"intent": "yes", "next": "done"}]},
            {"id": "done", "prompt": "Concluído.", "terminal": True},
        ],
        "intents": [{"id": "yes", "examples": ["sim"]}],
    }
    updated = client.patch(
        f"/v1/agents/{agent['id']}/draft",
        json={"behavior": {"execution_mode": "deterministic", "process": process}},
        headers=auth,
    )
    assert updated.status_code == 200
    result = client.post(
        f"/v1/agents/{agent['id']}/draft/process-simulate",
        json={"text": "sim"},
        headers=auth,
    )
    assert result.status_code == 200
    assert result.json()["intent"] == "yes"
    assert result.json()["state"] == "done"
    assert result.json()["terminal"] is True


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
        json={
            "agent_id": agent["id"],
            "end_user": {"external_id": "customer-42", "name": "Cliente"},
        },
        headers=auth,
    ).json()
    call = client.get(f"/v1/calls/{session['call_id']}", headers=auth).json()
    assert call["agent_version_id"] == published["current_version_id"]
    assert call["end_user_id"]
    assert (
        len(
            client.get(
                f"/v1/calls?agent_id={agent['id']}&channel=web&status=queued", headers=auth
            ).json()["data"]
        )
        == 1
    )
    today = datetime.now(UTC).date().isoformat()
    assert len(client.get(f"/v1/calls?q={session['call_id']}", headers=auth).json()["data"]) == 1
    assert len(client.get(f"/v1/calls?from={today}&to={today}", headers=auth).json()["data"]) == 1

    detail = client.get(f"/v1/agents/{agent['id']}", headers=auth).json()
    test_session = client.post(
        f"/v1/agents/{agent['id']}/test-session",
        json={
            "agent_id": agent["id"],
            "end_user": {"external_id": "customer-42", "phone": "+5511999999999"},
        },
        headers=auth,
    ).json()
    test_call = client.get(f"/v1/calls/{test_session['call_id']}", headers=auth).json()
    assert test_call["agent_version_id"] == detail["draft"]["id"]
    assert len(store.end_users) == 1
    assert len(client.get("/v1/calls?q=%2B5511999999999", headers=auth).json()["data"]) == 2


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
        json={
            "system_prompt": "Atenda como concierge.",
            "llm": {"provider": "anthropic", "temperature": 0.2},
        },
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
    assert (
        client.get(
            f"/v1/agents/{created['id']}/versions/{first_version_id}", headers=auth
        ).status_code
        == 200
    )

    rolled_back = client.post(
        f"/v1/agents/{created['id']}/rollback",
        json={"version_id": first_version_id},
        headers=auth,
    )
    assert rolled_back.status_code == 200
    assert rolled_back.json()["current_version_id"] == first_version_id

    renamed = client.patch(
        f"/v1/agents/{created['id']}", json={"name": "Concierge BR"}, headers=auth
    )
    assert renamed.json()["name"] == "Concierge BR"
    assert client.delete(f"/v1/agents/{created['id']}", headers=auth).status_code == 204
    assert client.get(f"/v1/agents/{created['id']}", headers=auth).status_code == 404


def test_operator_cannot_create_agent() -> None:
    response = client.post(
        "/v1/agents", json={"name": "Blocked"}, headers=headers(str(uuid4()), "operator")
    )
    assert response.status_code == 403


def test_operator_and_viewer_cannot_access_agent_configuration_resources() -> None:
    tenant = str(uuid4())
    for role in ("operator", "viewer"):
        auth = headers(tenant, role)
        assert client.get("/v1/tools", headers=auth).status_code == 403
        assert client.get("/v1/secrets", headers=auth).status_code == 403
        assert client.get("/v1/integrations", headers=auth).status_code == 403
        assert client.get("/v1/knowledge-bases", headers=auth).status_code == 403
        assert client.get(f"/v1/tenants/{tenant}/members", headers=auth).status_code == 403
        assert (
            client.post("/v1/knowledge-bases", json={"name": "Blocked"}, headers=auth).status_code
            == 403
        )


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
            "type": "native",
            "native_kind": "end_call",
            "parameters_schema": {"type": "object"},
        },
        headers=headers(tenant),
    )
    assert tool.status_code == 201
    tool_id = tool.json()["id"]
    assert client.get("/v1/tools", headers=headers(tenant)).json()["data"][0]["id"] == tool_id
    assert (
        client.patch(
            f"/v1/tools/{tool_id}", json={"speak_before": "Consultando"}, headers=headers(tenant)
        ).json()["speak_before"]
        == "Consultando"
    )
    assert (
        client.put(
            f"/v1/agents/{agent['id']}/draft/tools",
            json={"tool_ids": [tool_id]},
            headers=headers(tenant),
        ).status_code
        == 200
    )
    linked = client.get(f"/v1/agents/{agent['id']}/draft/tools", headers=headers(tenant))
    assert linked.status_code == 200 and linked.json()["data"][0]["id"] == tool_id
    assert (
        client.get(
            f"/v1/agents/{agent['id']}/draft/tools", headers=headers(str(uuid4()))
        ).status_code
        == 404
    )
    runtime = client.get(
        f"/internal/agents/{agent['id']}/runtime?version=draft",
        headers={"X-Internal-Token": get_settings().internal_api_token},
    )
    assert runtime.status_code == 200
    assert runtime.json()["language"] == "pt-BR"
    assert runtime.json()["tools"][0]["name"] == "consultar_pedido"
    published = client.post(f"/v1/agents/{agent['id']}/publish", headers=headers(tenant)).json()
    current = client.get(
        f"/internal/agents/{agent['id']}/runtime?version=current",
        headers={"X-Internal-Token": get_settings().internal_api_token},
    ).json()
    assert current["version_id"] == published["current_version_id"]
    assert current["tools"][0]["id"] == tool_id
    next_draft = client.get(
        f"/internal/agents/{agent['id']}/runtime?version=draft",
        headers={"X-Internal-Token": get_settings().internal_api_token},
    ).json()
    assert next_draft["tools"][0]["id"] == tool_id
    assert (
        client.get(
            f"/internal/agents/{agent['id']}/runtime?version=invalid",
            headers={"X-Internal-Token": get_settings().internal_api_token},
        ).status_code
        == 404
    )
    assert client.delete(f"/v1/tools/{tool_id}", headers=headers(tenant)).status_code == 204


def test_secret_values_are_encrypted_and_never_returned() -> None:
    store.secrets.clear()
    tenant = str(uuid4())
    auth = headers(tenant)
    created = client.post(
        "/v1/secrets", json={"name": "crm_token", "value": "super-secret"}, headers=auth
    )
    assert created.status_code == 201
    assert "value" not in created.json() and "ciphertext" not in created.json()
    secret_id = created.json()["id"]
    assert next(iter(store.secrets.values()))["ciphertext"] != b"super-secret"
    listed = client.get("/v1/secrets", headers=auth).json()["data"]
    assert listed[0]["name"] == "crm_token" and "ciphertext" not in listed[0]
    assert client.delete(f"/v1/secrets/{secret_id}", headers=auth).status_code == 204


def test_publish_rejects_untested_webhook_tool() -> None:
    store.agents.clear()
    store.agent_versions.clear()
    store.tools.clear()
    store.agent_tools.clear()
    tenant = str(uuid4())
    auth = headers(tenant)
    agent = client.post("/v1/agents", json={"name": "Guarded"}, headers=auth).json()
    tool = client.post(
        "/v1/tools",
        json={
            "name": "crm_lookup",
            "description": "Use para consultar o CRM",
            "type": "webhook",
            "parameters_schema": {"type": "object"},
            "webhook": {"url": "https://example.test", "auth": {"type": "none"}},
        },
        headers=auth,
    ).json()
    client.put(
        f"/v1/agents/{agent['id']}/draft/tools", json={"tool_ids": [tool["id"]]}, headers=auth
    )
    rejected = client.post(f"/v1/agents/{agent['id']}/publish", headers=auth)
    assert rejected.status_code == 422
    assert "must pass a test" in rejected.json()["error"]["details"]["errors"][0]


def test_voice_catalog_and_preview_are_admin_scoped() -> None:
    tenant = str(uuid4())
    owner = headers(tenant)
    catalog = client.get("/v1/voices", headers=owner)
    assert catalog.json() == {
        "data": [{"id": "voice-1", "name": "Ana", "labels": {"language": "pt"}}],
        "configured": True,
    }
    preview = client.post(
        "/v1/voices/voice-1/preview", json={"text": "Olá!", "speed": 1.1}, headers=owner
    )
    assert preview.status_code == 200 and preview.headers["content-type"] == "audio/mpeg"
    assert preview.content == b"ID3audio"
    assert client.get("/v1/voices", headers=headers(tenant, "viewer")).status_code == 403


def test_prompt_improvement_is_preview_only_and_admin_scoped() -> None:
    store.agents.clear()
    store.agent_versions.clear()
    tenant = str(uuid4())
    owner = headers(tenant)
    agent = client.post("/v1/agents", json={"name": "Prompt helper"}, headers=owner).json()
    original = "Você atende como {{ agent.name }} e nunca inventa informações."
    improved = client.post(
        f"/v1/agents/{agent['id']}/draft/improve-prompt", json={"prompt": original}, headers=owner
    )
    assert improved.status_code == 200
    assert improved.json()["improved_prompt"].endswith("curta e natural.")
    detail = client.get(f"/v1/agents/{agent['id']}", headers=owner).json()
    assert detail["draft"]["system_prompt"] != improved.json()["improved_prompt"]
    viewer = client.post(
        f"/v1/agents/{agent['id']}/draft/improve-prompt",
        json={"prompt": original},
        headers=headers(tenant, "viewer"),
    )
    assert viewer.status_code == 403


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
        json={
            "turns": [
                {"ordinal": 0, "role": "user", "text": "Olá"},
                {"ordinal": 1, "role": "agent", "text": "Como posso ajudar?", "ttfb_ms": 720},
            ]
        },
        headers=internal,
    )
    assert turns.json() == {"accepted": 2}
    tool_call = client.post(
        f"/internal/calls/{call_id}/tool-calls",
        json={
            "name": "consultar_pedido",
            "arguments": {"id": "42"},
            "result": {"status": "enviado"},
            "status": "ok",
            "duration_ms": 25,
        },
        headers=internal,
    )
    assert tool_call.status_code == 201
    assert [event[2]["type"] for event in event_bus.events] == [
        "call.answered",
        "turn.user",
        "turn.agent",
        "tool.called",
    ]

    detail = client.get(f"/v1/calls/{call_id}", headers=auth).json()
    assert [turn["role"] for turn in detail["turns"]] == ["user", "agent"]
    assert detail["events"][0]["type"] == "call.answered"
    assert detail["tool_calls"][0]["name"] == "consultar_pedido"
    store.call_recordings[UUID(call_id)] = {
        "s3_key": f"recordings/{tenant}/{call_id}.ogg",
        "format": "ogg",
        "status": "ready",
    }
    recording = client.get(f"/v1/calls/{call_id}/recording", headers=auth, follow_redirects=False)
    assert recording.status_code == 307
    assert recording.headers["location"] == "https://signed.example/recording.ogg"
    assert (
        client.get(
            f"/v1/calls/{call_id}/recording", headers=headers(str(uuid4())), follow_redirects=False
        ).status_code
        == 404
    )

    takeover = client.post(
        f"/v1/calls/{call_id}/takeover",
        json={},
        headers=headers(tenant, "operator"),
    )
    assert takeover.status_code == 200
    assert takeover.json()["mode"] == "web"
    assert takeover.json()["room_name"].startswith("voiceos_")
    assert takeover.json()["token"]
    assert event_bus.events[-1][2]["type"] == "operator.takeover"

    ended = client.post(f"/v1/calls/{call_id}/hangup", headers=auth)
    assert ended.json()["end_reason"] == "agent_hangup"
    assert client.delete(f"/v1/sessions/{call_id}", headers=auth).status_code == 204
    assert client.get(f"/v1/calls/{uuid4()}/live", headers=auth).status_code == 404


def test_public_widget_session_requires_valid_origin_and_public_key() -> None:
    store.api_keys.clear()
    store.agents.clear()
    store.agent_versions.clear()
    store.calls.clear()
    tenant = str(uuid4())
    auth = headers(tenant)
    agent = client.post("/v1/agents", json={"name": "Widget Agent"}, headers=auth).json()
    client.post(f"/v1/agents/{agent['id']}/publish", headers=auth)
    key = client.post(
        "/v1/api-keys",
        json={
            "name": "widget",
            "scope": "public",
            "allowed_origins": ["https://app.example.com"],
        },
        headers=auth,
    ).json()

    denied = client.post(
        f"/v1/public/tenants/{tenant}/widget/sessions",
        json={"agent_id": agent["id"]},
        headers={"X-API-Key": key["key"], "Origin": "https://evil.example.com"},
    )
    assert denied.status_code == 403

    created = client.post(
        f"/v1/public/tenants/{tenant}/widget/sessions",
        json={"agent_id": agent["id"], "metadata": {"source": "embedded_widget"}},
        headers={"X-API-Key": key["key"], "Origin": "https://app.example.com"},
    )
    assert created.status_code == 201
    session = created.json()
    call = client.get(f"/v1/calls/{session['call_id']}", headers=auth).json()
    assert call["metadata"]["widget_session"] is True
    assert call["metadata"]["origin"] == "https://app.example.com"
    assert call["metadata"]["public_api_key_prefix"] == key["prefix"]
    ended = client.delete(
        f"/v1/public/tenants/{tenant}/widget/sessions/{session['session_id']}",
        headers={"X-API-Key": key["key"], "Origin": "https://app.example.com"},
    )
    assert ended.status_code == 204
    ended_call = client.get(f"/v1/calls/{session['call_id']}", headers=auth).json()
    assert ended_call["status"] == "cancelled"
    assert ended_call["end_reason"] == "user_hangup"


def test_invalid_token_and_wrong_tenant() -> None:
    tenant = str(uuid4())
    assert (
        client.get(
            "/v1/me", headers={"Authorization": "Bearer invalid", "X-Tenant-Id": tenant}
        ).status_code
        == 401
    )
    settings = get_settings()
    token = jwt.encode(
        {"sub": "u", "iss": settings.jwt_issuer, "aud": settings.jwt_audience, "tenants": []},
        settings.auth_secret,
        algorithm="HS256",
    )
    assert (
        client.get(
            "/v1/me", headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant}
        ).status_code
        == 403
    )


def test_knowledge_base_and_document_crud_is_tenant_scoped() -> None:
    store.knowledge_bases.clear()
    store.documents.clear()
    store.chunks.clear()
    tenant_a, tenant_b = str(uuid4()), str(uuid4())
    auth_a, auth_b = headers(tenant_a), headers(tenant_b)
    kb = client.post(
        "/v1/knowledge-bases",
        json={"name": "FAQ", "chunk_size": 400, "chunk_overlap": 50},
        headers=auth_a,
    )
    assert kb.status_code == 201
    kb_id = kb.json()["id"]
    assert client.get("/v1/knowledge-bases", headers=auth_b).json()["data"] == []
    assert (
        client.patch(
            f"/v1/knowledge-bases/{kb_id}", json={"name": "FAQ BR"}, headers=auth_a
        ).json()["name"]
        == "FAQ BR"
    )
    assert (
        client.post(
            f"/v1/knowledge-bases/{kb_id}/documents", json={"name": "Sem fonte"}, headers=auth_a
        ).status_code
        == 422
    )
    document = client.post(
        f"/v1/knowledge-bases/{kb_id}/documents",
        json={"name": "Atendimento", "text": "Prazo de entrega de dois dias."},
        headers=auth_a,
    )
    assert document.status_code == 202
    document_id = document.json()["id"]
    documents = client.get(f"/v1/knowledge-bases/{kb_id}/documents", headers=auth_a).json()["data"]
    assert documents[0]["status"] == "ready"
    assert documents[0]["chunk_count"] == 1
    query = client.post(
        f"/v1/knowledge-bases/{kb_id}/query",
        json={"query": "Prazo de entrega de dois dias.", "min_score": 0.99},
        headers=auth_a,
    )
    assert query.json()["data"][0]["content"] == "Prazo de entrega de dois dias."
    internal_query = client.post(
        "/internal/rag/query",
        json={
            "knowledge_base_id": kb_id,
            "query": "Prazo de entrega de dois dias.",
            "min_score": 0.99,
        },
        headers={"X-Internal-Token": get_settings().internal_api_token},
    )
    assert internal_query.json()["data"][0]["score"] > 0.99
    upload = client.post(
        f"/v1/knowledge-bases/{kb_id}/documents",
        files={"file": ("faq.html", b"<h1>Trocas</h1><p>Prazo de sete dias.</p>", "text/html")},
        headers=auth_a,
    )
    assert upload.status_code == 202
    uploaded_documents = client.get(
        f"/v1/knowledge-bases/{kb_id}/documents", headers=auth_a
    ).json()["data"]
    assert any(
        item["name"] == "faq.html" and item["status"] == "ready" for item in uploaded_documents
    )
    assert client.get(f"/v1/knowledge-bases/{kb_id}", headers=auth_b).status_code == 404
    assert (
        client.delete(
            f"/v1/knowledge-bases/{kb_id}/documents/{document_id}", headers=auth_a
        ).status_code
        == 204
    )
    assert client.delete(f"/v1/knowledge-bases/{kb_id}", headers=auth_a).status_code == 204


def test_whatsapp_connect_and_list_integrations() -> None:
    store.integrations.clear()
    store.secrets.clear()
    tenant = str(uuid4())
    auth = headers(tenant)
    agent = client.post("/v1/agents", json={"name": "WhatsApp Agent"}, headers=auth).json()

    connected = client.post(
        "/v1/integrations/whatsapp",
        json={
            "phone_number_id": "phone-123",
            "business_account_id": "waba-456",
            "access_token": "token-1234567890",
            "agent_id": agent["id"],
        },
        headers=auth,
    )
    assert connected.status_code == 201
    payload = connected.json()
    assert payload["provider"] == "whatsapp"
    assert payload["config"]["phone_number_id"] == "phone-123"
    assert "refresh_token_secret_id" not in payload

    listed = client.get("/v1/integrations", headers=auth)
    assert listed.status_code == 200
    items = listed.json()["data"]
    assert any(item["provider"] == "whatsapp" for item in items)


def test_whatsapp_webhook_verify_and_ingest_message() -> None:
    store.integrations.clear()
    store.secrets.clear()
    store.whatsapp_messages.clear()
    store.calls.clear()
    store.end_users.clear()
    tenant = str(uuid4())
    auth = headers(tenant)
    agent = client.post("/v1/agents", json={"name": "Webhook Agent"}, headers=auth).json()
    settings = get_settings()
    previous_verify = settings.whatsapp_verify_token
    previous_secret = settings.whatsapp_app_secret
    settings.whatsapp_verify_token = "verify-token"
    settings.whatsapp_app_secret = "meta-secret"
    try:
        client.post(
            "/v1/integrations/whatsapp",
            json={
                "phone_number_id": "phone-789",
                "business_account_id": "waba-789",
                "access_token": "token-abcdefghij",
                "agent_id": agent["id"],
            },
            headers=auth,
        )
        verify = client.get(
            "/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-token",
                "hub.challenge": "12345",
            },
        )
        assert verify.status_code == 200
        assert verify.text == "12345"

        body = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "phone-789"},
                                "messages": [
                                    {
                                        "id": "wamid-1",
                                        "from": "+5511999999999",
                                        "type": "text",
                                        "text": {"body": "Preciso falar com humano"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
        payload = json.dumps(body).encode()
        response = client.post(
            "/webhooks/whatsapp",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": meta_signature("meta-secret", payload),
            },
        )
        assert response.status_code == 200
        assert response.json() == {"received": True, "accepted": 1}
        assert len(store.whatsapp_messages) == 1
        assert len(store.calls) == 1
    finally:
        settings.whatsapp_verify_token = previous_verify
        settings.whatsapp_app_secret = previous_secret


def test_internal_whatsapp_tick_processes_queue_and_requests_handoff(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    store.integrations.clear()
    store.secrets.clear()
    store.whatsapp_messages.clear()
    store.calls.clear()
    store.call_turns.clear()
    store.call_events.clear()
    store.end_users.clear()
    event_bus.events.clear()
    tenant = str(uuid4())
    auth = headers(tenant)
    agent = client.post("/v1/agents", json={"name": "Async Agent"}, headers=auth).json()
    settings = get_settings()
    previous_secret = settings.whatsapp_app_secret
    settings.whatsapp_app_secret = "tick-secret"

    class FakeGateway:
        def __init__(self, settings: object, access_token: str, phone_number_id: str) -> None:
            self.access_token = access_token
            self.phone_number_id = phone_number_id

        async def download_media(self, media_id: str) -> bytes:
            return b"audio"

        async def send_text(self, recipient: str, text: str) -> str:
            assert recipient == "+5511888888888"
            assert "atendente humano" in text
            return "wamid-out-1"

        async def send_audio_bytes(self, recipient: str, audio: bytes, **kwargs: object) -> str:
            raise AssertionError("audio should not be sent in text mode")

    monkeypatch.setattr(api_routes, "WhatsAppGateway", FakeGateway)
    try:
        client.post(
            "/v1/integrations/whatsapp",
            json={
                "phone_number_id": "phone-tick",
                "business_account_id": "waba-tick",
                "access_token": "token-zxywvutsrq",
                "agent_id": agent["id"],
            },
            headers=auth,
        )
        body = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "phone-tick"},
                                "messages": [
                                    {
                                        "id": "wamid-in-1",
                                        "from": "+5511888888888",
                                        "type": "text",
                                        "text": {"body": "Quero falar com humano"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
        payload = json.dumps(body).encode()
        client.post(
            "/webhooks/whatsapp",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": meta_signature("tick-secret", payload),
            },
        )
        tick = client.post(
            "/internal/whatsapp/tick",
            headers={"X-Internal-Token": get_settings().internal_api_token},
        )
        assert tick.status_code == 200
        assert tick.json()["processed"] == 1
        assert tick.json()["handoffs"] == 1
        message = next(iter(store.whatsapp_messages.values()))
        assert message["status"] == "done"
        call = next(iter(store.calls.values()))
        assert call["metadata"]["human_handoff"] is True
        assert len(store.call_turns[call["id"]]) == 2
        assert any(event[2]["type"] == "operator.takeover_requested" for event in event_bus.events)
    finally:
        settings.whatsapp_app_secret = previous_secret


def test_internal_whatsapp_tick_executes_runtime_tool(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    store.integrations.clear()
    store.secrets.clear()
    store.whatsapp_messages.clear()
    store.calls.clear()
    store.call_turns.clear()
    store.call_events.clear()
    store.call_tool_calls.clear()
    store.end_users.clear()
    event_bus.events.clear()
    tenant = str(uuid4())
    auth = headers(tenant)
    agent = client.post("/v1/agents", json={"name": "Tool Agent"}, headers=auth).json()
    settings = get_settings()
    previous_secret = settings.whatsapp_app_secret
    settings.whatsapp_app_secret = "tool-secret"

    class FakeGateway:
        def __init__(self, settings: object, access_token: str, phone_number_id: str) -> None:
            self.access_token = access_token
            self.phone_number_id = phone_number_id

        async def download_media(self, media_id: str) -> bytes:
            return b"audio"

        async def send_text(self, recipient: str, text: str) -> str:
            assert recipient == "+5511777777777"
            assert text == "Tool executada."
            return "wamid-out-tool"

        async def send_audio_bytes(self, recipient: str, audio: bytes, **kwargs: object) -> str:
            raise AssertionError("audio should not be sent")

    async def fake_generate_reply(
        settings: object,
        runtime: dict[str, object] | None,
        user_text: str,
        inbound_type: str,
        execute_tool=None,
        transport=None,
    ) -> tuple[str, bool, list[dict[str, object]]]:
        assert user_text == "Consultar agenda"
        assert inbound_type == "text"
        assert runtime is not None
        assert execute_tool is not None
        tool = list(runtime.get("tools") or [])[0]
        result = await execute_tool(tool, {"date": "2026-08-26"})
        assert result["available"] == ["2026-08-26T10:00:00Z"]
        return "Tool executada.", False, []

    monkeypatch.setattr(api_routes, "WhatsAppGateway", FakeGateway)
    monkeypatch.setattr(api_routes, "generate_whatsapp_reply", fake_generate_reply)
    async def fake_execute_runtime_tool(
        repo: object,
        executor: object,
        cipher: object,
        native: object,
        tenant_id: UUID,
        call: dict[str, object],
        tool: dict[str, object],
        arguments: dict[str, object],
        *,
        session_variables: dict[str, object] | None = None,
        end_user: dict[str, object] | None = None,
    ) -> tuple[dict[str, object], dict[str, object]]:
        return {"available": ["2026-08-26T10:00:00Z"]}, {"latency_ms": 12}

    monkeypatch.setattr(api_routes, "_execute_runtime_tool", fake_execute_runtime_tool)
    try:
        client.post(
            "/v1/integrations/whatsapp",
            json={
                "phone_number_id": "phone-tool",
                "business_account_id": "waba-tool",
                "access_token": "token-tool-abcdefgh",
                "agent_id": agent["id"],
            },
            headers=auth,
        )
        tool = client.post(
            "/v1/tools",
            json={
                "name": "google_calendar_check",
                "description": "Consulta agenda",
                "type": "native",
                "native_kind": "google_calendar_check",
                "parameters_schema": {
                    "type": "object",
                    "properties": {"date": {"type": "string"}},
                    "required": ["date"],
                },
            },
            headers=auth,
        ).json()
        client.put(
            f"/v1/agents/{agent['id']}/draft/tools",
            json={"tool_ids": [tool["id"]]},
            headers=auth,
        )
        body = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "phone-tool"},
                                "messages": [
                                    {
                                        "id": "wamid-tool-1",
                                        "from": "+5511777777777",
                                        "type": "text",
                                        "text": {"body": "Consultar agenda"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
        payload = json.dumps(body).encode()
        client.post(
            "/webhooks/whatsapp",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": meta_signature("tool-secret", payload),
            },
        )
        tick = client.post(
            "/internal/whatsapp/tick",
            headers={"X-Internal-Token": get_settings().internal_api_token},
        )
        assert tick.status_code == 200
        assert tick.json()["processed"] == 1
        assert tick.json()["tool_runs"] == 1
        call_id = next(iter(store.calls.keys()))
        assert len(store.call_tool_calls[call_id]) == 1
        assert store.call_tool_calls[call_id][0]["name"] == "google_calendar_check"
        assert any(event[2]["type"] == "tool.called" for event in event_bus.events)
    finally:
        settings.whatsapp_app_secret = previous_secret


def test_internal_whatsapp_tick_processes_audio_and_sends_text_plus_audio(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    store.integrations.clear()
    store.secrets.clear()
    store.whatsapp_messages.clear()
    store.calls.clear()
    store.call_turns.clear()
    store.call_events.clear()
    store.call_tool_calls.clear()
    store.end_users.clear()
    event_bus.events.clear()
    tenant = str(uuid4())
    auth = headers(tenant)
    agent = client.post("/v1/agents", json={"name": "Audio Agent"}, headers=auth).json()
    client.patch(
        f"/v1/agents/{agent['id']}/draft",
        json={
            "behavior": {"whatsapp_reply_mode": "both"},
            "tts": {"voice_id": "voice-1", "model": "eleven_flash_v2_5"},
        },
        headers=auth,
    )
    settings = get_settings()
    previous_secret = settings.whatsapp_app_secret
    settings.whatsapp_app_secret = "audio-secret"
    sent: list[tuple[str, object]] = []

    class FakeGateway:
        def __init__(self, settings: object, access_token: str, phone_number_id: str) -> None:
            self.access_token = access_token
            self.phone_number_id = phone_number_id

        async def download_media(self, media_id: str) -> bytes:
            assert media_id == "media-1"
            return b"ogg-audio"

        async def send_text(self, recipient: str, text: str) -> str:
            sent.append(("text", {"recipient": recipient, "text": text}))
            return "wamid-text-audio"

        async def send_audio_bytes(self, recipient: str, audio: bytes, **kwargs: object) -> str:
            sent.append(
                (
                    "audio",
                    {
                        "recipient": recipient,
                        "audio": audio,
                        "filename": kwargs.get("filename"),
                        "content_type": kwargs.get("content_type"),
                    },
                )
            )
            return "wamid-audio-audio"

    async def fake_transcribe(
        settings: object,
        runtime: dict[str, object] | None,
        audio: bytes,
        transport=None,
    ) -> str:
        assert audio == b"ogg-audio"
        return "Transcricao do audio"

    async def fake_generate_reply(
        settings: object,
        runtime: dict[str, object] | None,
        user_text: str,
        inbound_type: str,
        execute_tool=None,
        transport=None,
    ) -> tuple[str, bool, list[dict[str, object]]]:
        assert user_text == "Transcricao do audio"
        assert inbound_type == "audio"
        return "Resposta com audio", False, []

    async def fake_synthesize(
        settings: object,
        runtime: dict[str, object] | None,
        text: str,
        voice_preview: object,
        transport=None,
    ) -> tuple[bytes, str, str]:
        assert text == "Resposta com audio"
        return (b"OGGDATA", "reply.ogg", "audio/ogg")

    monkeypatch.setattr(api_routes, "WhatsAppGateway", FakeGateway)
    monkeypatch.setattr(api_routes, "transcribe_whatsapp_audio", fake_transcribe)
    monkeypatch.setattr(api_routes, "generate_whatsapp_reply", fake_generate_reply)
    monkeypatch.setattr(api_routes, "synthesize_whatsapp_audio", fake_synthesize)
    try:
        client.post(
            "/v1/integrations/whatsapp",
            json={
                "phone_number_id": "phone-audio",
                "business_account_id": "waba-audio",
                "access_token": "token-audio-abcdefgh",
                "agent_id": agent["id"],
            },
            headers=auth,
        )
        body = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "phone-audio"},
                                "messages": [
                                    {
                                        "id": "wamid-audio-1",
                                        "from": "+5511666666666",
                                        "type": "audio",
                                        "audio": {"id": "media-1"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
        payload = json.dumps(body).encode()
        client.post(
            "/webhooks/whatsapp",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": meta_signature("audio-secret", payload),
            },
        )
        tick = client.post(
            "/internal/whatsapp/tick",
            headers={"X-Internal-Token": get_settings().internal_api_token},
        )
        assert tick.status_code == 200
        assert tick.json()["processed"] == 1
        assert [kind for kind, _ in sent] == ["text", "audio"]
        assert sent[0][1]["text"] == "Resposta com audio"  # type: ignore[index]
        assert sent[1][1]["filename"] == "reply.ogg"  # type: ignore[index]
        assert sent[1][1]["content_type"] == "audio/ogg"  # type: ignore[index]
        call = next(iter(store.calls.values()))
        turns = store.call_turns[call["id"]]
        assert turns[0]["text"] == "Transcricao do audio"
        assert turns[1]["text"] == "Resposta com audio"
    finally:
        settings.whatsapp_app_secret = previous_secret


def test_whatsapp_handoff_route_sends_operator_message(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    store.integrations.clear()
    store.secrets.clear()
    store.whatsapp_messages.clear()
    store.calls.clear()
    store.call_turns.clear()
    store.call_events.clear()
    store.end_users.clear()
    event_bus.events.clear()
    tenant = str(uuid4())
    auth = headers(tenant)
    operator_auth = headers(tenant, "operator")
    agent = client.post("/v1/agents", json={"name": "Handoff Agent"}, headers=auth).json()
    settings = get_settings()
    previous_secret = settings.whatsapp_app_secret
    settings.whatsapp_app_secret = "handoff-secret"

    class FakeGateway:
        def __init__(self, settings: object, access_token: str, phone_number_id: str) -> None:
            self.access_token = access_token
            self.phone_number_id = phone_number_id

        async def send_text(self, recipient: str, text: str) -> str:
            assert recipient == "+5511555555555"
            assert text == "Operador assumiu a conversa."
            return "wamid-handoff-out"

    monkeypatch.setattr(api_routes, "WhatsAppGateway", FakeGateway)
    try:
        client.post(
            "/v1/integrations/whatsapp",
            json={
                "phone_number_id": "phone-handoff",
                "business_account_id": "waba-handoff",
                "access_token": "token-handoff-abcdefgh",
                "agent_id": agent["id"],
            },
            headers=auth,
        )
        body = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "phone-handoff"},
                                "messages": [
                                    {
                                        "id": "wamid-handoff-1",
                                        "from": "+5511555555555",
                                        "type": "text",
                                        "text": {"body": "Preciso de ajuda"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
        payload = json.dumps(body).encode()
        client.post(
            "/webhooks/whatsapp",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": meta_signature("handoff-secret", payload),
            },
        )
        call_id = str(next(iter(store.calls.keys())))
        response = client.post(
            f"/v1/calls/{call_id}/whatsapp-handoff",
            json={"text": "Operador assumiu a conversa."},
            headers=operator_auth,
        )
        assert response.status_code == 200
        assert response.json()["provider_message_id"] == "wamid-handoff-out"
        call = next(iter(store.calls.values()))
        assert call["metadata"]["human_handoff"] is True
        assert store.call_turns[call["id"]][-1]["role"] == "operator"
        assert store.call_turns[call["id"]][-1]["text"] == "Operador assumiu a conversa."
        assert event_bus.events[-1][2]["type"] == "operator.message"
    finally:
        settings.whatsapp_app_secret = previous_secret


def test_whatsapp_handoff_route_accepts_string_secret_id(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    store.integrations.clear()
    store.secrets.clear()
    store.whatsapp_messages.clear()
    store.calls.clear()
    store.call_turns.clear()
    store.call_events.clear()
    store.end_users.clear()
    event_bus.events.clear()
    tenant = str(uuid4())
    auth = headers(tenant)
    operator_auth = headers(tenant, "operator")
    agent = client.post("/v1/agents", json={"name": "String Secret Agent"}, headers=auth).json()
    settings = get_settings()
    previous_secret = settings.whatsapp_app_secret
    settings.whatsapp_app_secret = "handoff-string-secret"

    class FakeGateway:
        def __init__(self, settings: object, access_token: str, phone_number_id: str) -> None:
            self.access_token = access_token
            self.phone_number_id = phone_number_id

        async def send_text(self, recipient: str, text: str) -> str:
            assert recipient == "+5511444444444"
            assert text == "Operador assumiu com secret string."
            return "wamid-handoff-string"

    original_get_integration = MemoryRepository.get_integration

    async def fake_get_integration(
        self: MemoryRepository, tenant_id: UUID, provider: str
    ) -> dict[str, object] | None:
        item = await original_get_integration(self, tenant_id, provider)
        if item and provider == "whatsapp" and item.get("refresh_token_secret_id"):
            altered = dict(item)
            altered["refresh_token_secret_id"] = str(item["refresh_token_secret_id"])
            return altered
        return item

    monkeypatch.setattr(api_routes, "WhatsAppGateway", FakeGateway)
    monkeypatch.setattr(MemoryRepository, "get_integration", fake_get_integration)
    try:
        client.post(
            "/v1/integrations/whatsapp",
            json={
                "phone_number_id": "phone-handoff-string",
                "business_account_id": "waba-handoff-string",
                "access_token": "token-handoff-string-abcdefgh",
                "agent_id": agent["id"],
            },
            headers=auth,
        )
        body = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "phone-handoff-string"},
                                "messages": [
                                    {
                                        "id": "wamid-handoff-string-1",
                                        "from": "+5511444444444",
                                        "type": "text",
                                        "text": {"body": "Preciso de ajuda"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
        payload = json.dumps(body).encode()
        client.post(
            "/webhooks/whatsapp",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": meta_signature("handoff-string-secret", payload),
            },
        )
        call_id = str(next(iter(store.calls.keys())))
        response = client.post(
            f"/v1/calls/{call_id}/whatsapp-handoff",
            json={"text": "Operador assumiu com secret string."},
            headers=operator_auth,
        )
        assert response.status_code == 200
        assert response.json()["provider_message_id"] == "wamid-handoff-string"
    finally:
        settings.whatsapp_app_secret = previous_secret


def test_simulation_endpoints_return_report_and_yaml() -> None:
    store.simulations.clear()
    tenant = str(uuid4())
    auth = headers(tenant)
    agent = client.post("/v1/agents", json={"name": "Simulator Agent"}, headers=auth).json()
    created = client.post(
        "/v1/simulations",
        json={
            "agent_id": agent["id"],
            "persona": "Paciente com dúvida recorrente sobre agendamento e retorno.",
            "objective": "Validar se o agente conduz a conversa com clareza.",
            "conversation_count": 20,
        },
        headers=auth,
    )
    assert created.status_code == 201
    simulation = created.json()
    assert simulation["status"] == "completed"
    assert simulation["report"]["conversation_count"] == 20
    fetched = client.get(f"/v1/simulations/{simulation['id']}", headers=auth)
    assert fetched.status_code == 200
    assert fetched.json()["report"]["pass_rate"] > 0
    yaml_response = client.get(f"/v1/simulations/{simulation['id']}/yaml", headers=auth)
    assert yaml_response.status_code == 200
    assert "channel: whatsapp" in yaml_response.text
