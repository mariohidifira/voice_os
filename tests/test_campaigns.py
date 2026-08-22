from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from fastapi.testclient import TestClient
from voiceos_api.campaigns import dialing_allowed, retry_at, select_dispatchable
from voiceos_api.config import get_settings
from voiceos_api.idempotency import MemoryIdempotencyStore, get_idempotency_store
from voiceos_api.livekit_sessions import get_livekit_sessions
from voiceos_api.main import app
from voiceos_api.repository import MemoryRepository, get_repository
from voiceos_api.store import store
from voiceos_api.telephony import (
    DevNumberProvider,
    DevSipDispatch,
    DevSipOutbound,
    Telephony,
    get_telephony,
)

app.dependency_overrides[get_repository] = lambda: MemoryRepository(store)
idempotency = MemoryIdempotencyStore()
app.dependency_overrides[get_idempotency_store] = lambda: idempotency


class FakeRtc:
    async def provision(self, **kwargs: object) -> dict[str, str]:
        return {"room_name": f"voiceos_{kwargs['call_id']}", "token": "test"}

    def operator_token(self, room_name: str, operator_id: str) -> str:
        return f"operator-token:{room_name}:{operator_id}"


app.dependency_overrides[get_livekit_sessions] = FakeRtc
app.dependency_overrides[get_telephony] = lambda: Telephony(
    DevNumberProvider(), DevSipDispatch(), DevSipOutbound()
)
client = TestClient(app)


def auth(tenant_id: UUID) -> dict[str, str]:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": "campaign-test",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "tenants": [{"id": str(tenant_id), "role": "owner"}],
        },
        settings.auth_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant_id)}


def reset() -> None:
    store.campaigns.clear()
    store.campaign_contacts.clear()
    store.do_not_call.clear()
    store.agents.clear()
    store.agent_versions.clear()
    idempotency.values.clear()


def test_campaign_lifecycle_contacts_and_tenant_isolation() -> None:
    reset()
    tenant, other = uuid4(), uuid4()
    agent = store.create_agent(tenant, "Campaign agent")
    payload = {
        "agent_id": str(agent["id"]),
        "name": "August",
        "schedule": {
            "timezone": "America/Sao_Paulo",
            "days": [0, 1, 2, 3, 4],
            "window": {"start": "09:00", "end": "18:00"},
            "max_concurrency": 3,
        },
    }
    created = client.post("/v1/campaigns", json=payload, headers=auth(tenant))
    assert created.status_code == 201
    campaign_id = created.json()["id"]
    assert client.get(f"/v1/campaigns/{campaign_id}", headers=auth(other)).status_code == 404
    assert (
        client.post(f"/v1/campaigns/{campaign_id}/start", headers=auth(tenant)).status_code == 409
    )

    contacts = {
        "contacts": [{"phone": "+5511999990001", "name": "Ana", "variables": {"segment": "a"}}]
    }
    assert (
        client.post(
            f"/v1/campaigns/{campaign_id}/contacts", json=contacts, headers=auth(tenant)
        ).status_code
        == 201
    )
    assert (
        client.post(f"/v1/campaigns/{campaign_id}/start", headers=auth(tenant)).json()["status"]
        == "running"
    )
    assert (
        client.post(f"/v1/campaigns/{campaign_id}/pause", headers=auth(tenant)).json()["status"]
        == "paused"
    )
    assert (
        client.post(f"/v1/campaigns/{campaign_id}/resume", headers=auth(tenant)).json()["status"]
        == "running"
    )
    assert (
        client.post(f"/v1/campaigns/{campaign_id}/cancel", headers=auth(tenant)).json()["status"]
        == "cancelled"
    )


def test_do_not_call_filters_import_and_compliance_window() -> None:
    reset()
    tenant = uuid4()
    agent = store.create_agent(tenant, "DNC agent")
    headers = auth(tenant)
    assert (
        client.post(
            "/v1/do-not-call",
            json={"phone": "+5511999990002", "reason": "opt-out"},
            headers=headers,
        ).status_code
        == 201
    )
    campaign = client.post(
        "/v1/campaigns",
        json={"agent_id": str(agent["id"]), "name": "DNC", "schedule": {}},
        headers=headers,
    ).json()
    response = client.post(
        f"/v1/campaigns/{campaign['id']}/contacts",
        json={"contacts": [{"phone": "+5511999990002"}]},
        headers=headers,
    )
    assert response.status_code == 422
    schedule = {
        "timezone": "America/Sao_Paulo",
        "days": [0],
        "window": {"start": "06:00", "end": "22:00"},
    }
    assert dialing_allowed(schedule, now=datetime(2026, 8, 24, 16, 0, tzinfo=UTC))
    assert not dialing_allowed(schedule, now=datetime(2026, 8, 24, 23, 30, tzinfo=UTC))


def test_campaign_create_is_idempotent_and_contacts_accept_csv() -> None:
    reset()
    tenant = uuid4()
    agent = store.create_agent(tenant, "CSV agent")
    headers = {**auth(tenant), "Idempotency-Key": "campaign-csv-1"}
    payload = {"agent_id": str(agent["id"]), "name": "CSV", "schedule": {}}
    first = client.post("/v1/campaigns", json=payload, headers=headers)
    replay = client.post("/v1/campaigns", json=payload, headers=headers)
    assert first.status_code == replay.status_code == 201
    assert first.json()["id"] == replay.json()["id"]
    csv_body = "phone,name,var.segment\n+5511999990003,Bia,premium\n"
    imported = client.post(
        f"/v1/campaigns/{first.json()['id']}/contacts",
        files={"file": ("contacts.csv", csv_body, "text/csv")},
        headers=auth(tenant),
    )
    assert imported.status_code == 201
    assert imported.json()[0]["variables"] == {"segment": "premium"}


def test_runner_selection_honors_concurrency_due_dnc_and_retry_policy() -> None:
    now = datetime(2026, 8, 24, 16, 0, tzinfo=UTC)
    campaign_id = uuid4()
    campaign = {
        "id": campaign_id,
        "status": "running",
        "schedule": {
            "timezone": "America/Sao_Paulo",
            "days": [0],
            "window": {"start": "08:00", "end": "20:00"},
            "max_concurrency": 2,
        },
    }
    contacts = [
        {
            "id": uuid4(),
            "phone": "+551100000001",
            "status": "pending",
            "next_attempt_at": None,
            "variables": {},
        },
        {
            "id": uuid4(),
            "phone": "+551100000002",
            "status": "retry",
            "next_attempt_at": now,
            "variables": {},
        },
        {
            "id": uuid4(),
            "phone": "+551100000003",
            "status": "pending",
            "next_attempt_at": None,
            "variables": {},
        },
    ]
    calls = [{"campaign_id": campaign_id, "status": "ringing"}]
    selected = select_dispatchable(
        campaign, contacts, calls, {"+551100000002"}, now=now, plan_max_concurrency=5
    )
    assert [item["phone"] for item in selected] == ["+551100000001"]
    assert retry_at("busy", 1, {"max_attempts": 3, "delays_s": [60]}, now=now) == now + timedelta(
        seconds=60
    )
    assert retry_at("completed", 1, {}, now=now) is None
    assert retry_at("failed", 3, {"max_attempts": 3}, now=now) is None


def test_periodic_tick_dispatches_and_call_result_reconciles_contact() -> None:
    reset()
    tenant = uuid4()
    agent = store.create_agent(tenant, "Runner agent")
    agent["status"] = "active"
    agent["current_version_id"] = agent["draft_version_id"]
    number_id = uuid4()
    store.phone_numbers[number_id] = {
        "id": number_id,
        "tenant_id": tenant,
        "agent_id": agent["id"],
        "e164": "+551130000000",
        "status": "active",
        "capabilities": {"voice": True},
        "created_at": datetime.now(UTC),
    }
    headers = auth(tenant)
    campaign = client.post(
        "/v1/campaigns",
        json={
            "agent_id": str(agent["id"]),
            "name": "Runner",
            "schedule": {
                "timezone": "America/Sao_Paulo",
                "days": [0, 1, 2, 3, 4, 5, 6],
                "window": {"start": "08:00", "end": "20:00"},
                "retry_policy": {"max_attempts": 2, "delays_s": [60]},
            },
        },
        headers=headers,
    ).json()
    contact = client.post(
        f"/v1/campaigns/{campaign['id']}/contacts",
        json={"contacts": [{"phone": "+5511999991234", "name": "Ana"}]},
        headers=headers,
    ).json()[0]
    assert client.post(f"/v1/campaigns/{campaign['id']}/start", headers=headers).status_code == 200
    internal_headers = {"X-Internal-Token": get_settings().internal_api_token}
    response = client.post("/internal/campaigns/tick", headers=internal_headers)
    assert response.status_code == 200
    assert response.json()["dispatched"] == 1
    stored = store.campaign_contacts[UUID(contact["id"])]
    assert stored["status"] == "calling"
    call_id = stored["last_call_id"]
    assert (
        client.patch(
            f"/internal/calls/{call_id}", json={"status": "busy"}, headers=internal_headers
        ).status_code
        == 200
    )
    assert stored["status"] == "retry"
    assert stored["next_attempt_at"] is not None
    stored["next_attempt_at"] = datetime.now(UTC)
    assert client.post("/internal/campaigns/tick", headers=internal_headers).json()["dispatched"] == 1
    second_call_id = stored["last_call_id"]
    assert second_call_id != call_id
    assert client.patch(f"/internal/calls/{second_call_id}", json={"status": "completed"}, headers=internal_headers).status_code == 200
    assert stored["status"] == "done"
    finished = store.campaigns[UUID(campaign["id"])]
    assert finished["status"] == "completed"
    assert finished["stats"] == {"total": 1, "done": 1, "failed": 0, "remaining": 0}
