import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient
from voiceos_api.config import get_settings
from voiceos_api.main import app
from voiceos_api.outgoing_webhooks import OutgoingWebhookSender, delivery_result
from voiceos_api.repository import MemoryRepository, get_repository
from voiceos_api.routes import _postprocess_call
from voiceos_api.storage import get_export_storage, get_retention_storage
from voiceos_api.store import MemoryStore, store

app.dependency_overrides[get_repository] = lambda: MemoryRepository(store)


class FakeExportStorage:
    uploads: dict[str, bytes] = {}

    async def upload(self, key: str, body: bytes, content_type: str = "text/csv") -> None:
        self.uploads[key] = body

    async def download_url(self, key: str, expires_s: int = 900) -> str:
        return f"https://download.test/{key}"


class FakeRetentionStorage:
    deleted: tuple[list[str], list[str]] = ([], [])

    async def delete(self, recording_keys: list[str], document_keys: list[str]) -> None:
        self.deleted = (recording_keys, document_keys)


export_storage = FakeExportStorage()
retention_storage = FakeRetentionStorage()
app.dependency_overrides[get_export_storage] = lambda: export_storage
app.dependency_overrides[get_retention_storage] = lambda: retention_storage
client = TestClient(app)


def auth(tenant_id: UUID, *, platform_admin: bool = False) -> dict[str, str]:
    settings = get_settings()
    token = jwt.encode(
        {"sub": "phase3-test", "iss": settings.jwt_issuer, "aud": settings.jwt_audience, "tenants": [{"id": str(tenant_id), "role": "owner"}], "is_platform_admin": platform_admin},
        settings.auth_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant_id)}


def reset() -> None:
    store.tenants.clear()
    store.end_users.clear()
    store.calls.clear()
    store.call_qa.clear()
    store.webhooks.clear()
    store.webhook_deliveries.clear()
    store.secrets.clear()
    store.exports.clear()
    export_storage.uploads.clear()


def test_end_users_exports_and_lgpd_anonymization() -> None:
    reset()
    tenant = uuid4()
    repo = MemoryRepository(store)
    end_user = __import__("asyncio").run(repo.upsert_end_user(tenant, {"external_id": "customer-1", "email": "person@example.com", "name": "Pessoa"}))
    call = __import__("asyncio").run(repo.create_call(tenant, uuid4(), {}, {}, end_user_id=end_user["id"]))
    call["turns"] = [{"text": "personal data"}]
    headers = auth(tenant)
    assert client.get("/v1/end-users?q=customer", headers=headers).json()["data"][0]["calls_count"] == 1
    assert client.patch(f"/v1/end-users/{end_user['id']}", json={"name": "Novo nome"}, headers=headers).json()["name"] == "Novo nome"
    export = client.post("/v1/exports", json={"type": "end_user", "filters": {"id": str(end_user["id"])}}, headers=headers)
    assert export.status_code == 202
    export_id = export.json()["id"]
    assert client.get(f"/v1/exports/{export_id}", headers=headers).json()["status"] == "pending"
    completed = client.post("/internal/exports/tick", headers={"X-Internal-Token": get_settings().internal_api_token})
    assert completed.json() == {"claimed": 1, "ready": 1, "failed": 0}
    exported = client.get(f"/v1/exports/{export_id}", headers=headers).json()
    assert exported["status"] == "ready" and exported["download_url"].startswith("https://download.test/")
    assert any(b"external_id" in content for content in export_storage.uploads.values())
    assert client.delete(f"/v1/end-users/{end_user['id']}", headers=headers).status_code == 204
    assert store.calls[call["id"]]["end_user_id"] is None
    assert store.calls[call["id"]]["turns"][0]["text"] == "[deleted]"


def test_webhook_crud_queues_matching_event_and_manual_retry() -> None:
    reset()
    tenant = uuid4()
    headers = auth(tenant)
    created = client.post("/v1/webhooks", json={"url": "https://example.test/hook", "events": ["call.ended"]}, headers=headers)
    assert created.status_code == 201
    body = created.json()
    assert body["secret"].startswith("whsec_")
    repo = MemoryRepository(store)
    assert __import__("asyncio").run(repo.queue_webhook_event(tenant, "call.started", {"call": {}})) == 0
    assert __import__("asyncio").run(repo.queue_webhook_event(tenant, "call.ended", {"call": {"id": "1"}})) == 1
    deliveries = client.get(f"/v1/webhooks/{body['id']}/deliveries", headers=headers).json()["data"]
    assert len(deliveries) == 1 and deliveries[0]["status"] == "pending"
    delivery_id = deliveries[0]["id"]
    store.webhook_deliveries[UUID(delivery_id)]["status"] = "failed"
    retried = client.post(f"/v1/webhooks/{body['id']}/deliveries/{delivery_id}/retry", headers=headers)
    assert retried.json() == {"queued": True}


def test_retention_tick_removes_expired_objects_and_anonymizes_transcript() -> None:
    reset()
    tenant = uuid4()
    call_id = uuid4()
    document_id = uuid4()
    old = datetime.now(UTC) - timedelta(days=40)
    store.tenants[tenant] = {"id": tenant, "settings": {"retention_days": 30, "anonymize_transcripts": True}}
    store.calls[call_id] = {"id": call_id, "tenant_id": tenant, "started_at": old}
    store.call_turns[call_id] = [{"text": "personal"}]
    store.call_recordings[call_id] = {"s3_key": "recordings/old.ogg", "expires_at": old}
    store.documents[document_id] = {"id": document_id, "tenant_id": tenant, "s3_key": "documents/old.pdf", "deleted_at": old}
    response = client.post("/internal/retention/tick", headers={"X-Internal-Token": get_settings().internal_api_token})
    assert response.json() == {"recordings_deleted": 1, "documents_deleted": 1, "turns_anonymized": 1}
    assert store.call_turns[call_id][0]["text"] == "[retained-anonymized]"
    assert retention_storage.deleted == (["recordings/old.ogg"], ["documents/old.pdf"])


def test_analytics_and_manual_call_qa() -> None:
    reset()
    tenant = uuid4()
    repo = MemoryRepository(store)
    call = __import__("asyncio").run(repo.create_call(tenant, uuid4(), {}, {}))
    call.update({"status": "completed", "duration_s": 120, "billable_seconds": 120, "outcome": {"resolved": True}, "latency": {"ttfb_p50_ms": 500, "ttfb_p95_ms": 800}, "cost": {"total": 0.2}})
    headers = auth(tenant)
    qa = client.patch(f"/v1/calls/{call['id']}/qa", json={"score": 90, "rubric": {"resolution": 18}, "issues": []}, headers=headers)
    assert qa.status_code == 200 and qa.json()["model"] == "manual"
    overview = client.get("/v1/analytics/overview", headers=headers).json()
    assert overview["calls"] == 1 and overview["minutes"] == 2
    assert overview["resolution_rate"] == 1 and overview["csat"] == 4.5
    assert client.get("/v1/analytics/tools", headers=headers).json() == {"data": []}


def test_platform_admin_tenants_metrics_and_impersonation() -> None:
    reset()
    tenant = uuid4()
    store.tenants[tenant] = {"id": tenant, "slug": "admin-test", "name": "Admin Test", "status": "trial", "settings": {}, "created_at": datetime.now(UTC)}
    assert client.get("/admin/tenants", headers=auth(tenant)).status_code == 403
    headers = auth(tenant, platform_admin=True)
    listed = client.get("/admin/tenants", headers=headers)
    assert listed.status_code == 200 and listed.json()["data"][0]["id"] == str(tenant)
    updated = client.patch(f"/admin/tenants/{tenant}", json={"status": "active", "plan_code": "pro"}, headers=headers)
    assert updated.status_code == 200 and updated.json()["plan_code"] == "pro"
    assert client.get("/admin/metrics", headers=headers).json()["tenants"] == 1
    token = client.post(f"/admin/tenants/{tenant}/impersonate", headers=headers).json()
    assert token["expires_in"] == 900 and token["tenant_id"] == str(tenant)


@pytest.mark.asyncio
async def test_signed_webhook_delivery_and_retry_schedule() -> None:
    captured: dict[str, str | bytes] = {}

    async def receiver(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        captured["signature"] = request.headers["X-VoiceOS-Signature"]
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(receiver)) as http:
        status = await OutgoingWebhookSender(http).send("https://example.test/hook", {"ok": True}, "secret")
    assert status == 503
    timestamp, signature = str(captured["signature"]).replace("t=", "").replace("v1=", "").split(",")
    expected = hmac.new(b"secret", timestamp.encode() + b"." + bytes(captured["body"]), hashlib.sha256).hexdigest()
    assert hmac.compare_digest(signature, expected)
    retry = delivery_result(1, status)
    assert retry["status"] == "retrying"
    assert retry["next_retry_at"] > datetime.now(UTC)
    assert delivery_result(5, status)["status"] == "failed"


@pytest.mark.asyncio
async def test_postprocessing_creates_qa_for_every_completed_call() -> None:
    memory = MemoryStore()
    repo = MemoryRepository(memory)
    tenant = uuid4()
    call = await repo.create_call(tenant, uuid4(), {}, {})

    class Processor:
        async def process(self, current: dict[str, object]) -> dict[str, object]:
            return {"summary": "ok", "outcome": {"resolved": True}, "qa": {"score": 95, "rubric": {"accuracy": 20}, "issues": []}}

    await _postprocess_call(call["id"], call, repo, Processor())
    detail = await repo.get_call_detail(tenant, call["id"])
    assert detail and detail["qa"]["score"] == 95
