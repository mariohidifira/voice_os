from copy import deepcopy
from typing import Any

import pytest

from scripts.verify_phase1_staging import evaluate

RUN_ID = "phase1-2026-08-22"


def acceptance_calls() -> list[dict[str, Any]]:
    return [
        {
            "id": f"call-{index}",
            "status": "completed",
            "channel": "web",
            "duration_s": 60,
            "cost": {
                "total_usd": 0.05,
                "currency": "USD",
                "usage": [
                    {"type": "stt_usage", "provider": "deepgram"},
                    {"type": "llm_usage", "provider": "anthropic"},
                    {"type": "tts_usage", "provider": "elevenlabs"},
                ],
            },
            "latency": {
                "ttfb_samples_ms": [800 if index < 48 else 1500],
                "barge_in_samples_ms": [250] if index < 20 else [],
            },
            "metadata": {
                "acceptance_run_id": RUN_ID,
                "acceptance_barge_in": index < 20,
            },
            "recording": {
                "s3_key": f"recordings/call-{index}.ogg",
                "status": "ready",
            },
        }
        for index in range(50)
    ]


def test_phase1_staging_acceptance_requires_and_validates_real_metrics() -> None:
    report = evaluate(acceptance_calls(), RUN_ID)
    assert report["calls"] == 50
    assert report["ttfb_p50_ms"] == 800
    assert report["ttfb_p95_ms"] == 800
    assert report["barge_in_pass_rate"] == 1
    assert report["cost_per_minute_p50_usd"] == 0.05
    assert report["recordings"] == 50
    assert report["passed"] is True


def test_phase1_staging_acceptance_ignores_other_runs_and_channels() -> None:
    calls = acceptance_calls()
    calls.extend(
        [
            {**deepcopy(calls[0]), "metadata": {"acceptance_run_id": "other"}},
            {**deepcopy(calls[0]), "channel": "phone"},
        ]
    )
    assert evaluate(calls, RUN_ID)["calls"] == 50


@pytest.mark.parametrize(
    ("mutation", "failed_check"),
    [
        (lambda calls: calls.pop(), "fifty_completed_web_calls"),
        (
            lambda calls: calls[0]["latency"].update(ttfb_samples_ms=[]),
            "complete_ttfb_coverage",
        ),
        (
            lambda calls: calls[19]["metadata"].update(acceptance_barge_in=False),
            "rnf_03_barge_in",
        ),
        (
            lambda calls: calls[0]["cost"]["usage"][1].update(provider="openai"),
            "complete_provider_usage",
        ),
        (
            lambda calls: calls[0]["recording"].update(status="failed"),
            "egress_recordings",
        ),
    ],
)
def test_phase1_staging_acceptance_rejects_incomplete_evidence(
    mutation: Any, failed_check: str
) -> None:
    calls = acceptance_calls()
    mutation(calls)
    report = evaluate(calls, RUN_ID)
    assert report["passed"] is False
    assert report["checks"][failed_check] is False


def test_phase1_staging_acceptance_fails_without_external_evidence() -> None:
    report = evaluate([], RUN_ID)
    assert report["passed"] is False
    assert not any(report["checks"].values())
