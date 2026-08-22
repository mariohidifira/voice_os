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


def evaluate(calls: list[dict[str, Any]], run_id: str) -> dict[str, Any]:
    completed = [
        call
        for call in calls
        if call.get("status") == "completed"
        and call.get("channel") == "web"
        and (call.get("metadata") or {}).get("acceptance_run_id") == run_id
    ][:50]
    ttfb = [
        float(sample)
        for call in completed
        for sample in (call.get("latency") or {}).get("ttfb_samples_ms", [])
    ]
    calls_with_ttfb = sum(
        bool((call.get("latency") or {}).get("ttfb_samples_ms")) for call in completed
    )
    barge_cases = [
        call for call in completed if (call.get("metadata") or {}).get("acceptance_barge_in")
    ]
    successful_barge = [
        call
        for call in barge_cases
        if (samples := (call.get("latency") or {}).get("barge_in_samples_ms", []))
        and float(percentile([float(sample) for sample in samples], 0.95) or 0) <= 300
    ]
    costs_per_minute = []
    provider_usage_complete = 0
    for call in completed:
        duration = float(call.get("duration_s") or 0)
        cost = call.get("cost") or {}
        total = float(cost.get("total_usd") or 0)
        usage = cost.get("usage", [])
        providers = [
            (str(item.get("type")), str(item.get("provider", "")).casefold())
            for item in usage
        ]
        complete_usage = (
            any(kind == "stt_usage" and "deepgram" in provider for kind, provider in providers)
            and any(kind == "llm_usage" and "anthropic" in provider for kind, provider in providers)
            and any(kind == "tts_usage" and "elevenlabs" in provider for kind, provider in providers)
        )
        if complete_usage:
            provider_usage_complete += 1
        if duration > 0 and total > 0 and cost.get("currency") == "USD" and complete_usage:
            costs_per_minute.append(total * 60 / duration)
    recordings = [
        call
        for call in completed
        if (recording := call.get("recording"))
        and recording.get("status") == "ready"
        and recording.get("s3_key")
    ]
    report = {
        "scope": "real_staging_provider_measurement",
        "acceptance_run_id": run_id,
        "calls": len(completed),
        "calls_with_ttfb": calls_with_ttfb,
        "turns_with_ttfb": len(ttfb),
        "ttfb_p50_ms": percentile(ttfb, 0.50),
        "ttfb_p95_ms": percentile(ttfb, 0.95),
        "barge_in_cases": len(barge_cases),
        "barge_in_passed": len(successful_barge),
        "barge_in_pass_rate": len(successful_barge) / len(barge_cases) if barge_cases else 0,
        "cost_per_minute_p50_usd": percentile(costs_per_minute, 0.50),
        "calls_with_complete_provider_usage": provider_usage_complete,
        "recordings": len(recordings),
    }
    checks = {
        "fifty_completed_web_calls": len(completed) == 50,
        "complete_ttfb_coverage": calls_with_ttfb == 50,
        "rnf_01_ttfb_p50": len(ttfb) >= 50 and report["ttfb_p50_ms"] <= 900,
        "rnf_02_ttfb_p95": len(ttfb) >= 50 and report["ttfb_p95_ms"] <= 1800,
        "rnf_03_barge_in": len(barge_cases) >= 20
        and report["barge_in_pass_rate"] >= 0.95,
        "complete_provider_usage": provider_usage_complete == 50,
        "rnf_09_web_cost": len(costs_per_minute) == 50
        and report["cost_per_minute_p50_usd"] <= 0.08,
        "egress_recordings": len(recordings) == 50,
    }
    return {**report, "checks": checks, "passed": all(checks.values())}


def fetch_calls(api_url: str, token: str, tenant_id: str, run_id: str) -> list[dict[str, Any]]:
    headers = {"authorization": f"Bearer {token}", "x-tenant-id": tenant_id}
    with httpx.Client(base_url=api_url.rstrip("/"), headers=headers, timeout=30) as client:
        response = client.get("/v1/calls", params={"channel": "web", "status": "completed"})
        response.raise_for_status()
        summaries = [
            summary
            for summary in response.json()["data"]
            if (summary.get("metadata") or {}).get("acceptance_run_id") == run_id
        ][:50]
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
    parser.add_argument("--run-id", required=True)
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
            args.run_id,
        )
    report = evaluate(calls, args.run_id)
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
