import json
from uuid import uuid4

import httpx
import pytest
from voiceos_api.config import Settings
from voiceos_api.native_integrations import NativeIntegrations
from voiceos_api.repository import MemoryRepository
from voiceos_api.secrets import EnvelopeCipher
from voiceos_api.store import MemoryStore


@pytest.mark.asyncio
async def test_google_oauth_refresh_calendar_and_resend() -> None:
    requests: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.path == "/token" and b"authorization_code" in request.content:
            return httpx.Response(200, json={"access_token": "access-1", "refresh_token": "refresh-1"})
        if request.url.path == "/token":
            assert b"refresh-1" in request.content
            return httpx.Response(200, json={"access_token": "access-2"})
        if request.url.path.endswith("/userinfo"):
            return httpx.Response(200, json={"email": "owner@example.com"})
        if request.url.path.endswith("/freeBusy"):
            return httpx.Response(200, json={"calendars": {"primary": {"busy": [{"start": "2026-08-20T10:00:00Z"}]}}})
        if request.url.path.endswith("/events"):
            return httpx.Response(200, json={"id": "event-1", "htmlLink": "https://calendar/event-1"})
        if request.url.path == "/emails":
            assert json.loads(request.content)["from"] == "VoiceOS <voice@example.com>"
            return httpx.Response(200, json={"id": "email-1"})
        raise AssertionError(str(request.url))

    settings = Settings(app_env="test", auth_secret="x" * 32, google_client_id="client", google_client_secret="secret", resend_api_key="resend", email_from="VoiceOS <voice@example.com>")
    native = NativeIntegrations(settings, httpx.MockTransport(handler))
    cipher = EnvelopeCipher(settings)
    repo = MemoryRepository(MemoryStore())
    tenant_id = uuid4()
    url = native.google_connect_url(tenant_id, "user-1")
    state = httpx.URL(url).params["state"]
    integration = await native.google_callback("code-1", state, repo, cipher)
    assert integration["account_email"] == "owner@example.com"
    checked = await native.execute("google_calendar_check", {"date": "2026-08-20"}, tenant_id, repo, cipher)
    assert checked["busy"][0]["start"].startswith("2026-08-20")
    booked = await native.execute("google_calendar_book", {"start": "2026-08-20T14:00:00+00:00", "duration_min": 30, "title": "Demo"}, tenant_id, repo, cipher)
    assert booked == {"status": "booked", "id": "event-1", "link": "https://calendar/event-1"}
    email = await native.execute("send_email", {"to": "a@example.com", "subject": "Olá", "body": "Teste"}, tenant_id, repo, cipher)
    assert email == {"status": "sent", "id": "email-1"}
    assert len(requests) == 7
