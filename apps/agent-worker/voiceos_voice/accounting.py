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


def estimate_mos(packet_loss_pct: float, jitter_ms: float, rtt_ms: float) -> float:
    effective_latency = rtt_ms / 2 + jitter_ms * 2 + 10
    latency_penalty = 0.024 * effective_latency
    if effective_latency > 177.3:
        latency_penalty += 0.11 * (effective_latency - 177.3)
    r_factor = max(0.0, min(100.0, 93.2 - latency_penalty - packet_loss_pct * 2.5))
    mos = 1 + 0.035 * r_factor + r_factor * (r_factor - 60) * (100 - r_factor) * 0.000007
    return round(max(1.0, min(4.5, mos)), 2)


@dataclass
class CallAccounting:
    ttfb: list[float] = field(default_factory=list)
    barge_in_reaction: list[float] = field(default_factory=list)
    usage: list[dict[str, Any]] = field(default_factory=list)
    turns: int = 0
    barge_ins: int = 0
    network_samples: list[dict[str, float]] = field(default_factory=list)

    def observe_metric(self, event: MetricsCollectedEvent) -> None:
        metric = event.metrics
        if metric.type == "interruption_metrics":
            self.barge_ins += metric.num_interruptions
            if metric.num_interruptions and metric.detection_delay >= 0:
                self.barge_in_reaction.extend([metric.detection_delay] * metric.num_interruptions)

    def observe_e2e_latency(self, latency: float | None) -> None:
        if latency is not None and latency >= 0:
            self.ttfb.append(latency)

    def observe_network(self, packet_loss_pct: float, jitter_ms: float, rtt_ms: float) -> None:
        if min(packet_loss_pct, jitter_ms, rtt_ms) < 0:
            return
        self.network_samples.append(
            {
                "packet_loss_pct": packet_loss_pct,
                "jitter_ms": jitter_ms,
                "rtt_ms": rtt_ms,
                "mos": estimate_mos(packet_loss_pct, jitter_ms, rtt_ms),
            }
        )

    def observe_usage(self, event: SessionUsageUpdatedEvent) -> None:
        self.usage = [
            {name: getattr(item, name) for name in type(item).__annotations__}
            for item in event.usage.model_usage
        ]

    def latency(self) -> dict[str, Any]:
        network: dict[str, Any] = {}
        if self.network_samples:
            network = {
                name: round(
                    sum(item[name] for item in self.network_samples) / len(self.network_samples),
                    2,
                )
                for name in ("packet_loss_pct", "jitter_ms", "rtt_ms", "mos")
            }
            network["samples"] = self.network_samples
        return {
            "ttfb_p50_ms": _percentile(self.ttfb, 0.50),
            "ttfb_p95_ms": _percentile(self.ttfb, 0.95),
            "ttfb_samples_ms": [round(value * 1000) for value in self.ttfb],
            "turns": self.turns,
            "barge_ins": self.barge_ins,
            "barge_in_p50_ms": _percentile(self.barge_in_reaction, 0.50),
            "barge_in_p95_ms": _percentile(self.barge_in_reaction, 0.95),
            "barge_in_samples_ms": [round(value * 1000) for value in self.barge_in_reaction],
            "network": network,
        }

    def cost(self, duration_s: int) -> dict[str, Any]:
        stt = llm = tts = 0.0
        for item in self.usage:
            kind = item.get("type")
            if kind == "stt_usage":
                stt += (
                    float(item.get("audio_duration", 0))
                    / 60
                    * _rate("PRICE_DEEPGRAM_NOVA3_USD_PER_MIN", 0.0048)
                )
            elif kind == "llm_usage":
                provider = str(item.get("provider", "")).lower()
                prefix = "ANTHROPIC" if "anthropic" in provider else "OPENAI"
                input_rate = _rate(
                    f"PRICE_{prefix}_INPUT_USD_PER_MTOK", 3.0 if prefix == "ANTHROPIC" else 2.0
                )
                output_rate = _rate(
                    f"PRICE_{prefix}_OUTPUT_USD_PER_MTOK", 15.0 if prefix == "ANTHROPIC" else 8.0
                )
                llm += float(item.get("input_tokens", 0)) / 1_000_000 * input_rate
                llm += float(item.get("output_tokens", 0)) / 1_000_000 * output_rate
            elif kind == "tts_usage":
                tts += (
                    float(item.get("characters_count", 0))
                    / 1000
                    * _rate("PRICE_ELEVENLABS_FLASH_USD_PER_KCHAR", 0.05)
                )
        livekit = duration_s / 60 * _rate("PRICE_LIVEKIT_AGENT_USD_PER_MIN", 0.01)
        components = {"stt_usd": stt, "llm_usd": llm, "tts_usd": tts, "livekit_usd": livekit}
        return {
            **{key: round(value, 6) for key, value in components.items()},
            "total_usd": round(sum(components.values()), 4),
            "currency": "USD",
            "usage": self.usage,
        }
