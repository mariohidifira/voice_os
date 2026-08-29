import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from voiceos_api.billing import (
    DevStripeGateway,
    StripeHTTPGateway,
    get_stripe_gateway,
    stripe_signature_valid,
)
from voiceos_api.config import Settings, get_settings
from voiceos_api.main import app
from voiceos_api.repository import MemoryRepository, get_repository
from voiceos_api.store import store

app.dependency_overrides[get_repository] = lambda: MemoryRepository(store)
client = TestClient(app)


def auth(tenant_id: UUID, role: str = "owner") -> dict[str, str]:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": "billing-test",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "tenants": [{"id": str(tenant_id), "role": role}],
        },
        settings.auth_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant_id)}


def reset(tenant_id: UUID) -> None:
    store.tenants.clear()
    store.agents.clear()
    store.agent_versions.clear()
    store.subscriptions.clear()
    store.usage_records.clear()
    store.invoices.clear()
    store.phone_numbers.clear()
    store.billing_usage_alerts.clear()
    store.tenants[tenant_id] = {
        "id": tenant_id,
        "status": "trial",
        "settings": {},
        "created_at": datetime.now(UTC),
    }


def test_billing_plan_usage_checkout_portal_and_limits() -> None:
    tenant = uuid4()
    reset(tenant)
    headers = auth(tenant)
    plan = client.get("/v1/billing/plan", headers=headers)
    assert plan.status_code == 200
    assert plan.json()["code"] == "trial"
    first = client.post("/v1/agents", json={"name": "Trial agent"}, headers=headers)
    assert first.status_code == 201
    blocked = client.post("/v1/agents", json={"name": "Extra agent"}, headers=headers)
    assert blocked.status_code == 402
    assert blocked.json()["error"]["code"] == "plan_limit"
    call_id = uuid4()
    store.usage_records[call_id] = {
        "id": uuid4(),
        "tenant_id": tenant,
        "call_id": call_id,
        "period": datetime.now(UTC).date().replace(day=1),
        "billable_seconds": 121,
        "channel": "web",
        "cost_usd": 0.12,
    }
    usage = client.get("/v1/billing/usage", headers=headers).json()
    assert usage["minutes"] == 3
    assert usage["included_minutes"] == 60
    checkout = client.post("/v1/billing/checkout", json={"plan_code": "pro"}, headers=headers)
    assert checkout.status_code == 200
    assert "plan=pro" in checkout.json()["url"]
    assert client.post("/v1/billing/portal", headers=headers).status_code == 409


def test_stripe_webhook_updates_subscription_invoice_and_tenant() -> None:
    tenant = uuid4()
    reset(tenant)
    checkout = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": "cus_test",
                "subscription": "sub_test",
                "metadata": {"tenant_id": str(tenant), "plan_code": "pro"},
            }
        },
    }
    assert client.post("/webhooks/stripe", content=json.dumps(checkout)).status_code == 200
    assert store.tenants[tenant]["stripe_customer_id"] == "cus_test"
    assert client.get("/v1/billing/plan", headers=auth(tenant)).json()["code"] == "pro"
    portal = client.post("/v1/billing/portal", headers=auth(tenant))
    assert portal.status_code == 200 and "cus_test" in portal.json()["url"]
    failed = {
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "id": "in_test",
                "amount_due": 89700,
                "metadata": {"tenant_id": str(tenant), "plan_code": "pro"},
            }
        },
    }
    assert client.post("/webhooks/stripe", content=json.dumps(failed)).status_code == 200
    assert store.tenants[tenant]["status"] == "past_due"
    invoices = client.get("/v1/billing/invoices", headers=auth(tenant)).json()["data"]
    assert invoices[0]["stripe_invoice_id"] == "in_test"


def test_stripe_signature_verification() -> None:
    payload = b'{"id":"evt_test"}'
    timestamp = int(time.time())
    secret = "whsec_test"
    timestamp_text = str(timestamp)
    digest = hmac.new(
        secret.encode(), timestamp_text.encode() + b"." + payload, hashlib.sha256
    ).hexdigest()
    assert stripe_signature_valid(payload, f"t={timestamp_text},v1={digest}", secret)
    assert not stripe_signature_valid(payload, f"t={timestamp_text},v1=invalid", secret)
    assert not stripe_signature_valid(payload, f"t={timestamp - 301},v1={digest}", secret)


def test_dev_stripe_gateway_contract() -> None:
    import asyncio

    async def exercise() -> None:
        gateway = DevStripeGateway("http://localhost:3000")
        plan = {"code": "pro"}
        checkout = await gateway.checkout(None, plan, "tenant-12345678")
        assert checkout["session_id"] == "cs_test_tenant-1_pro"
        assert "plan=pro" in checkout["url"]
        assert (await gateway.portal("cus_test"))["url"].endswith("customer=cus_test")
        assert (await gateway.report_usage("si_test", 4, "usage-12345678")) == "ur_test_si_test_4_12345678"
        assert await gateway.set_quantity("si_test", 2) is None

    asyncio.run(exercise())


def test_dev_gateway_selected_without_stripe_secret() -> None:
    assert isinstance(get_stripe_gateway(), DevStripeGateway)


@pytest.mark.asyncio
async def test_stripe_http_gateway_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    from voiceos_api import billing

    class Response:
        def __init__(self, payload: dict[str, str]) -> None:
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return self.payload

    class Client:
        def __init__(self, **_: object) -> None:
            self.paths: list[str] = []

        async def __aenter__(self) -> "Client":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(self, path: str, **_: object) -> Response:
            self.paths.append(path)
            if path.endswith("checkout/sessions"):
                return Response({"url": "https://checkout.test", "id": "cs_live"})
            if path.endswith("billing_portal/sessions"):
                return Response({"url": "https://portal.test"})
            if path.endswith("usage_records"):
                return Response({"id": "ur_live"})
            return Response({"id": "updated"})

    monkeypatch.setattr(billing.httpx, "AsyncClient", Client)
    gateway = StripeHTTPGateway(Settings(stripe_secret_key="sk_test"))
    checkout = await gateway.checkout("cus_1", {"code": "pro", "stripe_price_id": "price_1"}, "tenant-1")
    assert checkout == {"url": "https://checkout.test", "session_id": "cs_live"}
    assert await gateway.portal("cus_1") == {"url": "https://portal.test"}
    assert await gateway.report_usage("si_1", 3, "idem-1") == "ur_live"
    assert await gateway.set_quantity("si_1", 4) is None


def test_hourly_meter_reports_only_overage_and_marks_records() -> None:
    tenant = uuid4()
    reset(tenant)
    subscription_id = uuid4()
    store.subscriptions[subscription_id] = {
        "id": subscription_id,
        "tenant_id": tenant,
        "plan_code": "starter",
        "status": "active",
        "stripe_subscription_id": "sub_meter",
        "stripe_overage_item_id": "si_overage",
        "stripe_phone_item_id": "si_phone",
    }
    record_id = uuid4()
    call_id = uuid4()
    store.usage_records[call_id] = {
        "id": record_id,
        "tenant_id": tenant,
        "call_id": call_id,
        "period": datetime.now(UTC).date().replace(day=1),
        "billable_seconds": 501 * 60,
        "channel": "phone_outbound",
        "cost_usd": 1,
    }
    number_id = uuid4()
    store.phone_numbers[number_id] = {
        "id": number_id,
        "tenant_id": tenant,
        "status": "active",
        "created_at": datetime.now(UTC),
    }
    response = client.post(
        "/internal/billing/tick",
        headers={"X-Internal-Token": get_settings().internal_api_token},
    )
    assert response.status_code == 200
    assert response.json() == {"tenants": 1, "records": 1, "phones": 1, "alerts": 2, "failed": 0}
    assert str(store.usage_records[call_id]["stripe_usage_record_id"]).startswith("ur_test_")
    repeated = client.post(
        "/internal/billing/tick",
        headers={"X-Internal-Token": get_settings().internal_api_token},
    )
    assert repeated.json()["alerts"] == 0
