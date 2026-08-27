import hashlib
import hmac
from typing import Any

import httpx

from .config import Settings


def valid_meta_signature(payload: bytes, signature: str, secret: str) -> bool:
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature.removeprefix("sha256="), expected)


def incoming_messages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            phone_number_id = value.get("metadata", {}).get("phone_number_id")
            for message in value.get("messages", []):
                kind = str(message.get("type", "text"))
                result.append(
                    {
                        "provider_message_id": str(message["id"]),
                        "phone_number_id": str(phone_number_id or ""),
                        "from": str(message.get("from", "")),
                        "type": kind,
                        "text": str(message.get("text", {}).get("body", "")),
                        "media_id": str(message.get(kind, {}).get("id", "")) or None,
                        "payload": message,
                    }
                )
    return result


class WhatsAppGateway:
    def __init__(self, settings: Settings, access_token: str, phone_number_id: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.transport = transport

    def _use_local_stub(self) -> bool:
        return (
            self.transport is None
            and self.settings.app_env in {"dev", "test"}
            and self.access_token.startswith(("token-", "mock-", "dev-"))
        )

    def _stub_message_id(self, recipient: str, kind: str) -> str:
        digest = hashlib.sha1(
            f"{self.phone_number_id}:{recipient}:{kind}".encode(),
        ).hexdigest()[:16]
        return f"wamid.stub.{digest}"

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        async with httpx.AsyncClient(
            base_url=f"https://graph.facebook.com/{self.settings.whatsapp_graph_version}",
            headers={"Authorization": f"Bearer {self.access_token}"},
            transport=self.transport,
            timeout=10,
        ) as client:
            response = await client.request(method, path, **kwargs)
            response.raise_for_status()
            return response

    async def download_media(self, media_id: str) -> bytes:
        if self._use_local_stub():
            return f"stub-media:{media_id}".encode()
        metadata = (await self._request("GET", f"/{media_id}")).json()
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {self.access_token}"}, transport=self.transport, timeout=10) as client:
            response = await client.get(str(metadata["url"]))
            response.raise_for_status()
            if len(response.content) > 16 * 1024 * 1024:
                raise ValueError("WhatsApp media exceeds 16 MB")
            return response.content

    async def send_text(self, recipient: str, text: str) -> str:
        if self._use_local_stub():
            return self._stub_message_id(recipient, "text")
        response = await self._request("POST", f"/{self.phone_number_id}/messages", json={"messaging_product": "whatsapp", "recipient_type": "individual", "to": recipient, "type": "text", "text": {"preview_url": False, "body": text[:4096]}})
        return str(response.json()["messages"][0]["id"])

    async def send_audio(self, recipient: str, media_id: str) -> str:
        if self._use_local_stub():
            return self._stub_message_id(recipient, "audio")
        response = await self._request("POST", f"/{self.phone_number_id}/messages", json={"messaging_product": "whatsapp", "to": recipient, "type": "audio", "audio": {"id": media_id}})
        return str(response.json()["messages"][0]["id"])

    async def send_audio_bytes(
        self,
        recipient: str,
        audio: bytes,
        *,
        filename: str = "reply.mp3",
        content_type: str = "audio/mpeg",
    ) -> str:
        if self._use_local_stub():
            return await self.send_audio(recipient, f"stub-media-{filename}")
        response = await self._request(
            "POST",
            f"/{self.phone_number_id}/media",
            data={"messaging_product": "whatsapp"},
            files={"file": (filename, audio, content_type)},
        )
        return await self.send_audio(recipient, str(response.json()["id"]))
