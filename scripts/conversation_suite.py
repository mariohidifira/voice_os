"""Deterministic conversation acceptance runner for PR (text) and nightly (audio)."""

import argparse
import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from voiceos_voice.contracts import LLMResponse
from voiceos_voice.providers import MockLLM, MockRAG, MockSTT, MockTTS
from voiceos_voice.session import VoiceSession
from voiceos_voice.tools import ToolRegistry

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    passed: bool
    elapsed_ms: float
    error: str | None = None


def load_cases(mode: str) -> list[dict[str, Any]]:
    path = ROOT / "tests" / "conversations" / f"{mode}.yaml"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON-compatible YAML list")
    minimum = 25 if mode == "text" else 10
    if len(data) < minimum:
        raise ValueError(f"{mode} suite requires at least {minimum} cases, found {len(data)}")
    return data


async def run_case(case: dict[str, Any], mode: str) -> CaseResult:
    started = time.perf_counter()
    registry = ToolRegistry()
    called: list[dict[str, Any]] = []
    tool = case.get("tool")
    replies: list[LLMResponse]
    if tool:
        async def handler(arguments: dict[str, Any]) -> dict[str, Any]:
            called.append(arguments)
            if tool.get("error"):
                raise RuntimeError(str(tool["error"]))
            return {"status": "ok", **tool.get("result", {})}

        registry.register(tool["name"], tool.get("schema", {"type": "object"}), handler)
        replies = [MockLLM.tool(tool["name"], tool.get("arguments", {})), LLMResponse(text=case["reply"])]
    else:
        replies = [LLMResponse(text=case["reply"])]
    events: list[str] = []

    async def sink(event: Any) -> None:
        events.append(event.type)

    session = VoiceSession(
        MockLLM(replies.copy()),
        MockLLM(replies.copy()),
        MockTTS(),
        MockTTS(),
        registry,
        "Siga o template e nunca invente dados.",
        rag=MockRAG(case.get("knowledge", [])) if "knowledge" in case else None,
        event_sink=sink,
    )
    try:
        user = str(case["user"])
        if mode == "audio":
            stt = MockSTT(transcript=user)
            user = await stt.transcribe(user.encode("utf-8"), language="pt-BR")
            if stt.calls != 1:
                raise AssertionError("audio input did not traverse STT")
        reply, audio = await session.turn(user)
        expected = case.get("contains", [])
        if expected and not any(str(term).casefold() in reply.casefold() for term in expected):
            raise AssertionError(f"reply does not contain any of {expected!r}")
        if not audio:
            raise AssertionError("TTS produced no audio")
        if tool and (not called or session.metrics.tool_calls != 1):
            raise AssertionError(f"tool {tool['name']} was not called exactly once")
        if case.get("knowledge") and "<knowledge>" not in repr(session.history):
            raise AssertionError("knowledge was not isolated in a tagged data block")
        if case.get("interrupt"):
            session._speaking_task = asyncio.create_task(asyncio.sleep(2, result=[b"audio"]))
            interrupted = await session.interrupt(str(case["interrupt"]))
            if not interrupted or "barge_in" not in events:
                raise AssertionError("barge-in did not cancel speech and emit an event")
        if case.get("backchannel"):
            session._speaking_task = asyncio.create_task(asyncio.sleep(0, result=[b"audio"]))
            if await session.interrupt(str(case["backchannel"])):
                raise AssertionError("backchannel incorrectly interrupted speech")
        return CaseResult(str(case["id"]), True, (time.perf_counter() - started) * 1000)
    except Exception as error:
        return CaseResult(str(case.get("id", "unknown")), False, (time.perf_counter() - started) * 1000, str(error))


async def run_suite(mode: str) -> dict[str, Any]:
    cases = load_cases(mode)
    results = [await run_case(case, mode) for case in cases]
    elapsed = sorted(result.elapsed_ms for result in results)
    passed = sum(result.passed for result in results)
    by_id = {result.case_id: result for result in results}
    interruption_cases = [case for case in cases if case.get("interrupt")]
    interruption_passed = sum(by_id[str(case["id"])].passed for case in interruption_cases)
    report = {
        "mode": mode,
        "cases": len(results),
        "passed": passed,
        "pass_rate": passed / len(results),
        "measurement_scope": "deterministic_local_not_provider_latency",
        "simulated_turn_p50_ms": elapsed[len(elapsed) // 2],
        "simulated_turn_p95_ms": elapsed[min(len(elapsed) - 1, int(len(elapsed) * 0.95))],
        "barge_in_cases": len(interruption_cases),
        "barge_in_passed": interruption_passed,
        "barge_in_pass_rate": interruption_passed / len(interruption_cases) if interruption_cases else None,
        "failures": [{"id": result.case_id, "error": result.error} for result in results if not result.passed],
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("text", "audio"), required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    report = asyncio.run(run_suite(args.mode))
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["pass_rate"] >= 0.95 else 1


if __name__ == "__main__":
    raise SystemExit(main())
