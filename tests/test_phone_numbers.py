from uuid import UUID, uuid4

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient
from voiceos_api.config import get_settings
from voiceos_api.idempotency import MemoryIdempotencyStore, get_idempotency_store
from voiceos_api.main import app
from voiceos_api.repository import MemoryRepository, get_repository
from voiceos_api.store import store
from voiceos_api.telephony import (
    DevNumberProvider,
    DevSipDispatch,
    DevSipOutbound,
    Telephony,
    TelephonyProviderError,
    TwilioNumberProvider,
    get_telephony,
)


class TrackingDispatch(DevSipDispatch):
    def __init__(self) -> None:
        self.created: list[tuple[UUID, UUID, str, str]] = []
        self.deleted: list[str] = []
        self.fail_create = False

    async def create(self, tenant_id: UUID, agent_id: UUID, e164: str) -> str:
        if self.fail_create:
            raise TelephonyProviderError("dispatch unavailable")
        rule_id = await super().create(tenant_id, agent_id, e164)
        self.created.append((tenant_id, agent_id, e164, rule_id))
        return rule_id

    async def delete(self, rule_id: str) -> None:
        self.deleted.append(rule_id)


class TrackingOutbound(DevSipOutbound):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self.fail = False

    async def dial(self, room_name: str, to: str, from_number: str) -> str:
        self.calls.append((room_name, to, from_number))
        if self.fail:
            raise TelephonyProviderError("outbound unavailable")
        return await super().dial(room_name, to, from_number)


numbers = DevNumberProvider()
dispatch = TrackingDispatch()
outbound = TrackingOutbound()
idempotency = MemoryIdempotencyStore()
app.dependency_overrides[get_repository] = lambda: MemoryRepository(store)
app.dependency_overrides[get_telephony] = lambda: Telephony(numbers, dispatch, outbound)
app.dependency_overrides[get_idempotency_store] = lambda: idempotency
client = TestClient(app)


def auth(tenant_id: UUID, role: str = "owner") -> dict[str, str]:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": "phone-test-user",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "tenants": [{"id": str(tenant_id), "role": role}],
        },
        settings.auth_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant_id)}


def reset() -> None:
    store.phone_numbers.clear()
    store.agents.clear()
    store.agent_versions.clear()
    numbers.purchased.clear()
    dispatch.created.clear()
    dispatch.deleted.clear()
    dispatch.fail_create = False
    outbound.calls.clear()
    outbound.fail = False
    idempotency.values.clear()
    store.calls.clear()
    store.end_users.clear()


def test_phone_number_search_purchase_assignment_release_and_isolation() -> None:
    reset()
    tenant_a, tenant_b = uuid4(), uuid4()
    agent = store.create_agent(tenant_a, "Telefone")
    agent["status"] = "active"
    available = client.get(
        "/v1/phone-numbers/available?country=BR&area_code=11", headers=auth(tenant_a)
    )
    assert available.status_code == 200
    e164 = available.json()["data"][0]["e164"]
    assert client.get("/v1/phone-numbers", headers=auth(tenant_a, "viewer")).status_code == 403

    purchased = client.post("/v1/phone-numbers", json={"e164": e164}, headers=auth(tenant_a))
    assert purchased.status_code == 201
    number_id = purchased.json()["id"]
    assert purchased.json()["agent_id"] is None
    assert client.get("/v1/phone-numbers", headers=auth(tenant_b)).json()["data"] == []

    assigned = client.patch(
        f"/v1/phone-numbers/{number_id}",
        json={"agent_id": str(agent["id"])},
        headers=auth(tenant_a),
    )
    assert assigned.status_code == 200
    assert assigned.json()["agent_id"] == str(agent["id"])
    assert assigned.json()["livekit_dispatch_rule_id"].startswith("SDR_DEV_")
    assert dispatch.created[0][0:3] == (tenant_a, agent["id"], e164)

    released = client.delete(f"/v1/phone-numbers/{number_id}", headers=auth(tenant_a))
    assert released.status_code == 204
    stored = client.get("/v1/phone-numbers", headers=auth(tenant_a)).json()["data"][0]
    assert stored["status"] == "released"
    assert stored["agent_id"] is None
    assert dispatch.deleted == [assigned.json()["livekit_dispatch_rule_id"]]
    assert e164 not in numbers.purchased


def test_phone_purchase_compensates_when_sip_dispatch_fails() -> None:
    reset()
    tenant = uuid4()
    agent = store.create_agent(tenant, "Falha SIP")
    agent["status"] = "active"
    e164 = "+551140009999"
    dispatch.fail_create = True
    response = client.post(
        "/v1/phone-numbers",
        json={"e164": e164, "agent_id": str(agent["id"])},
        headers=auth(tenant),
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "telephony_provider_error"
    assert e164 not in numbers.purchased
    assert store.phone_numbers == {}


@pytest.mark.asyncio
async def test_twilio_number_provider_uses_official_inventory_and_purchase_contracts() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "available_phone_numbers": [
                        {
                            "phone_number": "+551140001234",
                            "friendly_name": "+55 11 4000-1234",
                            "capabilities": {"voice": True, "SMS": True},
                        }
                    ]
                },
            )
        if request.method == "POST":
            return httpx.Response(
                201,
                json={
                    "sid": "PN123",
                    "phone_number": "+551140001234",
                    "capabilities": {"voice": True, "sms": True},
                },
            )
        return httpx.Response(204)

    provider = TwilioNumberProvider("AC123", "secret", httpx.MockTransport(handler))
    available = await provider.available("BR", "11")
    purchased = await provider.purchase(available[0]["e164"])
    await provider.release(purchased.provider_sid)

    assert available[0]["capabilities"] == {"voice": True, "sms": True}
    assert purchased.provider_sid == "PN123"
    assert [request.method for request in requests] == ["GET", "POST", "DELETE"]
    assert "Contains=%2B5511%2A" in str(requests[0].url)
    assert dict(httpx.QueryParams(requests[1].content.decode()))["PhoneNumber"] == "+551140001234"


def test_outbound_call_is_tenant_scoped_and_idempotent() -> None:
    reset()
    tenant = uuid4()
    agent = store.create_agent(tenant, "Outbound")
    agent["status"] = "active"
    purchased = client.post(
        "/v1/phone-numbers",
        json={"e164": "+551140008888", "agent_id": str(agent["id"])},
        headers=auth(tenant),
    )
    assert purchased.status_code == 201
    headers = {**auth(tenant), "Idempotency-Key": "campaign-contact-1"}
    payload = {
        "agent_id": str(agent["id"]),
        "to": "+5511999990001",
        "variables": {"invoice": "42"},
        "end_user": {"name": "Cliente"},
    }

    first = client.post("/v1/calls/outbound", json=payload, headers=headers)
    replay = client.post("/v1/calls/outbound", json=payload, headers=headers)

    assert first.status_code == replay.status_code == 202
    assert first.json() == replay.json()
    assert outbound.calls == []
    call = store.calls[UUID(first.json()["call_id"])]
    assert call["channel"] == "phone_outbound"
    assert call["status"] == "queued"
    assert call["from_number"] == "+551140008888"
    assert call["to_number"] == "+5511999990001"
    assert call["livekit_room"].startswith("voiceos_")
    takeover = client.post(
        f"/v1/calls/{call['id']}/takeover",
        json={"operator_extension": "+5511988887777"},
        headers=auth(tenant, "operator"),
    )
    assert takeover.status_code == 200
    assert takeover.json()["mode"] == "phone"
    assert outbound.calls[-1] == (
        call["livekit_room"],
        "+5511988887777",
        "+551140008888",
    )

    conflict = client.post(
        "/v1/calls/outbound",
        json={**payload, "to": "+5511999990099"},
        headers=headers,
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_key_reused"
    assert len(outbound.calls) == 1


def test_outbound_requires_sip_dialer_configuration() -> None:
    reset()
    tenant = uuid4()
    agent = store.create_agent(tenant, "Outbound failure")
    agent["status"] = "active"
    assert (
        client.post(
            "/v1/phone-numbers",
            json={"e164": "+551140007777", "agent_id": str(agent["id"])},
            headers=auth(tenant),
        ).status_code
        == 201
    )
    app.dependency_overrides[get_telephony] = lambda: Telephony(numbers, dispatch)
    headers = {**auth(tenant), "Idempotency-Key": "missing-sip"}
    payload = {"agent_id": str(agent["id"]), "to": "+5511999990002"}
    try:
        response = client.post("/v1/calls/outbound", json=payload, headers=headers)
    finally:
        app.dependency_overrides[get_telephony] = lambda: Telephony(numbers, dispatch, outbound)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "sip_not_configured"
    assert store.calls == {}
