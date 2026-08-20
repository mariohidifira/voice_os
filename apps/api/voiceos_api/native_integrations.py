from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx
import jwt

from .config import Settings, get_settings
from .repository import Repository
from .secrets import SecretCipher

GOOGLE_SCOPES = ["openid", "email", "https://www.googleapis.com/auth/calendar"]


class NativeIntegrations:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings, self.transport = settings, transport

    def google_connect_url(self, tenant_id: UUID, user_id: str) -> str:
        if not self.settings.google_client_id:
            raise RuntimeError("Google OAuth is not configured")
        state = jwt.encode({"tenant_id": str(tenant_id), "sub": user_id, "purpose": "google_oauth", "exp": datetime.now(UTC) + timedelta(minutes=10)}, self.settings.auth_secret, algorithm="HS256")
        query = urlencode({"client_id": self.settings.google_client_id, "redirect_uri": self.settings.google_redirect_uri, "response_type": "code", "scope": " ".join(GOOGLE_SCOPES), "access_type": "offline", "prompt": "consent", "state": state})
        return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"

    async def google_callback(self, code: str, state: str, repo: Repository, cipher: SecretCipher) -> dict[str, Any]:
        claims = jwt.decode(state, self.settings.auth_secret, algorithms=["HS256"], options={"require": ["exp", "tenant_id", "purpose"]})
        if claims["purpose"] != "google_oauth":
            raise ValueError("invalid OAuth state")
        tenant_id = UUID(claims["tenant_id"])
        async with httpx.AsyncClient(transport=self.transport, timeout=15) as client:
            token_response = await client.post("https://oauth2.googleapis.com/token", data={"code": code, "client_id": self.settings.google_client_id, "client_secret": self.settings.google_client_secret, "redirect_uri": self.settings.google_redirect_uri, "grant_type": "authorization_code"})
            token_response.raise_for_status()
            tokens = token_response.json()
            user_response = await client.get("https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": f"Bearer {tokens['access_token']}"})
            user_response.raise_for_status()
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            raise ValueError("Google did not return a refresh token")
        ciphertext, key_id = await cipher.encrypt(refresh_token)
        secret = await repo.create_secret(tenant_id, "google_oauth_refresh", ciphertext, key_id)
        return await repo.upsert_integration(tenant_id, "google", {"scopes": GOOGLE_SCOPES, "refresh_token_secret_id": secret["id"], "account_email": user_response.json().get("email"), "status": "active"})

    async def _google_access_token(self, tenant_id: UUID, repo: Repository, cipher: SecretCipher) -> str:
        integration = await repo.get_integration(tenant_id, "google")
        if not integration or integration["status"] != "active" or not integration.get("refresh_token_secret_id"):
            raise RuntimeError("Google Calendar is not connected")
        secret = await repo.get_secret(tenant_id, integration["refresh_token_secret_id"])
        if not secret:
            raise RuntimeError("Google refresh token is unavailable")
        refresh_token = await cipher.decrypt(secret["ciphertext"], secret["kms_key_id"])
        async with httpx.AsyncClient(transport=self.transport, timeout=15) as client:
            response = await client.post("https://oauth2.googleapis.com/token", data={"client_id": self.settings.google_client_id, "client_secret": self.settings.google_client_secret, "refresh_token": refresh_token, "grant_type": "refresh_token"})
            response.raise_for_status()
            return str(response.json()["access_token"])

    async def execute(self, kind: str, arguments: dict[str, Any], tenant_id: UUID, repo: Repository, cipher: SecretCipher) -> dict[str, Any]:
        if kind == "send_email":
            if not self.settings.resend_api_key:
                return {"error": "integration_unavailable", "message": "Resend is not configured"}
            async with httpx.AsyncClient(transport=self.transport, timeout=15) as client:
                response = await client.post("https://api.resend.com/emails", headers={"Authorization": f"Bearer {self.settings.resend_api_key}"}, json={"from": self.settings.email_from, "to": [arguments["to"]], "subject": arguments["subject"], "html": arguments["body"]})
                response.raise_for_status()
                return {"status": "sent", "id": response.json()["id"]}
        if kind not in {"google_calendar_check", "google_calendar_book"}:
            return {"error": "unsupported_tool", "message": f"Native tool {kind} is not available in API"}
        token = await self._google_access_token(tenant_id, repo, cipher)
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(transport=self.transport, timeout=15) as client:
            if kind == "google_calendar_check":
                day = datetime.fromisoformat(arguments["date"]).date()
                start = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
                end = start + timedelta(days=1)
                response = await client.post("https://www.googleapis.com/calendar/v3/freeBusy", headers=headers, json={"timeMin": start.isoformat(), "timeMax": end.isoformat(), "items": [{"id": "primary"}]})
                response.raise_for_status()
                return {"busy": response.json().get("calendars", {}).get("primary", {}).get("busy", [])}
            start = datetime.fromisoformat(arguments["start"])
            end = start + timedelta(minutes=int(arguments["duration_min"]))
            event = {"summary": arguments["title"], "description": arguments.get("notes"), "start": {"dateTime": start.isoformat()}, "end": {"dateTime": end.isoformat()}}
            if arguments.get("attendee_email"):
                event["attendees"] = [{"email": arguments["attendee_email"]}]
            response = await client.post("https://www.googleapis.com/calendar/v3/calendars/primary/events", headers=headers, json=event)
            response.raise_for_status()
            result = response.json()
            return {"status": "booked", "id": result["id"], "link": result.get("htmlLink")}


def get_native_integrations() -> NativeIntegrations:
    return NativeIntegrations(get_settings())
