from livekit.agents import MetricsCollectedEvent, SessionUsageUpdatedEvent
from livekit.agents.metrics import AgentSessionUsage, InterruptionMetrics
from livekit.agents.metrics.usage import LLMModelUsage, STTModelUsage, TTSModelUsage
from voiceos_voice.accounting import CallAccounting, estimate_mos


def test_accounting_aggregates_latency_usage_and_cost(monkeypatch: object) -> None:
    accounting = CallAccounting(turns=4)
    for ttfb in (0.1, 0.2, 0.4):
        accounting.observe_e2e_latency(ttfb)
    accounting.observe_metric(
        MetricsCollectedEvent(
            metrics=InterruptionMetrics(
                timestamp=0,
                total_duration=1,
                prediction_duration=0.1,
                detection_delay=0.2,
                num_interruptions=2,
                num_backchannels=1,
                num_requests=3,
            )
        )
    )
    accounting.observe_usage(
        SessionUsageUpdatedEvent(
            usage=AgentSessionUsage(
                [
                    STTModelUsage(provider="deepgram", model="nova-3", audio_duration=60),
                    LLMModelUsage(
                        provider="anthropic",
                        model="claude-sonnet-4-6",
                        input_tokens=1_000_000,
                        output_tokens=100_000,
                    ),
                    TTSModelUsage(
                        provider="elevenlabs", model="eleven_flash_v2_5", characters_count=1000
                    ),
                ]
            )
        )
    )
    accounting.observe_network(1.0, 20.0, 80.0)
    assert accounting.latency() == {
        "ttfb_p50_ms": 200,
        "ttfb_p95_ms": 400,
        "ttfb_samples_ms": [100, 200, 400],
        "turns": 4,
        "barge_ins": 2,
        "barge_in_p50_ms": 200,
        "barge_in_p95_ms": 200,
        "barge_in_samples_ms": [200, 200],
        "network": {
            "packet_loss_pct": 1.0,
            "jitter_ms": 20.0,
            "rtt_ms": 80.0,
            "mos": estimate_mos(1.0, 20.0, 80.0),
            "samples": [
                {
                    "packet_loss_pct": 1.0,
                    "jitter_ms": 20.0,
                    "rtt_ms": 80.0,
                    "mos": estimate_mos(1.0, 20.0, 80.0),
                }
            ],
        },
    }
    assert estimate_mos(0, 5, 40) > estimate_mos(8, 80, 500)
    cost = accounting.cost(60)
    assert cost["stt_usd"] == 0.0048
    assert cost["llm_usd"] == 4.5
    assert cost["tts_usd"] == 0.05
    assert cost["livekit_usd"] == 0.01
    assert cost["total_usd"] == 4.5648


def test_representative_web_minute_cost_model_is_within_rnf_09() -> None:
    accounting = CallAccounting(
        usage=[
            {"type": "stt_usage", "provider": "deepgram", "audio_duration": 60},
            {
                "type": "llm_usage",
                "provider": "anthropic",
                "input_tokens": 1000,
                "output_tokens": 200,
            },
            {"type": "tts_usage", "provider": "elevenlabs", "characters_count": 500},
        ]
    )
    cost = accounting.cost(60)
    assert cost["total_usd"] == 0.0458
    assert cost["total_usd"] <= 0.08
