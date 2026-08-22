import math
import os
from dataclasses import dataclass, field
from typing import Any

from livekit.agents import MetricsCollectedEvent, SessionUsageUpdatedEvent


def _rate(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _percentile(values: list[float], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return round(ordered[index] * 1000)


@dataclass
class CallAccounting:
    ttfb: list[float] = field(default_factory=list)
    barge_in_reaction: list[float] = field(default_factory=list)
    usage: list[dict[str, Any]] = field(default_factory=list)
    turns: int = 0
    barge_ins: int = 0

    def observe_metric(self, event: MetricsCollectedEvent) -> None:
        metric = event.metrics
        if metric.type == "interruption_metrics":
            self.barge_ins += metric.num_interruptions
            if metric.num_interruptions and metric.detection_delay >= 0:
                self.barge_in_reaction.extend(
                    [metric.detection_delay] * metric.num_interruptions
                )

    def observe_e2e_latency(self, latency: float | None) -> None:
        if latency is not None and latency >= 0:
            self.ttfb.append(latency)

    def observe_usage(self, event: SessionUsageUpdatedEvent) -> None:
        self.usage = [
            {name: getattr(item, name) for name in type(item).__annotations__}
            for item in event.usage.model_usage
        ]

    def latency(self) -> dict[str, Any]:
        return {
            "ttfb_p50_ms": _percentile(self.ttfb, 0.50),
            "ttfb_p95_ms": _percentile(self.ttfb, 0.95),
            "ttfb_samples_ms": [round(value * 1000) for value in self.ttfb],
            "turns": self.turns,
            "barge_ins": self.barge_ins,
            "barge_in_p50_ms": _percentile(self.barge_in_reaction, 0.50),
            "barge_in_p95_ms": _percentile(self.barge_in_reaction, 0.95),
            "barge_in_samples_ms": [
                round(value * 1000) for value in self.barge_in_reaction
            ],
        }

    def cost(self, duration_s: int) -> dict[str, Any]:
        stt = llm = tts = 0.0
        for item in self.usage:
            kind = item.get("type")
            if kind == "stt_usage":
                stt += float(item.get("audio_duration", 0)) / 60 * _rate("PRICE_DEEPGRAM_NOVA3_USD_PER_MIN", 0.0048)
            elif kind == "llm_usage":
                provider = str(item.get("provider", "")).lower()
                prefix = "ANTHROPIC" if "anthropic" in provider else "OPENAI"
                input_rate = _rate(f"PRICE_{prefix}_INPUT_USD_PER_MTOK", 3.0 if prefix == "ANTHROPIC" else 2.0)
                output_rate = _rate(f"PRICE_{prefix}_OUTPUT_USD_PER_MTOK", 15.0 if prefix == "ANTHROPIC" else 8.0)
                llm += float(item.get("input_tokens", 0)) / 1_000_000 * input_rate
                llm += float(item.get("output_tokens", 0)) / 1_000_000 * output_rate
            elif kind == "tts_usage":
                tts += float(item.get("characters_count", 0)) / 1000 * _rate("PRICE_ELEVENLABS_FLASH_USD_PER_KCHAR", 0.05)
        livekit = duration_s / 60 * _rate("PRICE_LIVEKIT_AGENT_USD_PER_MIN", 0.01)
        components = {"stt_usd": stt, "llm_usd": llm, "tts_usd": tts, "livekit_usd": livekit}
        return {**{key: round(value, 6) for key, value in components.items()}, "total_usd": round(sum(components.values()), 4), "currency": "USD", "usage": self.usage}
