import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from .config import Settings, get_settings

PLANS: dict[str, dict[str, Any]] = {
    "trial": {
        "code": "trial",
        "name": "Trial",
        "monthly_price_cents": 0,
        "included_minutes": 60,
        "overage_cents_per_min": 0,
        "max_agents": 1,
        "max_concurrent_calls": 2,
        "features": {"web": True},
    },
    "starter": {
        "code": "starter",
        "name": "Starter",
        "monthly_price_cents": 29700,
        "included_minutes": 500,
        "overage_cents_per_min": 79,
        "max_agents": 2,
        "max_concurrent_calls": 5,
        "features": {"web": True, "phone": True},
    },
    "pro": {
        "code": "pro",
        "name": "Pro",
        "monthly_price_cents": 89700,
        "included_minutes": 2000,
        "overage_cents_per_min": 69,
        "max_agents": 10,
        "max_concurrent_calls": 20,
        "features": {
            "web": True,
            "phone": True,
            "campaigns": True,
            "api": True,
            "webhooks": True,
            "qa": True,
        },
    },
    "business": {
        "code": "business",
        "name": "Business",
        "monthly_price_cents": 249700,
        "included_minutes": 7000,
        "overage_cents_per_min": 59,
        "max_agents": None,
        "max_concurrent_calls": 50,
        "features": {"all": True, "whatsapp": True, "white_label": True},
    },
    "enterprise": {
        "code": "enterprise",
        "name": "Enterprise",
        "monthly_price_cents": 0,
        "included_minutes": 0,
        "overage_cents_per_min": 0,
        "max_agents": None,
        "max_concurrent_calls": None,
        "features": {"all": True},
    },
}


class StripeGateway(Protocol):
    async def checkout(
        self, customer_id: str | None, plan: dict[str, Any], tenant_id: str
    ) -> dict[str, str]: ...
    async def portal(self, customer_id: str) -> dict[str, str]: ...
    async def report_usage(self, item_id: str, quantity: int, idempotency_key: str) -> str: ...
    async def set_quantity(self, item_id: str, quantity: int) -> None: ...


@dataclass
class DevStripeGateway:
    base_url: str

    async def checkout(
        self, customer_id: str | None, plan: dict[str, Any], tenant_id: str
    ) -> dict[str, str]:
        return {
            "url": f"{self.base_url}/billing/dev-checkout?tenant={tenant_id}&plan={plan['code']}",
            "session_id": f"cs_test_{tenant_id[:8]}_{plan['code']}",
        }

    async def portal(self, customer_id: str) -> dict[str, str]:
        return {"url": f"{self.base_url}/billing/dev-portal?customer={customer_id}"}

    async def report_usage(self, item_id: str, quantity: int, idempotency_key: str) -> str:
        return f"ur_test_{item_id}_{quantity}_{idempotency_key[-8:]}"

    async def set_quantity(self, item_id: str, quantity: int) -> None:
        return None


@dataclass
class StripeHTTPGateway:
    settings: Settings

    async def _post(self, path: str, data: dict[str, str]) -> dict[str, Any]:
        async with httpx.AsyncClient(
            base_url="https://api.stripe.com/v1",
            headers={"Authorization": f"Bearer {self.settings.stripe_secret_key}"},
            timeout=15,
        ) as client:
            response = await client.post(path, data=data)
            response.raise_for_status()
            return dict(response.json())

    async def checkout(
        self, customer_id: str | None, plan: dict[str, Any], tenant_id: str
    ) -> dict[str, str]:
        data = {
            "mode": "subscription",
            "success_url": f"{self.settings.app_base_url}/app?billing=success",
            "cancel_url": f"{self.settings.app_base_url}/app?billing=cancelled",
            "client_reference_id": tenant_id,
            "metadata[tenant_id]": tenant_id,
            "metadata[plan_code]": str(plan["code"]),
            "subscription_data[metadata][tenant_id]": tenant_id,
            "subscription_data[metadata][plan_code]": str(plan["code"]),
            "line_items[0][price]": str(plan["stripe_price_id"]),
            "line_items[0][quantity]": "1",
        }
        if customer_id:
            data["customer"] = customer_id
        result = await self._post("/checkout/sessions", data)
        return {"url": str(result["url"]), "session_id": str(result["id"])}

    async def portal(self, customer_id: str) -> dict[str, str]:
        result = await self._post(
            "/billing_portal/sessions",
            {"customer": customer_id, "return_url": f"{self.settings.app_base_url}/app"},
        )
        return {"url": str(result["url"])}

    async def report_usage(self, item_id: str, quantity: int, idempotency_key: str) -> str:
        async with httpx.AsyncClient(
            base_url="https://api.stripe.com/v1",
            headers={
                "Authorization": f"Bearer {self.settings.stripe_secret_key}",
                "Idempotency-Key": idempotency_key,
            },
            timeout=15,
        ) as client:
            response = await client.post(
                f"/subscription_items/{item_id}/usage_records",
                data={"quantity": str(quantity), "action": "increment", "timestamp": "now"},
            )
            response.raise_for_status()
            return str(response.json()["id"])

    async def set_quantity(self, item_id: str, quantity: int) -> None:
        await self._post(
            f"/subscription_items/{item_id}",
            {"quantity": str(quantity), "proration_behavior": "none"},
        )


def stripe_signature_valid(
    payload: bytes, signature: str, secret: str, tolerance_s: int = 300
) -> bool:
    fields = dict(item.split("=", 1) for item in signature.split(",") if "=" in item)
    timestamp = fields.get("t", "")
    supplied = fields.get("v1", "")
    if not timestamp or abs(int(time.time()) - int(timestamp)) > tolerance_s:
        return False
    expected = hmac.new(
        secret.encode(), timestamp.encode() + b"." + payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, supplied)


def stripe_event(payload: bytes) -> dict[str, Any]:
    return dict(json.loads(payload))


def get_stripe_gateway() -> StripeGateway:
    settings = get_settings()
    if settings.app_env in {"dev", "test"} or not settings.stripe_secret_key:
        return DevStripeGateway(settings.app_base_url)
    return StripeHTTPGateway(settings)
