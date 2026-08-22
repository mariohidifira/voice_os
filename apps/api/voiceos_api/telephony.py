import json
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

import httpx
from fastapi import HTTPException
from livekit import api

from .config import Settings, get_settings


class TelephonyProviderError(RuntimeError):
    """Raised when a provider operation cannot be completed safely."""


@dataclass(frozen=True)
class PurchasedNumber:
    e164: str
    provider_sid: str
    capabilities: dict[str, bool]


class NumberProvider(Protocol):
    async def available(self, country: str, area_code: str) -> list[dict[str, Any]]: ...
    async def purchase(self, e164: str) -> PurchasedNumber: ...
    async def release(self, provider_sid: str) -> None: ...


class SipDispatch(Protocol):
    async def create(self, tenant_id: UUID, agent_id: UUID, e164: str) -> str: ...
    async def delete(self, rule_id: str) -> None: ...


class SipOutbound(Protocol):
    async def dial(self, room_name: str, to: str, from_number: str) -> str: ...


class TwilioNumberProvider:
    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.account_sid = account_sid
        self.auth = httpx.BasicAuth(account_sid, auth_token)
        self.transport = transport

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        async with httpx.AsyncClient(
            base_url="https://api.twilio.com/2010-04-01",
            auth=self.auth,
            timeout=15,
            transport=self.transport,
        ) as client:
            try:
                response = await client.request(method, path, **kwargs)
            except httpx.HTTPError as exc:
                raise TelephonyProviderError("Twilio connection failed") from exc
        if response.status_code >= 400:
            try:
                detail = str(response.json().get("message") or "")
            except (ValueError, AttributeError):
                detail = response.text
            raise TelephonyProviderError(
                f"Twilio HTTP {response.status_code}: {detail[:200]}"
            )
        return response

    async def available(self, country: str, area_code: str) -> list[dict[str, Any]]:
        response = await self._request(
            "GET",
            f"/Accounts/{self.account_sid}/AvailablePhoneNumbers/{country}/Local.json",
            params={
                "Contains": f"+55{area_code}*" if country == "BR" else f"+{area_code}*",
                "VoiceEnabled": "true",
                "PageSize": 20,
            },
        )
        return [
            {
                "e164": item["phone_number"],
                "friendly_name": item.get("friendly_name") or item["phone_number"],
                "locality": item.get("locality"),
                "region": item.get("region"),
                "capabilities": {
                    key.lower(): bool(value)
                    for key, value in (item.get("capabilities") or {}).items()
                },
            }
            for item in response.json().get("available_phone_numbers", [])
        ]

    async def purchase(self, e164: str) -> PurchasedNumber:
        response = await self._request(
            "POST",
            f"/Accounts/{self.account_sid}/IncomingPhoneNumbers.json",
            data={"PhoneNumber": e164},
        )
        item = response.json()
        return PurchasedNumber(
            e164=str(item["phone_number"]),
            provider_sid=str(item["sid"]),
            capabilities={
                key.lower(): bool(value)
                for key, value in (item.get("capabilities") or {}).items()
            },
        )

    async def release(self, provider_sid: str) -> None:
        await self._request(
            "DELETE",
            f"/Accounts/{self.account_sid}/IncomingPhoneNumbers/{provider_sid}.json",
        )


class LiveKitSipDispatch:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def create(self, tenant_id: UUID, agent_id: UUID, e164: str) -> str:
        metadata = json.dumps(
            {
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "channel": "phone_inbound",
            }
        )
        client = api.LiveKitAPI(
            self.settings.livekit_url,
            self.settings.livekit_api_key,
            self.settings.livekit_api_secret,
        )
        try:
            request = api.CreateSIPDispatchRuleRequest(
                rule=api.SIPDispatchRule(
                    dispatch_rule_individual=api.SIPDispatchRuleIndividual(
                        room_prefix="call_"
                    )
                ),
                trunk_ids=[self.settings.livekit_sip_trunk_id_inbound],
                inbound_numbers=[e164],
                name=f"voiceos-{e164}",
                metadata=metadata,
                room_config=api.RoomConfiguration(
                    agents=[
                        api.RoomAgentDispatch(
                            agent_name="voiceos-agent", metadata=metadata
                        )
                    ]
                ),
            )
            created = await client.sip.create_dispatch_rule(request)
            return str(created.sip_dispatch_rule_id)
        except Exception as exc:
            raise TelephonyProviderError("LiveKit SIP dispatch creation failed") from exc
        finally:
            await client.aclose()

    async def delete(self, rule_id: str) -> None:
        client = api.LiveKitAPI(
            self.settings.livekit_url,
            self.settings.livekit_api_key,
            self.settings.livekit_api_secret,
        )
        try:
            await client.sip.delete_dispatch_rule(
                api.DeleteSIPDispatchRuleRequest(sip_dispatch_rule_id=rule_id)
            )
        except Exception as exc:
            raise TelephonyProviderError("LiveKit SIP dispatch deletion failed") from exc
        finally:
            await client.aclose()


class LiveKitSipOutbound:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def dial(self, room_name: str, to: str, from_number: str) -> str:
        if not self.settings.livekit_sip_trunk_id_outbound:
            raise TelephonyProviderError("LiveKit outbound SIP trunk is not configured")
        client = api.LiveKitAPI(
            self.settings.livekit_url,
            self.settings.livekit_api_key,
            self.settings.livekit_api_secret,
        )
        try:
            participant = await client.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    sip_trunk_id=self.settings.livekit_sip_trunk_id_outbound,
                    sip_call_to=to,
                    sip_number=from_number,
                    room_name=room_name,
                    participant_identity=f"phone_{to.removeprefix('+')}",
                    participant_name=to,
                    participant_metadata=json.dumps({"channel": "phone_outbound"}),
                    wait_until_answered=True,
                    play_dialtone=False,
                    krisp_enabled=True,
                )
            )
            return str(participant.participant_id or participant.sip_call_id)
        except Exception as exc:
            raise TelephonyProviderError("LiveKit outbound SIP call failed") from exc
        finally:
            await client.aclose()


class DevNumberProvider:
    def __init__(self) -> None:
        self.purchased: set[str] = set()

    async def available(self, country: str, area_code: str) -> list[dict[str, Any]]:
        if country != "BR":
            return []
        prefix = f"+55{area_code}"
        return [
            {
                "e164": f"{prefix}4000{index:04d}",
                "friendly_name": f"({area_code}) 4000-{index:04d}",
                "locality": "São Paulo" if area_code == "11" else None,
                "region": "SP" if area_code == "11" else None,
                "capabilities": {"voice": True, "sms": True, "mms": False},
            }
            for index in range(1, 6)
            if f"{prefix}4000{index:04d}" not in self.purchased
        ]

    async def purchase(self, e164: str) -> PurchasedNumber:
        if e164 in self.purchased:
            raise TelephonyProviderError("Number is no longer available")
        self.purchased.add(e164)
        return PurchasedNumber(
            e164=e164,
            provider_sid=f"PN_DEV_{e164.removeprefix('+')}",
            capabilities={"voice": True, "sms": True, "mms": False},
        )

    async def release(self, provider_sid: str) -> None:
        number = provider_sid.removeprefix("PN_DEV_")
        self.purchased.discard(f"+{number}")


class DevSipDispatch:
    async def create(self, tenant_id: UUID, agent_id: UUID, e164: str) -> str:
        return f"SDR_DEV_{tenant_id.hex[:8]}_{agent_id.hex[:8]}_{e164[-4:]}"

    async def delete(self, rule_id: str) -> None:
        return None


class DevSipOutbound:
    async def dial(self, room_name: str, to: str, from_number: str) -> str:
        return f"SIP_DEV_{room_name}_{to[-4:]}_{from_number[-4:]}"


@dataclass(frozen=True)
class Telephony:
    numbers: NumberProvider
    dispatch: SipDispatch
    outbound: SipOutbound | None = None


_dev_numbers = DevNumberProvider()


def get_telephony() -> Telephony:
    settings = get_settings()
    if settings.app_env in {"dev", "test"}:
        return Telephony(_dev_numbers, DevSipDispatch(), DevSipOutbound())
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        raise HTTPException(
            503,
            detail={
                "code": "telephony_not_configured",
                "message": "Twilio credentials are not configured",
            },
        )
    if not settings.livekit_sip_trunk_id_inbound:
        raise HTTPException(
            503,
            detail={
                "code": "sip_not_configured",
                "message": "LiveKit inbound SIP trunk is not configured",
            },
        )
    return Telephony(
        TwilioNumberProvider(settings.twilio_account_sid, settings.twilio_auth_token),
        LiveKitSipDispatch(settings),
        LiveKitSipOutbound(settings) if settings.livekit_sip_trunk_id_outbound else None,
    )
