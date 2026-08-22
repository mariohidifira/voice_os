"""Verify Phase 1 media acceptance from real staging call records."""

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any

import httpx


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def evaluate(calls: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [call for call in calls if call.get("status") == "completed"][:50]
    ttfb = [
        float(turn["ttfb_ms"])
        for call in completed
        for turn in call.get("turns", [])
        if turn.get("role") in {"agent", "assistant"} and turn.get("ttfb_ms") is not None
    ]
    barge_cases = [
        call for call in completed if (call.get("metadata") or {}).get("acceptance_barge_in")
    ]
    successful_barge = [
        call
        for call in barge_cases
        if (call.get("latency") or {}).get("barge_in_p95_ms") is not None
        and float(call["latency"]["barge_in_p95_ms"]) <= 300
    ]
    costs_per_minute = []
    for call in completed:
        duration = float(call.get("duration_s") or 0)
        total = float((call.get("cost") or {}).get("total_usd") or 0)
        if duration > 0:
            costs_per_minute.append(total * 60 / duration)
    recordings = [call for call in completed if call.get("recording")]
    report = {
        "scope": "real_staging_provider_measurement",
        "calls": len(completed),
        "turns_with_ttfb": len(ttfb),
        "ttfb_p50_ms": percentile(ttfb, 0.50),
        "ttfb_p95_ms": percentile(ttfb, 0.95),
        "barge_in_cases": len(barge_cases),
        "barge_in_passed": len(successful_barge),
        "barge_in_pass_rate": len(successful_barge) / len(barge_cases) if barge_cases else 0,
        "cost_per_minute_p50_usd": percentile(costs_per_minute, 0.50),
        "recordings": len(recordings),
    }
    checks = {
        "fifty_completed_calls": len(completed) >= 50,
        "rnf_01_ttfb_p50": bool(ttfb) and report["ttfb_p50_ms"] <= 900,
        "rnf_02_ttfb_p95": bool(ttfb) and report["ttfb_p95_ms"] <= 1800,
        "rnf_03_barge_in": len(barge_cases) >= 1 and report["barge_in_pass_rate"] >= 0.95,
        "rnf_09_web_cost": bool(costs_per_minute) and report["cost_per_minute_p50_usd"] <= 0.08,
        "egress_recordings": len(completed) >= 50 and len(recordings) == len(completed),
    }
    return {**report, "checks": checks, "passed": all(checks.values())}


def fetch_calls(api_url: str, token: str, tenant_id: str) -> list[dict[str, Any]]:
    headers = {"authorization": f"Bearer {token}", "x-tenant-id": tenant_id}
    with httpx.Client(base_url=api_url.rstrip("/"), headers=headers, timeout=30) as client:
        response = client.get("/v1/calls", params={"channel": "web", "status": "completed"})
        response.raise_for_status()
        summaries = response.json()["data"][:50]
        calls = []
        for summary in summaries:
            detail = client.get(f"/v1/calls/{summary['id']}")
            detail.raise_for_status()
            calls.append(detail.json())
        return calls


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="Offline JSON list of call details")
    parser.add_argument("--report", default="reports/phase1-staging-acceptance.json")
    args = parser.parse_args()
    if args.input:
        calls = json.loads(Path(args.input).read_text(encoding="utf-8"))
    else:
        required = ["STAGING_API_URL", "STAGING_ACCEPTANCE_TOKEN", "STAGING_TENANT_ID"]
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise SystemExit(f"Missing environment variables: {', '.join(missing)}")
        calls = fetch_calls(
            os.environ["STAGING_API_URL"],
            os.environ["STAGING_ACCEPTANCE_TOKEN"],
            os.environ["STAGING_TENANT_ID"],
        )
    report = evaluate(calls)
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
