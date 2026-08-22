"""Synchronize VoiceOS plans and recurring/metered prices with Stripe."""

import asyncio
import os
from typing import Any

import httpx
from sqlalchemy import text
from voiceos_api.db import SessionFactory


async def stripe_post(client: httpx.AsyncClient, path: str, data: dict[str, str]) -> dict[str, Any]:
    response = await client.post(path, data=data)
    response.raise_for_status()
    return dict(response.json())


async def main() -> None:
    secret = os.environ.get("STRIPE_SECRET_KEY")
    if not secret:
        raise SystemExit("STRIPE_SECRET_KEY is required")
    async with SessionFactory() as db:
        plans = [
            dict(row)
            for row in (
                await db.execute(
                    text(
                        "SELECT * FROM plans WHERE code NOT IN ('trial','enterprise') ORDER BY monthly_price_cents"
                    )
                )
            ).mappings()
        ]
    async with httpx.AsyncClient(
        base_url="https://api.stripe.com/v1",
        headers={"Authorization": f"Bearer {secret}"},
        timeout=30,
    ) as client:
        for plan in plans:
            product = await stripe_post(
                client,
                "/products",
                {"name": f"VoiceOS {plan['name']}", "metadata[plan_code]": str(plan["code"])},
            )
            fixed = await stripe_post(
                client,
                "/prices",
                {
                    "product": str(product["id"]),
                    "currency": "brl",
                    "unit_amount": str(plan["monthly_price_cents"]),
                    "recurring[interval]": "month",
                    "nickname": f"{plan['code']} monthly",
                },
            )
            overage = await stripe_post(
                client,
                "/prices",
                {
                    "product": str(product["id"]),
                    "currency": "brl",
                    "unit_amount": str(plan["overage_cents_per_min"]),
                    "recurring[interval]": "month",
                    "recurring[usage_type]": "metered",
                    "billing_scheme": "per_unit",
                    "nickname": f"{plan['code']} overage minute",
                },
            )
            phone = await stripe_post(
                client,
                "/prices",
                {
                    "product": str(product["id"]),
                    "currency": "brl",
                    "unit_amount": "3900",
                    "recurring[interval]": "month",
                    "nickname": f"{plan['code']} phone number",
                },
            )
            async with SessionFactory() as db, db.begin():
                await db.execute(
                    text(
                        "UPDATE plans SET stripe_price_id=:fixed,stripe_overage_price_id=:overage,stripe_phone_price_id=:phone,updated_at=now() WHERE id=:id"
                    ),
                    {
                        "id": plan["id"],
                        "fixed": fixed["id"],
                        "overage": overage["id"],
                        "phone": phone["id"],
                    },
                )
            print(f"synced {plan['code']}: {fixed['id']}")


if __name__ == "__main__":
    asyncio.run(main())
