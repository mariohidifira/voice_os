import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from uuid import UUID, uuid4

import jwt
from fastapi.testclient import TestClient
from voiceos_api.billing import stripe_signature_valid
from voiceos_api.config import get_settings
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
    timestamp = str(int(time.time()))
    secret = "whsec_test"
    digest = hmac.new(
        secret.encode(), timestamp.encode() + b"." + payload, hashlib.sha256
    ).hexdigest()
    assert stripe_signature_valid(payload, f"t={timestamp},v1={digest}", secret)
    assert not stripe_signature_valid(payload, f"t={timestamp},v1=invalid", secret)


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
