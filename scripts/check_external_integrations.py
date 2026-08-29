"""Read-only connectivity checks for commercial providers using Windows keyring."""

from __future__ import annotations

import asyncio

import httpx
from start_local_with_keyring import load_credentials


async def check_http(url: str, *, auth: httpx.Auth | None = None, headers: dict[str, str] | None = None) -> str:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, auth=auth, headers=headers)
        return "available" if response.is_success else f"rejected_http_{response.status_code}"
    except Exception as exc:  # pragma: no cover - depends on external network
        return f"error_{type(exc).__name__}"


async def main() -> int:
    values, _ = load_credentials()
    results: dict[str, str] = {}

    if values.get("AWS_ACCESS_KEY_ID") and values.get("AWS_SECRET_ACCESS_KEY"):
        try:
            import boto3

            client = boto3.client(
                "sts",
                region_name=values.get("AWS_REGION") or "sa-east-1",
                aws_access_key_id=values["AWS_ACCESS_KEY_ID"],
                aws_secret_access_key=values["AWS_SECRET_ACCESS_KEY"],
            )
            client.get_caller_identity()
            results["aws"] = "available"
        except Exception as exc:  # pragma: no cover - depends on external account
            results["aws"] = f"error_{type(exc).__name__}"
    else:
        results["aws"] = "missing_credentials"

    sid = values.get("TWILIO_ACCOUNT_SID")
    token = values.get("TWILIO_AUTH_TOKEN")
    results["twilio"] = (
        await check_http(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json",
            auth=httpx.BasicAuth(sid or "", token or ""),
        )
        if sid and token
        else "missing_credentials"
    )

    stripe_key = values.get("STRIPE_SECRET_KEY")
    results["stripe"] = (
        await check_http(
            "https://api.stripe.com/v1/account",
            headers={"Authorization": f"Bearer {stripe_key}"},
        )
        if stripe_key
        else "missing_credentials"
    )

    for provider, status in results.items():
        print(f"{provider}: {status}")
    required = {"aws", "twilio", "stripe"}
    return 0 if all(results[name] == "available" for name in required) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
