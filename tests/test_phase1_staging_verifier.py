from scripts.verify_phase1_staging import evaluate


def test_phase1_staging_acceptance_requires_and_validates_real_metrics() -> None:
    calls = [
        {
            "status": "completed",
            "duration_s": 60,
            "cost": {"total_usd": 0.05},
            "latency": {"barge_in_p95_ms": 250},
            "metadata": {"acceptance_barge_in": index < 20},
            "turns": [
                {"role": "user", "ttfb_ms": None},
                {"role": "agent", "ttfb_ms": 800 if index < 48 else 1500},
            ],
            "recording": {"storage_key": f"recordings/call-{index}.ogg"},
        }
        for index in range(50)
    ]
    report = evaluate(calls)
    assert report["calls"] == 50
    assert report["ttfb_p50_ms"] == 800
    assert report["ttfb_p95_ms"] == 800
    assert report["barge_in_pass_rate"] == 1
    assert report["cost_per_minute_p50_usd"] == 0.05
    assert report["passed"] is True


def test_phase1_staging_acceptance_fails_without_external_evidence() -> None:
    report = evaluate([])
    assert report["passed"] is False
    assert not any(report["checks"].values())
