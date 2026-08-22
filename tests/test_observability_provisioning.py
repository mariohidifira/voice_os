import json
from pathlib import Path

import pytest
from voiceos_voice.resilience import CircuitBreaker, resilient_call


def test_all_grafana_dashboards_and_fallback_alert_are_provisioned() -> None:
    root = Path("infra/grafana/provisioning")
    dashboards = ["voiceos-overview.json", "voiceos-pipeline.json", "voiceos-tenant.json", "voiceos-infra.json"]
    assert all(json.loads((root / name).read_text(encoding="utf-8"))["panels"] for name in dashboards)
    alerts = (root / "alerts.yaml").read_text(encoding="utf-8")
    assert "voiceos_provider_fallback_total" in alerts
    assert "voiceos_provider_errors_total" in alerts


@pytest.mark.asyncio
async def test_deepgram_key_chaos_activates_fallback_with_alert_rule() -> None:
    async def deepgram_with_revoked_key() -> str:
        raise PermissionError("401 invalid Deepgram key")

    async def whisper_fallback() -> str:
        return "fallback transcript"

    result, fallback_used = await resilient_call(
        deepgram_with_revoked_key,
        whisper_fallback,
        breaker=CircuitBreaker(failure_threshold=1),
        retries=0,
        timeout_s=1,
    )
    assert result == "fallback transcript" and fallback_used
    assert "Fallback ativo" in Path("infra/grafana/provisioning/alerts.yaml").read_text(encoding="utf-8")
