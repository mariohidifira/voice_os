from livekit.agents import MetricsCollectedEvent, SessionUsageUpdatedEvent
from livekit.agents.metrics import AgentSessionUsage, InterruptionMetrics, TTSMetrics
from livekit.agents.metrics.usage import LLMModelUsage, STTModelUsage, TTSModelUsage
from voiceos_voice.accounting import CallAccounting


def test_accounting_aggregates_latency_usage_and_cost(monkeypatch: object) -> None:
    accounting = CallAccounting(turns=4)
    for ttfb in (0.1, 0.2, 0.4):
        accounting.observe_metric(
            MetricsCollectedEvent(
                metrics=TTSMetrics(label="elevenlabs", request_id="r", timestamp=0, ttfb=ttfb, duration=1, audio_duration=1, cancelled=False, characters_count=100, streamed=True)
            )
        )
    accounting.observe_metric(
        MetricsCollectedEvent(metrics=InterruptionMetrics(timestamp=0, total_duration=1, prediction_duration=0.1, detection_delay=0.2, num_interruptions=2, num_backchannels=1, num_requests=3))
    )
    accounting.observe_usage(
        SessionUsageUpdatedEvent(
            usage=AgentSessionUsage(
                [
                    STTModelUsage(provider="deepgram", model="nova-3", audio_duration=60),
                    LLMModelUsage(provider="anthropic", model="claude-sonnet-4-6", input_tokens=1_000_000, output_tokens=100_000),
                    TTSModelUsage(provider="elevenlabs", model="eleven_flash_v2_5", characters_count=1000),
                ]
            )
        )
    )
    assert accounting.latency() == {"ttfb_p50_ms": 200, "ttfb_p95_ms": 400, "turns": 4, "barge_ins": 2}
    cost = accounting.cost(60)
    assert cost["stt_usd"] == 0.0048
    assert cost["llm_usd"] == 4.5
    assert cost["tts_usd"] == 0.05
    assert cost["livekit_usd"] == 0.01
    assert cost["total_usd"] == 4.5648
